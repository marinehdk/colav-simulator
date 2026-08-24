"""Explicit, fail-closed source binding for bounded Historical AIS scenes."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

HAIS_ARCHIVE_ENV_VAR = "COLAV_HAIS_ARCHIVE_PATH"


class HistoricalAISScenarioReadiness(str, Enum):
    """Typed scene-source readiness."""

    READY = "READY"
    SOURCE_BINDING_MISSING = "SOURCE_BINDING_MISSING"
    SOURCE_BINDING_NOT_FOUND = "SOURCE_BINDING_NOT_FOUND"
    SOURCE_ARCHIVE_UNREADABLE = "SOURCE_ARCHIVE_UNREADABLE"
    SOURCE_ARCHIVE_DIGEST_MISMATCH = "SOURCE_ARCHIVE_DIGEST_MISMATCH"
    DATASET_IDENTITY_MISMATCH = "DATASET_IDENTITY_MISMATCH"
    ENC_IDENTITY_MISMATCH = "ENC_IDENTITY_MISMATCH"
    CASE_BUILD_FAILED = "CASE_BUILD_FAILED"


class HistoricalAISScenarioError(ValueError):
    """Fail-closed scene error with machine-readable status."""

    def __init__(self, status: HistoricalAISScenarioReadiness | str, reason: str) -> None:
        super().__init__(reason)
        self.status = HistoricalAISScenarioReadiness(status)

    def detail(self) -> dict[str, Any]:
        return {"status": self.status.value, "reason": str(self)}


@dataclass(frozen=True)
class HistoricalAISScenarioSourceReadiness:
    """Public readiness evidence that never exposes the configured local path."""

    status: HistoricalAISScenarioReadiness
    expected_archive_sha256: str
    observed_archive_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "env_var": HAIS_ARCHIVE_ENV_VAR,
            "expected_archive_sha256": self.expected_archive_sha256,
            "observed_archive_sha256": self.observed_archive_sha256,
        }


class SceneSourceDescriptor(Protocol):
    """Minimal descriptor contract needed by the source binder."""

    archive_sha256: str


class HistoricalAISSceneSourceBinder:
    """Resolve and content-verify one external archive binding."""

    @staticmethod
    def readiness(
        descriptor: SceneSourceDescriptor,
        environ: Mapping[str, str] | None = None,
    ) -> HistoricalAISScenarioSourceReadiness:
        environ = os.environ if environ is None else environ
        raw_path = str(environ.get(HAIS_ARCHIVE_ENV_VAR, "")).strip()
        if not raw_path:
            return HistoricalAISScenarioSourceReadiness(
                HistoricalAISScenarioReadiness.SOURCE_BINDING_MISSING,
                descriptor.archive_sha256,
            )
        source = Path(raw_path).expanduser()
        if not source.is_file():
            return HistoricalAISScenarioSourceReadiness(
                HistoricalAISScenarioReadiness.SOURCE_BINDING_NOT_FOUND,
                descriptor.archive_sha256,
            )
        try:
            observed = _sha256_file(source)
        except OSError:
            return HistoricalAISScenarioSourceReadiness(
                HistoricalAISScenarioReadiness.SOURCE_ARCHIVE_UNREADABLE,
                descriptor.archive_sha256,
            )
        return HistoricalAISScenarioSourceReadiness(
            HistoricalAISScenarioReadiness.READY
            if observed == descriptor.archive_sha256
            else HistoricalAISScenarioReadiness.SOURCE_ARCHIVE_DIGEST_MISMATCH,
            descriptor.archive_sha256,
            observed,
        )

    @classmethod
    def require_source(
        cls,
        descriptor: SceneSourceDescriptor,
        environ: Mapping[str, str] | None = None,
    ) -> Path:
        environ = os.environ if environ is None else environ
        raw_path = str(environ.get(HAIS_ARCHIVE_ENV_VAR, "")).strip()
        readiness = cls.readiness(descriptor, environ)
        if readiness.status is not HistoricalAISScenarioReadiness.READY:
            raise HistoricalAISScenarioError(readiness.status, _readiness_reason(readiness))
        return Path(raw_path).expanduser().resolve()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _readiness_reason(readiness: HistoricalAISScenarioSourceReadiness) -> str:
    reasons = {
        HistoricalAISScenarioReadiness.SOURCE_BINDING_MISSING: f"{HAIS_ARCHIVE_ENV_VAR} is not configured",
        HistoricalAISScenarioReadiness.SOURCE_BINDING_NOT_FOUND: (
            f"{HAIS_ARCHIVE_ENV_VAR} does not point to a readable archive"
        ),
        HistoricalAISScenarioReadiness.SOURCE_ARCHIVE_UNREADABLE: (
            f"Historical AIS archive bound by {HAIS_ARCHIVE_ENV_VAR} is unreadable"
        ),
        HistoricalAISScenarioReadiness.SOURCE_ARCHIVE_DIGEST_MISMATCH: (
            "Historical AIS archive digest does not match the published scene descriptor"
        ),
    }
    return reasons.get(readiness.status, "Historical AIS source binding is unavailable")


__all__ = [
    "HAIS_ARCHIVE_ENV_VAR",
    "HistoricalAISScenarioError",
    "HistoricalAISScenarioReadiness",
    "HistoricalAISScenarioSourceReadiness",
    "HistoricalAISSceneSourceBinder",
]
