"""Extract the original Python propulsion policy onto explicit values and time."""

from __future__ import annotations

import ast
import difflib
import hashlib
from pathlib import Path

POLICY_PATH = "src/mission/mission_supervisor/mission_supervisor/propulsion_policy_node.py"


class ExplicitTime(ast.NodeTransformer):
    """Replace only ROS clock access and Duration's nanosecond accessor."""

    def visit_Call(self, node: ast.Call) -> ast.AST:
        if ast.unparse(node) == "self.get_clock().now()":
            return ast.copy_location(
                ast.Call(ast.Attribute(ast.Name("self", ast.Load()), "clock_ns", ast.Load()), [], []), node
            )
        return self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        if node.attr == "nanoseconds" and isinstance(node.value, ast.BinOp):
            return ast.copy_location(self.visit(node.value), node)
        return self.generic_visit(node)


# Keep source contract branches together for audit against the frozen implementation.
def extract_policy(source: Path, output: Path) -> dict:  # noqa: PLR0912
    """Keep all policy equations and state initialization from the frozen file."""
    path = source / POLICY_PATH
    original = path.read_text()
    tree = ast.parse(original)
    body = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # No ROS classes are retained, including no emulated Node base.
            module = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
            if module in {"pathlib", "json", "math", "yaml"}:
                body.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name != "main":
            body.append(node)
        elif isinstance(node, ast.ClassDef):
            if node.name == "PropulsionPolicyNode":
                node.name = "OriginalPropulsionPolicy"
                node.bases = []
                for method in node.body:
                    if not isinstance(method, ast.FunctionDef):
                        continue
                    if method.name == "__init__":
                        method.args = (
                            ast.parse(
                                "def init(self, config, scenario, config_file, scenario_file, "
                                "shadow_mode, publish_rate_hz, clock_ns): pass"
                            )
                            .body[0]
                            .args
                        )
                        start = next(
                            i
                            for i, item in enumerate(method.body)
                            if isinstance(item, ast.Assign) and ast.unparse(item.targets[0]) == "self.config_file"
                        )
                        end = next(
                            i
                            for i, item in enumerate(method.body)
                            if isinstance(item, ast.Expr)
                            and isinstance(item.value, ast.Call)
                            and ast.unparse(item.value.func) == "self.create_subscription"
                        )
                        method.body = [ast.parse("self.clock_ns = clock_ns").body[0], *method.body[start:end]]
                        replacements = {
                            "self.config_file": "str(config_file)",
                            "self.scenario_file": "str(scenario_file)",
                            "self.config": "config",
                            "self.scenario": "scenario",
                            "self.shadow_mode": "_as_bool(shadow_mode)",
                            "rate": "float(publish_rate_hz or self.config.get('publish_rate_hz', 2.0))",
                        }
                        for item in method.body:
                            if isinstance(item, ast.Assign) and ast.unparse(item.targets[0]) in replacements:
                                item.value = ast.parse(replacements[ast.unparse(item.targets[0])], mode="eval").body
                    elif method.name == "_tick":
                        # Preserve original JSON serialization and array creation;
                        # delivery is owned by the native stack's explicit ports.
                        method.body = ast.parse("""
policy = self._build_policy()
return [
    {"topic": "/propulsion/policy", "type": "std_msgs/msg/String",
     "fields": {"data": json.dumps(policy, ensure_ascii=True, sort_keys=True)}},
    {"topic": "/propulsion/constraints", "type": "std_msgs/msg/Float64MultiArray",
     "fields": {"layout": {"dim": [], "data_offset": 0}, "data": self._constraints_array(policy)}}
]
""").body
            body.append(node)
    tree.body = body
    tree = ast.fix_missing_locations(ExplicitTime().visit(tree))
    native = '"""Generated from frozen original policy; see extraction manifest."""\n' + ast.unparse(tree) + "\n"
    if "rclpy" in native or "get_clock" in native or "create_subscription" in native:
        raise ValueError("Unextracted policy transport")
    target = output / "original_propulsion_policy.py"
    target.write_text(native)
    return {
        "source_path": POLICY_PATH,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "output_path": str(target),
        "native_sha256": hashlib.sha256(native.encode()).hexdigest(),
        "complete_diff": "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                native.splitlines(keepends=True),
                fromfile=POLICY_PATH,
                tofile=target.name,
            )
        ),
        "transformations": [
            "ROS imports and Node base removed",
            "explicit integer nanosecond clock",
            "typed config input",
            "explicit return of original publications",
        ],
        "callbacks": {
            "/mission/status": "_on_mission_status",
            "/captain/decision": "_on_captain_decision",
            "/ship/odometry": "_on_odometry",
            "/cmd_tau": "_on_cmd_tau",
            "/actuator/capability": "_on_actuator_capability",
            "/env/total_load": "_on_environment_load",
            "/guidance/dp_hold_active": "_on_dp_hold_active",
        },
    }
