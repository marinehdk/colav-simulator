"""Build the original C++ core locally with no ROS libraries or Python extension ABI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import uuid
from pathlib import Path

from extract_native import MESSAGE_PACKAGES, extract
from proposal_patches import PROPOSALS, apply_proposals
from state_fields import SNAPSHOTS


def dependency_fingerprints(dependencies: Path, eigen: Path) -> dict:
    """Follow explicit dependency symlinks without losing header identities."""
    result = {}
    for label, root in (("dependencies", dependencies), ("eigen", eigen)):
        seen = set()
        for directory, children, files in os.walk(root, followlinks=True):
            resolved = Path(directory).resolve()
            if resolved in seen:
                children.clear()
                continue
            seen.add(resolved)
            for name in files:
                path = Path(directory) / name
                result[f"{label}/{path.relative_to(root)}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def write_bindings(manifest: dict, output: Path) -> list[Path]:
    """Expose only the original registered callbacks and read-only state."""
    sources = []
    factories = []
    branches = []
    for name, module in manifest["modules"].items():
        cls = module["class"]
        dispatch = []
        for callback in module["callbacks"]:
            function, message = callback["function"], callback["message_type"]
            if message:
                for package in MESSAGE_PACKAGES:
                    message = message.replace(f"{package}::msg::", f"original_gnc::messages::{package}::")
                argument = f"std::make_shared<{message}>(input.get<{message}>())"
            else:
                argument = ""
            dispatch.append(f'if (function == "{function}") module->{function}({argument});')
        calls = (
            "\n    else ".join(dispatch) + '\n    else throw std::runtime_error("Unknown original callback: " + function);'
        )
        path = output / f"{name}_binding.cpp"
        path.write_text(f'''#include "{name}.cpp"
namespace original_gnc {{
template<> Json Kernel<{cls}>::snapshot() const {{
    const auto& node = *module;
    {SNAPSHOTS[name]}
}}
template<> Json Kernel<{cls}>::invoke(const std::string& function, const Json& input, int64_t time_ns) {{
    context.outputs.clear();
    context.timer_updates.clear();
    context.clock.set(time_ns);
    {calls}
    return {{{{"outputs",context.outputs}},{{"state",snapshot()}},{{"clock_reads",context.clock.reads_consumed()}},
            {{"timer_updates",context.timer_updates}}}};
}}
std::unique_ptr<KernelBase> make_{name}(const Json& parameters, const Json& options) {{
    return std::make_unique<Kernel<{cls}>>("{name}", parameters, options);
}}
}}
''')
        sources.append(path)
        factories.append(f"std::unique_ptr<KernelBase> make_{name}(const Json&, const Json&);")
        branches.append(f'if (name == "{name}") return make_{name}(parameters, options);')
    (output / "include/native_factories.hpp").write_text(
        """#pragma once
