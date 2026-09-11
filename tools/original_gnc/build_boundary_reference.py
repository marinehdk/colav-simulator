"""Build original-source callback stimulus drivers in a separate reference staging tree."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import build_reference_replay as reference


def build(workspace: Path, output: Path) -> None:
    """Change only reference clock/input plumbing; compile original algorithm bodies."""
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    staging = output / "source"
    shutil.copytree(workspace / "src", staging / "src")
    manifest = json.loads((workspace / "instrumentation.json").read_text())
    original_header = next((workspace / "src").rglob("reference_trace.hpp"), None)
    if original_header is None:
        original_header = workspace / "original_reference_trace.hpp"
    header = original_header.read_text()
    header = header.replace(
        "inline Store& store()",
        "inline int64_t& stimulus_clock_ns() { static int64_t value = 0; return value; }\n\ninline Store& store()",
    )
    header = header.replace(
        ": node->now();", ": (stimulus_clock_ns() ? rclcpp::Time(stimulus_clock_ns(), RCL_ROS_TIME) : node->now());"
    )
    header = header.replace(
        "    size_t index() const { return index_; }",
        "    size_t index() const { return index_; }\n"
        "    size_t next_ordinal(const std::string& node) { return ordinals_[node]; }",
    )
    header_path = staging / "reference_trace.hpp"
    header_path.write_text(header)
    for item in manifest["files"]:
        old = Path(item["file"])
        new = staging / old.relative_to(workspace)
        text = new.read_text()
        # Existing observer sites and original equations stay byte-for-byte;
        # only the explicit test clock header include moves to this staging tree.
        text = text.replace(str(original_header), str(header_path))
        new.write_text(text)
        item["file"] = str(new)
    (staging / "instrumentation.json").write_text(json.dumps(manifest, indent=2))
    original_driver = reference.driver

    def driver(source: Path, callbacks: list[dict]) -> str:
        text = original_driver(source, callbacks)
        text = text.replace(
            "        auto node = std::make_shared",
            "        original_reference_trace::stimulus_clock_ns() = 2000000000000000000LL;\n"
            "        auto node = std::make_shared",
        )
        text = text.replace(
            '        if (!trace.replaying()) throw std::runtime_error("ORIGINAL_GNC_REPLAY_FILE is required");',
            '        const char* stimuli_path = std::getenv("ORIGINAL_GNC_STIMULI");\n'
            '        if (!stimuli_path) throw std::runtime_error("ORIGINAL_GNC_STIMULI is required");\n'
            "        std::ifstream stimuli(stimuli_path);\n"
            '        if (!stimuli) throw std::runtime_error("Cannot read source stimuli");',
        )
        text = text.replace(
            "        while (!trace.finished()) {\n            auto event = trace.next();",
            "        for (std::string line; std::getline(stimuli, line); ) {\n"
            "            auto event = original_reference_trace::Json::parse(line);\n"
            '            event["ordinal"] = trace.next_ordinal(node->get_name());\n'
            '            original_reference_trace::stimulus_clock_ns() = event.at("time_ns").get<int64_t>();',
        )
        return text

    reference.driver = driver
    reference.build(staging, output / "drivers", [Path(x["file"]).stem for x in manifest["files"]])
    (output / "reference-origin.json").write_text(
        json.dumps(
            {
                "workspace": str(workspace),
                "changes": ["reference-only explicit test clock", "reference-only callback input driver"],
                "embedded_algorithm_code_used": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.workspace.resolve(), args.output.resolve())
