"""PROTOTYPE: freeze Gemini's original pose service; prepare Unity/Python assets."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
COMMIT = "ce538dff7e1a8d1f1a249d7eeed2f5349fdf1b33"
GRPC_URL = "https://packages.grpc.io/archive/2019/12/a02d6b9be81cbadb60eed88b3b44498ba27bcba9-edd81ac6-e3d1-461a-a263-2b06ae913c3f/csharp/grpc_unity_package.2.26.0-dev.zip"
GRPC_SHA = "509af7278e725cc6a291d354365db930ea1bc96fe53bd96dc88cb33ed1c3e797"
parser = argparse.ArgumentParser()
parser.add_argument("--upstream", type=Path, default=ROOT / ".build/Gemini")
args = parser.parse_args()
upstream = args.upstream.resolve()
if not upstream.exists():
    subprocess.run(["git", "clone", "https://github.com/Gemini-team/Gemini.git", str(upstream)], check=True)
    subprocess.run(["git", "-C", str(upstream), "checkout", "--detach", COMMIT], check=True)
assert subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip() == COMMIT
base = upstream / "Gemini-Unity/Packages/gemini/Runtime/Gemini/Scripts"
files = ["Core/ThreadManager.cs", "EMRSensors/Core/Sensor.cs",
         "Networking/Services/Simulation/Pose.cs",
         "Networking/Services/Simulation/SimulationController.cs",
         "Networking/Services/Simulation/SimulationServiceImpl.cs",
         "Networking/ProtobufFiles/simulation/Simulation.cs",
         "Networking/ProtobufFiles/simulation/SimulationGrpc.cs",
         "Networking/ProtobufFiles/sensor_streaming/SensorStreaming.cs",
         "Networking/ProtobufFiles/sensor_streaming/SensorStreamingGrpc.cs"]
dest = ROOT / "unity/Assets/GeminiOriginal"
hashes = {}
for name in files:
    target = dest / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(base / name, target)
    hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
shutil.copyfile(upstream / "LICENSE", dest / "LICENSE.txt")
proto = ROOT / "client/simulation.proto"
shutil.copyfile(upstream / "API/Protobuf/ProtoFiles/simulation/simulation.proto", proto)
generated = ROOT / "client/generated"
generated.mkdir(exist_ok=True)
subprocess.run([sys.executable, "-m", "grpc_tools.protoc", "-I" + str(proto.parent),
                "--python_out=" + str(generated), "--grpc_python_out=" + str(generated), str(proto)], check=True)
archive = ROOT / ".build/grpc-unity.zip"
if not archive.exists(): urllib.request.urlretrieve(GRPC_URL, archive)
assert hashlib.sha256(archive.read_bytes()).hexdigest() == GRPC_SHA, "gRPC archive checksum mismatch"
with zipfile.ZipFile(archive) as z:
    for item in z.infolist():
        parts = Path(item.filename).parts
        if "Plugins" not in parts or item.is_dir(): continue
        relative = Path(*parts[parts.index("Plugins"):])
        if "osx" in relative.parts and ("x86" in relative.parts or relative.name == "x86.meta"):
            continue  # Legacy i386 bundle collides with the required macOS x86_64 player plugin.
        # Editor is Intel, matching Gemini's 2019 plugin. Retain package metadata.
        target = ROOT / "unity/Assets" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(z.read(item))
streaming = ROOT / "unity/Assets/StreamingAssets"
streaming.mkdir(exist_ok=True)
for name in ["replay.json", "enc.png"]:
    shutil.copyfile(ROOT / "data" / name, streaming / name)
(ROOT / "upstream-lock.json").write_text(json.dumps({"repository": "https://github.com/Gemini-team/Gemini",
    "commit": COMMIT, "editor": "2019.4.20f1", "unchanged_source_sha256": hashes,
    "grpc_url": GRPC_URL, "grpc_sha256": GRPC_SHA,
    "scope": "Original SimulationServiceImpl/ThreadManager and protocol dependencies. "
             "No EMR sensor models or restricted Trondheim assets included."}, indent=2))
print("Prepared unchanged Gemini pose service, pinned gRPC plugins, Python bindings and recorded scene data.")
