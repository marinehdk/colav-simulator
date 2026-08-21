from __future__ import annotations

import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc


def test_runner_import_after_map_stack_does_not_load_pyarrow() -> None:
    """Normal runtime imports must stay clear of Arrow's native dataset extension."""
    project_root = Path(__file__).resolve().parents[1]
    code = """
import fiona
import pyproj
from osgeo import osr
import shapely

from colav_simulator.experiment.runner import ExperimentRunner
from gui_server import main as gui_main

assert ExperimentRunner is not None
assert gui_main.app is not None
assert "pyarrow.dataset" not in sys.modules
print("runner-import-ok")
"""

    result = subprocess.run(
        [sys.executable, "-c", "import sys; " + code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip() == "runner-import-ok"


def test_zip_parquet_read_after_map_stack_uses_isolated_dataset_worker(tmp_path: Path) -> None:
    """Parquet ingestion remains usable after GIS native libraries are loaded."""
    parquet_path = tmp_path / "hais_2026-07-01.snappy.parquet"
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import pyarrow as pa; import pyarrow.parquet as pq; "
                "pq.write_table(pa.table({'date_time_utc': pa.array([__import__('datetime').datetime(2026, 7, 1)]), "
                "'mmsi': pa.array([123456789]), 'longitude': pa.array([7.1]), "
                "'latitude': pa.array([62.0]), 'speed_over_ground': pa.array([10.0]), "
                "'course_over_ground': pa.array([90.0])}), sys.argv[1])"
            ),
            str(parquet_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    archive_path = tmp_path / "hais.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(parquet_path, parquet_path.name)

    import fiona  # noqa: F401, PLC0415
    import pyproj  # noqa: F401, PLC0415
    import shapely  # noqa: PLC0415, F401
    from osgeo import osr  # noqa: PLC0415, F401

    from colav_simulator.historical_ais import (  # noqa: PLC0415
        HistoricalAISDatasetReader,
        HistoricalAISSelection,
    )

    result = HistoricalAISDatasetReader(archive_path).read(
        HistoricalAISSelection(
            start_utc=datetime(2026, 7, 1, tzinfo=UTC),
            end_utc=datetime(2026, 7, 2, tzinfo=UTC),
            bbox=(7.0, 61.0, 8.0, 63.0),
        )
    )

    assert result.descriptor.entries == (parquet_path.name,)
    assert len(result.observations) == 1
    assert result.observations[0].normalized.mmsi == 123456789
    assert "pyarrow.dataset" not in sys.modules


def test_historical_contract_modules_are_python310_enum_compatible() -> None:
    project_root = Path(__file__).resolve().parents[1]
    modules = (
        "historical_acceptance.py",
        "historical_case.py",
        "historical_compare.py",
        "historical_counterfactual.py",
        "historical_replay.py",
    )

    for module in modules:
        source = (project_root / "colav_simulator" / module).read_text(encoding="utf-8")
        assert "StrEnum" not in source, module
