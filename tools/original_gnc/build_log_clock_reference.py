"""Make the original guidance replay's one display-only clock independent of log throttling."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from instrument_reference import closing, code_mask

HELPER = r"""
// Replay-only presentation adapter. Never supplies or skips a business clock.
inline void replay_log_clocks(const rclcpp::Node* node, std::initializer_list<const char*> sites) {
    auto& trace = store();
    if (!trace.replaying()) throw std::runtime_error("Display-clock replay requires a recorded trace");
    while (!trace.finished() && trace.next().at("kind") == "clock") {
        const auto site = trace.next().at("site").get<std::string>();
        bool allowed = false;
        for (const char* candidate : sites) if (site == candidate) allowed = true;
        if (!allowed) break;
        (void) now(node, site.c_str());
    }
}
"""


def build(base: Path, output: Path) -> dict:
    """Copy the existing original-source driver; change only audited log presentation."""
    output.mkdir(parents=True, exist_ok=False)
    driver_path = base / "ship_guidance_node_replay.cpp"
    driver = driver_path.read_text()
    source = Path(re.search(r'#include "([^"]+ship_guidance_node.cpp)"', driver)[1])
    text = source.read_bytes().decode()
    header = Path(re.search(r'#include "([^"]+reference_trace.hpp)"', text)[1])
    new_header = output / "reference_trace.hpp"
    header_text = header.read_bytes().decode()
    if "class Frame {" not in header_text:
        raise ValueError("Unknown reference tracing header")
    new_header.write_text(header_text.replace("class Frame {", HELPER + "\nclass Frame {"))
    mask = code_mask(text)
    edits = []
    for match in re.finditer(r"\bRCLCPP_[A-Z_]+\s*\(", mask):
        opening = mask.index("(", match.start())
        end = closing(mask, opening) + 1
        if mask[end : end + 1] == ";":
            end += 1
        block = text[match.start() : end]
        sites = re.findall(r'original_reference_trace::now\(this, "([^"]+)"\)', block)
        if not sites:
            continue
        if sites != ["ship_guidance_node.cpp:4570"]:
            raise ValueError(f"Unaudited log clock: {sites}")
        if "xte_rejoin_release_guard_until_sec_" not in block or "RCLCPP_WARN_THROTTLE" not in block:
            raise ValueError("The audited display-only warning changed")
        blank = "".join(character if character in "\r\n" else " " for character in block)
        replacement = 'original_reference_trace::replay_log_clocks(this, {"ship_guidance_node.cpp:4570"});'
        edits.append((match.start(), end, blank, replacement, block))
    if len(edits) != 1:
        raise ValueError("Expected exactly the audited XTE-release display clock")
    start, end, blank, replacement, block = edits[0]
    outside = text[:start] + blank + text[end:]
    patched = text[:start] + replacement + blank + text[end:]
    if patched.replace(replacement, "", 1) != outside:
        raise ValueError("A non-log source region changed")
    staged_source = output / "ship_guidance_node.cpp"
    staged_source.write_text(patched.replace(str(header), str(new_header)))
    (output / driver_path.name).write_text(driver.replace(str(source), str(staged_source)))
    cmake = []
    for line in (base / "CMakeLists.txt").read_text().splitlines():
        if line.startswith(
            ("add_executable(", "target_compile_options(", "ament_target_dependencies(", "target_link_libraries(")
        ):
            if "ship_guidance_node_replay" not in line:
                continue
        cmake.append(line)
    (output / "CMakeLists.txt").write_text("\n".join(cmake) + "\n")
    subprocess.run(
        ["cmake", "-S", str(output), "-B", str(output / "build"), "-DCMAKE_BUILD_TYPE=RelWithDebInfo"], check=True
    )
    subprocess.run(["cmake", "--build", str(output / "build"), "-j", "1"], check=True)
    report = {
        "source": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "base_driver": str(driver_path),
        "base_driver_sha256": hashlib.sha256(driver_path.read_bytes()).hexdigest(),
        "source_outside_display_call_sha256": hashlib.sha256(outside.encode()).hexdigest(),
        "display_clock_sites": ["ship_guidance_node.cpp:4570"],
        "original_display_call": block,
        "replay_source_sha256": hashlib.sha256(staged_source.read_bytes()).hexdigest(),
        "header_sha256": hashlib.sha256(new_header.read_bytes()).hexdigest(),
        "binary_sha256": hashlib.sha256((output / "build/ship_guidance_node_replay").read_bytes()).hexdigest(),
        "scope": (
            "Only replay-time logging/clock presentation; "
            "all source business statements and strict event comparisons retained"
        ),
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.base.resolve(), args.output.resolve())
