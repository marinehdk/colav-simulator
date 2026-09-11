"""Extract source observation logic onto explicit parameters, clocks and values."""

from __future__ import annotations

import ast
import difflib
import hashlib
import re
from pathlib import Path
from typing import Any

from native_messages import PRIMITIVES

MODULES = {
    "navigation_mode_observer_node": (
        "src/mission/mission_supervisor/mission_supervisor/navigation_mode_observer_node.py",
        "NavigationModeObserverNode",
    ),
    "operational_risk_observer_node": (
        "src/safety/safety_supervisor/safety_supervisor/operational_risk_observer_node.py",
        "OperationalRiskObserverNode",
    ),
    "operator_command_interpreter": (
        "src/platform/ship_utils/ship_utils/operator_command_interpreter.py",
        "OperatorCommandInterpreter",
    ),
}
HELPERS = {
    "navigation_mode_state_machine": "src/mission/mission_supervisor/mission_supervisor/navigation_mode_state_machine.py",
    "operational_risk_policy": "src/safety/safety_supervisor/safety_supervisor/operational_risk_policy.py",
}


def expression(text: Any) -> str:
    """Render one source AST expression without changing its evaluation."""
    return ast.parse(text, mode="eval").body


class NativeInterfaces(ast.NodeTransformer):
    """Replace ROS boundary calls; retain source policy arithmetic and branches."""

    def __init__(self):
        self.qos_names = set()

    def visit_ClassDef(self, node: Any) -> Any:
        if any(isinstance(base, ast.Name) and base.id == "Node" for base in node.bases):
            node.bases = []
            for method in node.body:
                if isinstance(method, ast.FunctionDef) and method.name == "__init__":
                    method.args = ast.parse("def init(self, settings, clock_ns, steady_s, values): pass").body[0].args
                    prefix = ast.parse("""
self.settings = dict(settings)
self.clock_ns = clock_ns
self.steady_s = steady_s
self.values = values
self.outputs = []
self.inputs = []
self.timers = []
""").body
                    method.body = prefix + method.body
        return self.generic_visit(node)

    def visit_Assign(self, node: Any) -> Any:
        if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "QoSProfile":
            self.qos_names.update(ast.unparse(target) for target in node.targets)
            return ast.copy_location(ast.Pass(), node)
        if any(isinstance(target, ast.Attribute) and ast.unparse(target.value) in self.qos_names for target in node.targets):
            return ast.copy_location(ast.Pass(), node)
        if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "self.create_timer":
            return ast.copy_location(ast.Expr(self.visit(node.value)), node)
        return self.generic_visit(node)

    def visit_Expr(self, node: Any) -> Any:
        if isinstance(node.value, ast.Call):
            name = ast.unparse(node.value.func)
            if name == "super().__init__" or name.startswith("self.get_logger()."):
                return ast.copy_location(ast.Pass(), node)
        return self.generic_visit(node)

    def visit_Attribute(self, node: Any) -> Any:
        if node.attr == "nanoseconds":
            return ast.copy_location(self.visit(node.value), node)
        if (
            node.attr == "value"
            and isinstance(node.value, ast.Call)
            and ast.unparse(node.value.func) == "self.get_parameter"
        ):
            return ast.copy_location(
                ast.Subscript(expression("self.settings"), self.visit(node.value.args[0]), ast.Load()), node
            )
        return self.generic_visit(node)

    def visit_Call(self, node: Any) -> Any:
        name = ast.unparse(node.func)
        if name == "self.get_clock().now":
            return ast.copy_location(expression("self.clock_ns()"), node)
        if name == "time.monotonic":
            return ast.copy_location(expression("self.steady_s()"), node)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "to_msg":
            return ast.copy_location(ast.Call(expression("self.values.stamp"), [self.visit(node.func.value)], []), node)
        node = self.generic_visit(node)
        args = [ast.unparse(arg) for arg in node.args]
        if name == "self.declare_parameter":
            return ast.copy_location(expression("self.settings.setdefault(" + ",".join(args) + ")"), node)
        if name == "self.create_subscription":
            latched = args[3] in self.qos_names
            return ast.copy_location(
                expression(f"self.inputs.append(({args[1]}, {args[2]}.__name__, {args[0]}.type_name, {latched}))"), node
            )
        if name == "self.create_publisher":
            return ast.copy_location(expression(f"self.values.output(self.outputs, {args[0]}, {args[1]})"), node)
        if name == "self.create_timer":
            return ast.copy_location(expression(f"self.timers.append(({args[0]}, {args[1]}.__name__))"), node)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "publish":
            node.func.attr = "emit"
        return node


