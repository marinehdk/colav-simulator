"""Add reference-only callback/clock/output hooks to a separately staged source.

No generated output from this tool may be used as the embedded implementation.
The original business expressions remain in place and every insertion is logged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


def code_mask(text: str) -> str:
    """Mask C++ strings/comments with spaces without changing character offsets."""
    pattern = r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\''
    return re.sub(pattern, lambda m: "".join("\n" if c == "\n" else " " for c in m[0]), text, flags=re.S)


def closing(mask: str, start: int, opening: str = "(", closing_char: str = ")") -> int:
    """Find a balanced delimiter in masked C++ source."""
    depth = 0
    for index in range(start, len(mask)):
        if mask[index] == opening:
            depth += 1
        elif mask[index] == closing_char:
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f"Unbalanced C++ delimiter at {start}")


def instrument(path: Path, header: Path) -> dict:
    """Instrument registered callbacks, clock reads and concrete publishers."""
    original_bytes = path.read_bytes()
    original = path.read_text()
    mask = code_mask(original)
    changes = []
    callbacks = []
    bindings = set(re.findall(r"std::bind\s*\(\s*&([\w:]+)::(\w+)", mask))
    for klass, name in sorted(bindings):
        pattern = rf"\bvoid\s+(?:{re.escape(klass)}::)?{re.escape(name)}\s*\("
        matches = list(re.finditer(pattern, mask))
        for match in matches:
            start = mask.index("(", match.start())
            end = closing(mask, start)
            body = end + 1
            while body < len(mask) and mask[body].isspace():
                body += 1
            if body >= len(mask) or mask[body] != "{":
                continue
            arguments = original[start + 1 : end].strip()
            message = re.fullmatch(r"(?:const\s+)?([\w:]+)::(?:ConstSharedPtr|SharedPtr)\s+(\w+)", arguments)
            if arguments and message is None:
                continue
            statement = f'\n    original_reference_trace::Frame original_trace_frame(this, "{name}"'
            if message:
                statement += f", original_reference_trace::message_record(*{message[2]})"
            statement += ");\n"
            changes.append((body + 1, body + 1, statement, "callback_entry"))
            callbacks.append({"class": klass, "function": name, "message_type": message[1] if message else None})
    for match in re.finditer(r"(?:this->)?get_clock\(\)->now\(\)|this->now\(\)|(?<![\w:>.])now\(\)", mask):
        line = original.count("\n", 0, match.start()) + 1
        replacement = f'original_reference_trace::now(this, "{path.name}:{line}")'
        changes.append((match.start(), match.end(), replacement, "clock_read"))
    for match in re.finditer(r"\b(\w+)\s*->\s*publish\s*\(", mask):
        start = mask.index("(", match.start())
        end = closing(mask, start)
        argument = original[start + 1 : end]
        replacement = f'original_reference_trace::publish(this, "{match[1]}", {match[1]}, {argument})'
        changes.append((match.start(), end + 1, replacement, "publish_observation"))
    # Nested replacements (e.g. publish(now())) need an explicit reviewed rule;
    # fail rather than silently drop one instrumentation edit.
    ordered = sorted(changes, key=lambda c: (c[0], c[1]))
    for first, second in zip(ordered, ordered[1:], strict=False):
        if first[1] > second[0]:
            raise ValueError(f"Overlapping trace edits at {path}:{first[0]}")
    text = original
    for start, end, replacement, _ in reversed(ordered):
        text = text[:start] + replacement + text[end:]
    text = f'#include "{header}"\n' + text
    path.write_text(text)
    return {
        "file": str(path),
        "source_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "instrumented_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "callbacks": callbacks,
        "edits": [
            {"kind": kind, "start": start, "end": end, "replacement": replacement}
            for start, end, replacement, kind in ordered
        ],
    }


def main():
    """Instrument only the separately staged reference workspace."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    if not (workspace / "source-staging.json").is_file():
        raise ValueError("Requires a separately verified reference staging")
    if (workspace / "instrumentation.json").exists():
        raise FileExistsError("Reference instrumentation already exists")
    header = workspace / "original_reference_trace.hpp"
    shutil.copyfile(Path(__file__).with_name("reference_trace.hpp"), header)
    paths = [
        "src/gnc/ship_guidance/src/ship_guidance_node.cpp",
        "src/gnc/ship_guidance/src/coordinate_transform_node.cpp",
        "src/gnc/ship_guidance/src/active_route_manager_node.cpp",
        "src/gnc/ship_control/src/ship_control_node.cpp",
        "src/gnc/thrust_allocation/src/thrust_allocation_node.cpp",
        "src/simulation/ship_dynamics/src/ship_dynamics_node.cpp",
        *[
            f"src/environment/env_engines/src/nodes/{name}_node.cpp"
            for name in ("wind_engine", "current_engine", "wave_engine", "force_aggregator")
        ],
    ]
    result = {
        "schema": "original-gnc.reference-instrumentation.v1",
        "files": [instrument(workspace / p, header) for p in paths],
    }
    (workspace / "instrumentation.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({"files": len(result["files"]), "callbacks": sum(len(f["callbacks"]) for f in result["files"])}))


if __name__ == "__main__":
    main()
