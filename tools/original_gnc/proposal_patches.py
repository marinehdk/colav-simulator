"""Colleague-proposal reference patches applied on top of the frozen extraction.

Each proposal is a reviewed semantic change discussed with the colleague
(register docs/research/2026-09-11-colleague-structural-issues-register.md).
Patches run AFTER the mechanical extraction, fail loudly when the frozen
anchor text is absent, and are recorded in extraction.json with a
"colleague-proposal" edit kind so the extraction ledger stays self-describing.
The frozen source itself is never modified.
"""

from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path

# P-C1 (register R3): avoidance speed-policy differentiation.
#
# The guidance surge cap (emergency_avoidance_speed_cap_mps) engages on ANY
# avoidance-tagged leg. Two links in the executed chain force that:
#   1) coordinate_transform_node navigation_mode_code() collapses ALL
#      avoidance-family strings ("emergency_avoidance", "emergency_avoid",
#      "collision_avoidance", "avoidance") onto path protocol code 6, and
#   2) ship_guidance_node navigation_mode_from_code() decodes code 6 back as
#      the literal string "emergency_avoidance", and the cap gate keys off it.
# The proposal therefore carries the colleague's own arbitration distinction
# (route_arbitration_policy.hpp emergency_behavior: only "emergency_avoidance"
# / "emergency_avoid" are emergency) across the code boundary: genuine
# emergency tags keep code 6; non-emergency tags ("collision_avoidance",
# "avoidance") take new code 10 and decode to their real tier. The surge cap
# then engages only for emergency tags; non-emergency "avoidance" legs follow
# the commanded/route speed. Every other avoidance interlock keeps the
# original behavior: is_emergency_avoidance_mode still accepts "avoidance",
# and the coordinate_transform guard/FAP predicate accepts codes 6 and 10.
_PC1_COORDINATE_TRANSFORM_EDITS = (
    {
        "anchor": '''    if (mode == "emergency_avoidance" ||
        mode == "emergency_avoid" ||
        mode == "collision_avoidance" ||
        mode == "avoidance") return 6;
''',
        "replacement": '''    // Colleague-proposal-s1 (P-C1): keep the emergency-tier distinction
    // alive across the path protocol. Genuine emergency tags stay code 6;
    // non-emergency avoidance tags ("collision_avoidance", "avoidance")
    // become code 10 so ship_guidance can decode the true tier.
    if (mode == "emergency_avoidance" ||
        mode == "emergency_avoid") return 6;
    if (mode == "collision_avoidance" ||
        mode == "avoidance") return 10;
''',
    },
    {
        "anchor": '''        [](const NedPoint& pt) { return pt.navigation_mode_code == 6; });
''',
        "replacement": '''        // Colleague-proposal-s1 (P-C1): code 10 is the non-emergency
        // avoidance tier; guard relaxation and FAP handling keep covering
        // every avoidance-tagged route exactly as before.
        [](const NedPoint& pt) {
            return pt.navigation_mode_code == 6 || pt.navigation_mode_code == 10;
        });
''',
    },
)