def message_values(source: Path, dependencies: Any, output: Path):
    """Generate plain typed values from the original message definitions."""
    roots = {p.name: p / "msg" for p in (dependencies / "ros_messages").iterdir() if p.is_dir()}
    roots["ship_interfaces"] = source / "src/interfaces/ship_interfaces/msg"
    emitted = set()
    parts = [
        "from __future__ import annotations",
        "from dataclasses import dataclass, field",
        "from typing import ClassVar, Any",
    ]

    def emit(identity: str):
        if identity in emitted:
            return
        package, name = identity.split("/")
        fields = []
        constants = []
        field_types = {}
        for raw_line in (roots[package] / f"{name}.msg").read_text().splitlines():
            line = raw_line.partition("#")[0].strip()
            if not line:
                continue
            match = re.fullmatch(r"(\S+)\s+(\w+)(?:\s*=\s*(.*)|\s+(.*))?", line)
            if not match:
                raise ValueError(f"Unrecognized message field: {line}")
            token, key, constant, default = match.groups()
            array = re.fullmatch(r"(.+)\[(\d*)\]", token)
            base = array[1] if array else token
            primitive = base in PRIMITIVES
            if primitive:
                value = {"bool": "False", "string": "''"}.get(base, "0.0" if base.startswith("float") else "0")
            else:
                dep = base if "/" in base else package + "/" + base
                emit(dep)
                value = dep.replace("/", "_") + "()"
            if constant is not None:
                if base == "bool":
                    constant = constant.lower() == "true"
                else:
                    constant = ast.literal_eval(constant)
                constants.append(f"    {key}: ClassVar = {constant!r}")
                continue
            if default is not None:
                value = str(default.lower() == "true") if base == "bool" else default
            if array:
                value = f"[{value} for _ in range({array[2]})]" if array[2] else "[]"
            fields.append(f"    {key}: Any = field(default_factory=lambda: {value})")
            field_types[key] = token
        parts.append(
            "@dataclass\nclass "
            + package
            + "_"
            + name
            + ":\n"
            + f'    type_name: ClassVar[str] = "{package}/msg/{name}"\n'
            + f"    field_types: ClassVar[dict] = {field_types!r}\n"
            + "\n".join(constants + fields)
        )
        emitted.add(identity)

    for name in [
        "nav_msgs/Path",
        "nav_msgs/Odometry",
        "diagnostic_msgs/DiagnosticArray",
        "geometry_msgs/WrenchStamped",
        "std_msgs/Float64",
        "std_msgs/Float64MultiArray",
        "std_msgs/String",
        *["ship_interfaces/" + p.stem for p in roots["ship_interfaces"].glob("*.msg")],
    ]:
        emit(name)
    parts.append(
        "REGISTRY = {" + ",".join(repr(n.replace("/", "/msg/")) + ":" + n.replace("/", "_") for n in sorted(emitted)) + "}"
    )
    output.write_text("\n\n".join(parts) + "\n")


def extract(source: Path, dependencies: Path, output: Path) -> dict:
    """Extract unchanged observer logic with explicit native ports and clocks."""
    folder = output / "observers"
    folder.mkdir(exist_ok=True)
    (folder / "__init__.py").write_text("")
    message_values(source, dependencies, folder / "message_values.py")
    entries = {}
    for name, relative in HELPERS.items():
        original = (source / relative).read_bytes()
        (folder / f"{name}.py").write_bytes(original)
        entries[name] = {"source_path": relative, "source_sha256": hashlib.sha256(original).hexdigest(), "unchanged": True}
    for name, (relative, klass) in MODULES.items():
        path = source / relative
        original = path.read_text()
        tree = ast.parse(original)
        body = []
        for original_node in tree.body:
            node = original_node
            if isinstance(node, ast.Import) and any(n.name == "rclpy" for n in node.names):
                continue
            if isinstance(node, ast.ImportFrom):
                if node.module.startswith("rclpy"):
                    continue
                if node.module.endswith(".msg"):
                    package = node.module.removesuffix(".msg")
                    node = ast.ImportFrom(
                        module="message_values",
                        names=[ast.alias(name=package + "_" + n.name, asname=n.asname or n.name) for n in node.names],
                        level=1,
                    )
                elif node.module.startswith(("mission_supervisor.", "safety_supervisor.")):
                    node = ast.ImportFrom(module=node.module.split(".")[-1], names=node.names, level=1)
            if isinstance(node, ast.FunctionDef) and node.name == "main":
                continue
            if isinstance(node, ast.If) and "__name__" in ast.unparse(node.test):
                continue
            body.append(node)
        tree.body = body
        tree = ast.fix_missing_locations(NativeInterfaces().visit(tree))
        native = ast.unparse(tree) + "\n"
        if any(
            token in native for token in ("rclpy", "get_clock", "create_subscription", "get_parameter", "create_publisher")
        ):
            raise ValueError(f"Unextracted observer boundary: {name}")
        target = folder / f"{name}.py"
        target.write_text(native)
        entries[name] = {
            "source_path": relative,
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "native_sha256": hashlib.sha256(native.encode()).hexdigest(),
            "class": klass,
            "complete_diff": "".join(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    native.splitlines(keepends=True),
                    fromfile=relative,
                    tofile=target.name,
                )
            ),
        }
    return entries
