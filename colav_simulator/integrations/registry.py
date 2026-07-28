"""Runtime registry with explicit availability and no silent fallback."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import os
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from colav_simulator.core.colav.colav_interface import (
    ICOLAV,
    COLAVType,
    Config,
    LayerConfig,
    SBMPCWrapper,
    VOWrapper,
)
from colav_simulator.core.colav.custom_mpc_adapter import (
    BuildIdentity,
    CustomMPCAdapter,
    FactoryContext,
)
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.core.colav.kuwata_vo_alg.kuwata_vo import VOParams
from colav_simulator.core.colav.sbmpc.sbmpc import SBMPCParams
from colav_simulator.core.guidances import LOSGuidanceParams
from colav_simulator.core.tracking.trackers import KF, GodTracker, ITracker, KFParams


@dataclass(frozen=True)
class IntegrationStatus:
    integration_id: str
    kind: str
    available: bool
    version: str | None
    source: str | None
    commit: str | None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ecosystem_root() -> Path | None:
    """Resolve the configured external repository root without HOME coupling."""
    configured = os.environ.get("COLAV_ECOSYSTEM_ROOT")
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.append(Path.home() / "Code" / "ecosystem")
    return next((path.resolve() for path in candidates if path.exists()), None)


def _add_import_path(path: Path) -> None:
    value = str(path)
    if path.exists() and value not in sys.path:
        sys.path.insert(0, value)


def _repo_commit(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        git_dir = path / ".git"
        if git_dir.is_file():
            marker = git_dir.read_text(encoding="utf-8").strip()
            git_dir = (path / marker.removeprefix("gitdir:").strip()).resolve()
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref: "):
            return head
        reference = head.removeprefix("ref: ")
        loose_ref = git_dir / reference
        if loose_ref.is_file():
            return loose_ref.read_text(encoding="utf-8").strip()
        common_dir = git_dir
        common_dir_file = git_dir / "commondir"
        if common_dir_file.is_file():
            common_dir = (git_dir / common_dir_file.read_text(encoding="utf-8").strip()).resolve()
        packed_refs = common_dir / "packed-refs"
        if packed_refs.is_file():
            for line in packed_refs.read_text(encoding="utf-8").splitlines():
                if line.endswith(f" {reference}"):
                    return line.split(" ", 1)[0]
        return None
    except OSError:
        return None


def _module_status(integration_id: str, kind: str, module_name: str, repo: Path | None = None) -> IntegrationStatus:
    try:
        module = importlib.import_module(module_name)
        try:
            version = importlib.metadata.version(module_name.split(".")[0])
        except importlib.metadata.PackageNotFoundError:
            version = getattr(module, "__version__", None)
        source = getattr(module, "__file__", None)
        return IntegrationStatus(integration_id, kind, True, version, source, _repo_commit(repo))
    except Exception as exc:
        return IntegrationStatus(integration_id, kind, False, None, None, _repo_commit(repo), str(exc))


class IntegrationRegistry:
    """Build algorithms and trackers selected by stable IDs."""

    def __init__(self) -> None:
        root = ecosystem_root()
        self.root = root
        self.repos = {
            "vimmjipda": root / "vimmjipda" if root else None,
            "psbmpc": root / "psbmpc" if root else None,
            "rrt": root / "rrt-rs" if root else None,
            "rlmpc": root / "rlmpc" if root else None,
        }
        if self.repos["vimmjipda"]:
            _add_import_path(self.repos["vimmjipda"])
        if self.repos["rrt"]:
            _add_import_path(self.repos["rrt"])
        if self.repos["rlmpc"]:
            _add_import_path(self.repos["rlmpc"])
        if self.repos["psbmpc"]:
            _add_import_path(self.repos["psbmpc"] / "build" / "psbmpc_interface")
        self._statuses = self._probe_statuses()

    def statuses(self) -> dict[str, IntegrationStatus]:
        return dict(self._statuses)

    def _probe_statuses(self) -> dict[str, IntegrationStatus]:
        builtins = {
            "nominal": IntegrationStatus("nominal", "algorithm", True, None, "colav-simulator", None),
            "vo": IntegrationStatus("vo", "algorithm", True, None, "colav-simulator", None),
            "sbmpc": IntegrationStatus("sbmpc", "algorithm", True, None, "colav-simulator", None),
            "potocnik_simplified_mpc": _module_status(
                "potocnik_simplified_mpc",
                "algorithm",
                "colav_simulator.integrations.potocnik_mpc",
            ),
            "scenario_default": IntegrationStatus("scenario_default", "tracker", True, None, "colav-simulator", None),
            "god": IntegrationStatus("god", "tracker", True, None, "colav-simulator", None),
            "kf": IntegrationStatus("kf", "tracker", True, None, "colav-simulator", None),
        }
        external = {
            "vimmjipda": _module_status(
                "vimmjipda", "tracker", "vimmjipda.vimmjipda_tracker_interface", self.repos["vimmjipda"]
            ),
            "psbmpc": _module_status("psbmpc", "algorithm", "PSBMPCInterface", self.repos["psbmpc"]),
            "rrt": _module_status("rrt", "algorithm", "rrt_star_lib", self.repos["rrt"]),
            "rlmpc": _module_status("rlmpc", "algorithm", "rlmpc.rlmpc_cas", self.repos["rlmpc"]),
        }
        return {**builtins, **external}

    def dependency_manifest(self) -> dict[str, dict[str, Any]]:
        return {name: status.to_dict() for name, status in self.statuses().items()}

    def build_algorithm(
        self,
        algorithm_id: str,
        config: dict[str, Any] | None = None,
        *,
        factory_context: FactoryContext | None = None,
    ) -> ICOLAV | None:
        config = config or {}
        algorithm_id = algorithm_id.lower()
        if algorithm_id == "nominal":
            return None
        if algorithm_id == "vo":
            params = Config(
                name=COLAVType.VO,
                layer1=LayerConfig(vo=VOParams()),
                layer2=LayerConfig(los=LOSGuidanceParams()),
            )
            return VOWrapper(params)
        if algorithm_id == "sbmpc":
            params = Config(
                name=COLAVType.SBMPC,
                layer1=LayerConfig(sbmpc=SBMPCParams()),
                layer2=LayerConfig(los=LOSGuidanceParams()),
            )
            return SBMPCWrapper(params)
        if config.get("factory"):
            return self._build_plugin(algorithm_id, config, factory_context)

        status = self.statuses().get(algorithm_id)
        if status is None:
            return self._build_plugin(algorithm_id, config, factory_context)
        if not status.available:
            raise ColavExecutionError(
                PlanStatus.DEPENDENCY_UNAVAILABLE,
                f"{algorithm_id} unavailable: {status.reason}",
            )
        if algorithm_id == "psbmpc":
            from colav_simulator.integrations.psbmpc import PSBMPCColav  # noqa: PLC0415

            return PSBMPCColav(**config)
        if algorithm_id == "rrt":
            from colav_simulator.integrations.rrt import RRTStarColav  # noqa: PLC0415

            return RRTStarColav(**config)
        if algorithm_id == "rlmpc":
            module = importlib.import_module("rlmpc.rlmpc_cas")
            path = Path(config["config_path"]).expanduser() if "config_path" in config else None
            return module.RLMPC(config=path) if path else module.RLMPC()
        raise ColavExecutionError(PlanStatus.INVALID_INPUT, f"Unsupported algorithm: {algorithm_id}")

    def build_tracker(self, tracker_id: str, config: dict[str, Any] | None = None) -> ITracker | None:
        config = config or {}
        tracker_id = tracker_id.lower()
        if tracker_id == "scenario_default":
            return None
        if tracker_id == "god":
            return GodTracker()
        if tracker_id == "kf":
            params = KFParams.from_dict(config) if config else KFParams()
            return KF(sensor_list=[], params=params)
        if tracker_id == "vimmjipda":
            status = self.statuses()["vimmjipda"]
            if not status.available:
                raise ColavExecutionError(PlanStatus.DEPENDENCY_UNAVAILABLE, f"vimmjipda unavailable: {status.reason}")
            module = importlib.import_module("vimmjipda.vimmjipda_tracker_interface")
            config_path = self._resolve_vimmjipda_config(config)
            params = module.VIMMJIPDAParams.from_yaml(config_path)
            return module.VIMMJIPDA(params=params)
        raise ColavExecutionError(PlanStatus.INVALID_INPUT, f"Unsupported tracker: {tracker_id}")

    def _resolve_vimmjipda_config(self, config: dict[str, Any]) -> Path:
        if config.get("config_path"):
            path = Path(config["config_path"]).expanduser()
        elif os.environ.get("VIMMJIPDA_CONFIG"):
            path = Path(os.environ["VIMMJIPDA_CONFIG"]).expanduser()
        elif self.repos["vimmjipda"]:
            path = self.repos["vimmjipda"] / "config" / "vimmjipda.yaml"
        else:
            path = Path()
        if not path.is_file():
            raise ColavExecutionError(PlanStatus.INVALID_INPUT, f"VIMMJIPDA config not found: {path}")
        return path

    @staticmethod
    def _build_plugin(
        algorithm_id: str,
        config: dict[str, Any],
        context: FactoryContext | None,
    ) -> ICOLAV:
        factory_ref = config.get("factory")
        if not factory_ref or ":" not in factory_ref:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "custom algorithm requires algorithm_config.factory='module:callable'",
            )
        module_name, callable_name = factory_ref.split(":", 1)
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            raise ColavExecutionError(
                PlanStatus.DEPENDENCY_UNAVAILABLE,
                f"{factory_ref} dependency unavailable: {exc}",
            ) from exc
        try:
            factory: Callable[..., ICOLAV] = getattr(module, callable_name)
        except AttributeError as exc:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"{factory_ref} callable does not exist",
            ) from exc
        if context is None:
            context = FactoryContext(
                requested_algorithm=algorithm_id,
                algorithm_seed=0,
            )
        try:
            instance = factory(context=context, **config.get("kwargs", {}))
        except ColavExecutionError:
            raise
        except ImportError as exc:
            raise ColavExecutionError(
                PlanStatus.DEPENDENCY_UNAVAILABLE,
                f"{factory_ref} dependency unavailable: {exc}",
            ) from exc
        except Exception as exc:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"{factory_ref} construction failed: {exc}",
            ) from exc
        if not isinstance(instance, CustomMPCAdapter):
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"{factory_ref} did not return CustomMPCAdapter",
            )
        if instance.descriptor.algorithm_id != algorithm_id:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"{factory_ref} descriptor ID {instance.descriptor.algorithm_id!r} "
                f"does not match requested {algorithm_id!r}",
            )
        dependency_lock = config.get("dependency_lock")
        dependency_lock_path = Path(dependency_lock).expanduser() if dependency_lock else None
        dependency_hash = _file_sha256(dependency_lock_path)
        if dependency_lock_path is not None and dependency_hash == "UNKNOWN":
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"dependency lock not found: {dependency_lock_path}",
            )
        source_path = Path(module.__file__) if getattr(module, "__file__", None) else None
        source_version = getattr(module, "__version__", None)
        if source_version is None:
            try:
                source_version = importlib.metadata.version(module_name.split(".")[0])
            except importlib.metadata.PackageNotFoundError:
                source_version = "UNKNOWN"
        identity = BuildIdentity(
            factory_ref=factory_ref,
            module_sha256=_file_sha256(source_path),
            dependency_lock_sha256=dependency_hash,
            config_sha256=_mapping_sha256(config),
            source_version=str(source_version),
        )
        instance.attach_build_identity(identity)
        return instance


def _file_sha256(path: Path | None) -> str:
    if path is None or not path.is_file():
        return "UNKNOWN"
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mapping_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