_PC1_SHIP_GUIDANCE_EDITS = (
    {
        "anchor": '''        case 6: return "emergency_avoidance";
''',
        "replacement": '''        case 6: return "emergency_avoidance";
        // Colleague-proposal-s1 (P-C1): non-emergency avoidance tier
        // (coordinate_transform code 10) decodes to its real tag.
        case 10: return "avoidance";
''',
    },
    {
        "anchor": '''static bool is_emergency_avoidance_mode(const std::string& mode)
{
    const std::string normalized = normalize_navigation_mode(mode);
    return normalized == "emergency_avoidance" ||
           normalized == "emergency_avoid" ||
           normalized == "collision_avoidance" ||
           normalized == "avoidance";
}
''',
        "replacement": '''static bool is_emergency_avoidance_mode(const std::string& mode)
{
    const std::string normalized = normalize_navigation_mode(mode);
    return normalized == "emergency_avoidance" ||
           normalized == "emergency_avoid" ||
           normalized == "collision_avoidance" ||
           normalized == "avoidance";
}

// Colleague-proposal-s1 (P-C1): emergency-tier scope for the avoidance surge
// cap. Mirrors the existing route_arbitration_policy.hpp emergency_behavior()
// definition: only genuine emergency tags qualify. Non-emergency avoidance
// tags ("avoidance", "collision_avoidance") stay covered by
// is_emergency_avoidance_mode for every other interlock.
static bool is_emergency_avoidance_speed_cap_mode(const std::string& mode)
{
    const std::string normalized = normalize_navigation_mode(mode);
    return normalized == "emergency_avoidance" ||
           normalized == "emergency_avoid";
}
''',
    },
    {
        "anchor": '''    const bool emergency_avoidance_active =
        target_is_emergency_avoidance || previous_is_emergency_avoidance;
''',
        "replacement": '''    const bool emergency_avoidance_active =
        target_is_emergency_avoidance || previous_is_emergency_avoidance;
    // Colleague-proposal-s1 (P-C1): cap-scoped predicate; see the surge-cap
    // gate below for the policy rationale.
    const bool emergency_avoidance_speed_cap_active =
        is_emergency_avoidance_speed_cap_mode(target_navigation_mode) ||
        is_emergency_avoidance_speed_cap_mode(previous_navigation_mode);
''',
    },
    {
        "anchor": '''    if (emergency_avoidance_active && !dp_mode_active_ && !final_speed_coupling_blocked) {
''',
        "replacement": '''    // Colleague-proposal-s1 (P-C1) avoidance speed policy: the emergency
    // surge cap engages ONLY when the target or predecessor waypoint carries
    // a genuine emergency tag ("emergency_avoidance"/"emergency_avoid").
    // Non-emergency "avoidance" legs follow the commanded/route speed so a
    // deviation segment transits at cruise pace instead of the 3.2 m/s cap.
    // Safety interlocks are untouched: every other emergency_avoidance_active
    // check (wheel-over, switch radius, cruise floor, corridor, manager
    // gates) keeps the original any-avoidance leg scope, and emergency
    // behavior is byte-identical because an emergency tag still satisfies
    // both predicates.
    if (emergency_avoidance_speed_cap_active && !dp_mode_active_ && !final_speed_coupling_blocked) {
''',
    },
)

PROPOSALS = {
    "P-C1": {
        "id": "P-C1",
        "title": "avoidance speed-policy differentiation",
        "register": "R3",
        "branch": "codex/colleague-proposal-s1",
        "files": {
            "coordinate_transform_node.cpp": {
                "source_relative_path": "src/gnc/ship_guidance/src/coordinate_transform_node.cpp",
                "edits": _PC1_COORDINATE_TRANSFORM_EDITS,
            },
            "ship_guidance_node.cpp": {
                "source_relative_path": "src/gnc/ship_guidance/src/ship_guidance_node.cpp",
                "edits": _PC1_SHIP_GUIDANCE_EDITS,
            },
        },
    },
}


def apply_proposal(proposal_id: str, source: Path, output: Path) -> dict:
    """Apply one reviewed proposal to the extracted outputs and its ledger."""
    proposal = PROPOSALS[proposal_id]
    extraction_path = output / "extraction.json"
    extraction = json.loads(extraction_path.read_text())
    entries = {entry["file"]: entry for entry in extraction["files"]}
    patched = {}
    for file_name, spec in proposal["files"].items():
        if file_name not in entries:
            raise ValueError(f"Proposal {proposal_id}: no extraction ledger entry for {file_name}")
        target = output / file_name
        text = target.read_text()
        ledger = []
        for index, edit in enumerate(spec["edits"]):
            anchor, replacement = edit["anchor"], edit["replacement"]
            occurrences = text.count(anchor)
            if occurrences != 1:
                raise ValueError(
                    f"Proposal {proposal_id} anchor {index} matches {occurrences} times in "
                    f"{file_name}; frozen source layout changed"
                )
            text = text.replace(anchor, replacement)
            ledger.append(
                {
                    "kind": f"colleague-proposal-{proposal['branch']}:{proposal_id}",
                    "before": anchor,
                    "after": replacement,
                }
            )
        target.write_text(text)
        entry = entries[file_name]
        entry["edits"].extend(ledger)
        entry["native_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        original_path = source / spec["source_relative_path"]
        entry["complete_diff"] = "".join(
            difflib.unified_diff(
                original_path.read_text().splitlines(keepends=True),
                text.splitlines(keepends=True),
                fromfile=f"original/{entry['source_path']}",
                tofile=f"native/{entry['source_path']}",
            )
        )
        patched[file_name] = {
            "edit_count": len(ledger),
            "native_sha256": entry["native_sha256"],
        }
    extraction["colleague_proposal"] = {
        "id": proposal["id"],
        "title": proposal["title"],
        "register": proposal["register"],
        "branch": proposal["branch"],
        "patched_files": sorted(patched),
    }
    extraction_path.write_text(json.dumps(extraction, indent=2))
    return {
        "id": proposal["id"],
        "title": proposal["title"],
        "register": proposal["register"],
        "branch": proposal["branch"],
        "patched_files": patched,
    }