#include "native_context.hpp"
namespace original_gnc {
"""
        + "\n".join(factories)
        + """
inline std::unique_ptr<KernelBase> make_kernel(const std::string& name, const Json& parameters, const Json& options) {
"""
        + "\n".join(branches)
        + '\nthrow std::runtime_error("Unknown original GNC module: " + name);\n}\n}\n'
    )
    return sources


def build(
    source: Path, dependencies: Path, output: Path, compiler: str, eigen: Path, proposals: list[str] | None = None
) -> dict:  # noqa: PLR0915
    """Verify, extract and compile a separately identifiable native library."""
    if (output / "build-manifest.json").exists():
        raise FileExistsError("Use a new build directory to preserve existing validation evidence")
    root = Path(__file__).resolve().parents[2]
    support = root / "cpp/original_gnc"
    math_source = support / "reference_math/upstream"
    math_identity = json.loads((math_source / "source-manifest.json").read_text())
    for name, expected in math_identity["files"].items():
        if hashlib.sha256((math_source / Path(name).name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Reference math source identity changed: {name}")
    glibc_source = support / "reference_math/glibc_upstream"
    glibc_identity = json.loads((glibc_source / "source-manifest.json").read_text())
    for name, identity in glibc_identity.items():
        if hashlib.sha256((glibc_source / name).read_bytes()).hexdigest() != identity["sha256"]:
            raise ValueError(f"Reference trigonometry source identity changed: {name}")
    version_header = eigen / "Eigen/src/Core/util/Macros.h"
    version = version_header.read_text()
    if not all(
        token in version
        for token in ("#define EIGEN_WORLD_VERSION 3", "#define EIGEN_MAJOR_VERSION 4", "#define EIGEN_MINOR_VERSION 0")
    ):
        raise ValueError("Original GNC requires the reference Eigen 3.4.0 headers")
    manifest = extract(source, dependencies, output, support)
    if proposals:
        # Colleague-proposal reference builds compile the reviewed semantic
        # changes on top of the mechanical extraction; the ledger records
        # them (dependencies apply first, composition is explicit).
        manifest["colleague_proposal"] = apply_proposals(proposals, source, output)
    sources = write_bindings(manifest, output)
    shutil.copytree(support / "reference_math", output / "reference_math", dirs_exist_ok=True)
    sources.append(output / "reference_math/reference_exp.cpp")
    generated_math = output / "reference_math/glibc_cpp"
    generated_math.mkdir(parents=True, exist_ok=True)
    (generated_math / "s_sin.inc").write_text(
        (glibc_source / "s_sin.c").read_text().replace("extern const union\n{", "extern const union SincosTable\n{")
    )
    (generated_math / "sincostab.inc").write_text(
        (glibc_source / "sincostab.c").read_text().replace("const union {", "extern const union SincosTable {")
    )
    (generated_math / "s_sincos.inc").write_text(
        (glibc_source / "s_sincos.c").read_text().replace('#include "s_sin.c"', '#include "s_sin.inc"')
    )
    sources.extend(
        output / "reference_math" / name
        for name in (
            "reference_tan.cpp",
            "reference_sincos.cpp",
            "reference_sincos_table.cpp",
            "reference_paired_sincos.cpp",
            "reference_atan.cpp",
            "reference_atan2.cpp",
            "reference_hypot.cpp",
            "reference_asincos.cpp",
        )
    )
    sources.extend(Path(path) for path in manifest.get("support_sources", []))
    abi = output / "native_abi.cpp"
    shutil.copyfile(support / "native_abi.cpp", abi)
    sources.append(abi)
    arithmetic = output / "reference_arithmetic.hpp"
    shutil.copyfile(support / "reference_arithmetic.hpp", arithmetic)
    suffix = ".dylib" if platform.system() == "Darwin" else ".so"
    library = output / f"liboriginal_gnc-{uuid.uuid4().hex}{suffix}"
    command = [
        compiler,
        "-std=c++17",
        "-O2",
        "-ffp-contract=off",
        "-include",
        str(arithmetic),
        "-g",
        "-DNDEBUG",
        "-shared",
        "-fPIC",
        "-fno-builtin-tan",
        "-fno-builtin-atan",
        "-fno-builtin-atan2",
        "-fno-builtin-hypot",
        "-fno-builtin-asin",
        "-fno-builtin-acos",
        "-Wno-c++11-narrowing",
        "-I",
        str(output / "reference_math/glibc_compat"),
        "-I",
        str(output / "reference_math/glibc_upstream"),
        "-I",
        str(output / "include"),
        "-isystem",
        str(eigen),
        "-isystem",
        str(dependencies),
        *map(str, sources),
        "-o",
        str(library),
    ]
    subprocess.run(command, check=True)
    dependency_command = ["otool", "-L", str(library)] if platform.system() == "Darwin" else ["ldd", str(library)]
    linked = subprocess.check_output(dependency_command, text=True)
    if any(name in linked for name in ("librcl", "librmw", "librosidl", "libfastrtps", "libfastcdr", "libtf2_ros")):
        raise RuntimeError("A ROS runtime library leaked into the native build")
    exports = None
    if platform.system() == "Darwin":
        exports = subprocess.check_output(["nm", "-gU", str(library)], text=True)
        forbidden = {"_exp", "_sin", "_cos", "_tan", "_atan", "_atan2", "_asin", "_acos", "_hypot", "___sincos_stret"}
        leaked = forbidden.intersection(line.split()[-1] for line in exports.splitlines() if line.split())
        if leaked:
            raise RuntimeError(f"Reference math symbols leaked into global exports: {sorted(leaked)}")
    fingerprint = {
        str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(output.rglob("*"))
        if p.is_file() and p.suffix in {".cpp", ".c", ".hpp", ".h", ".py", ".inc", ".tbl"}
    }
    result = {
        "schema": "original-gnc.native-build.v1",
        "source_manifest_sha256": manifest["source_manifest_sha256"],
        "command": command,
        "compiler": subprocess.check_output([compiler, "--version"], text=True),
        "platform": platform.platform(),
        "source_fingerprints": fingerprint,
        "library": str(library),
        "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
        "extraction_sha256": hashlib.sha256((output / "extraction.json").read_bytes()).hexdigest(),
        "ros_runtime_dependency": False,
        "colleague_proposal": manifest.get("colleague_proposal"),
        "linked_libraries": linked,
        "exported_symbols": exports,
        "floating_point_profile": "eigen-3.4.0-simd-separate-multiply-add",
        "random_profile": "libstdcxx-polar-pair-order",
        "allocator_exp_profile": "glibc-2.35-FMA-compatible-Arm-v21.02",
        "reference_math_source": json.loads((support / "reference_math/upstream/source-manifest.json").read_text()),
        "trigonometry_profile": "glibc-2.35-FMA-library-local-hidden-sin-cos-paired-sincos-tan-atan-atan2-asin-acos-hypot",
        "trigonometry_source": glibc_identity,
        "dependency_files": dependency_fingerprints(dependencies, eigen),
    }
    macros = subprocess.run(
        [compiler, "-std=c++17", "-dM", "-E", "-x", "c++", "-include", "random", "-"],
        input="",
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    result["standard_library"] = [
        line
        for line in macros.splitlines()
        if line.startswith(("#define __GLIBCXX__ ", "#define _GLIBCXX_RELEASE ", "#define _LIBCPP_VERSION "))
    ]
    (output / "build-manifest.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compiler", default="c++")
    parser.add_argument("--eigen", type=Path)
    parser.add_argument(
        "--proposal",
        action="append",
        choices=sorted(PROPOSALS),
        help="Apply reviewed colleague-proposal reference patches after extraction (repeatable, composed)",
    )
    args = parser.parse_args()
    eigen = args.eigen.resolve() if args.eigen else args.dependencies.resolve() / "eigen3"
    report = build(
        args.source.resolve(),
        args.dependencies.resolve(),
        args.output.resolve(),
        args.compiler,
        eigen,
        args.proposal,
    )
    print(json.dumps({"library": report["library"], "sha256": report["library_sha256"]}))
