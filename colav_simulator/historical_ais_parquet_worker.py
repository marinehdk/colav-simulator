"""Process-isolated Parquet reader for historical AIS ingestion."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from colav_simulator.historical_ais import (
    HistoricalAISSelection,
    _read_parquet_rows_in_process,
    _worker_encode,
)


def main(argv: list[str] | None = None) -> int:
    """Read one Parquet entry and write its stdlib response document."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        raise SystemExit("usage: historical_ais_parquet_worker REQUEST_JSON RESPONSE_JSON")
    request_path, response_path = (Path(item) for item in args)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    selection_payload: dict[str, Any] = dict(request["selection"])
    selection = HistoricalAISSelection(**selection_payload)
    rows, schema = _read_parquet_rows_in_process(Path(request["path"]), selection)
    response = {"rows": [_worker_encode(row) for row in rows], "schema": schema}
    response_path.write_text(
        json.dumps(response, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
