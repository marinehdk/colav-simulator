"""Large sealed traces must retain indexed reads without repeated gzip work."""

import gzip
import json
from unittest.mock import patch

from colav_simulator.decision_replay import bundle as module


def test_large_trace_random_windows_decode_once(tmp_path, monkeypatch):
    trace = tmp_path / "decision"
    trace.mkdir()
    records = [{"sequence": i + 1, "sim_time": i / 10, "payload": {"text": "x" * 200}} for i in range(50)]
    body = b"".join(json.dumps(row).encode() + b"\n" for row in records)
    (trace / "frames.jsonl.gz").write_bytes(gzip.compress(body))
    monkeypatch.setattr(module, "MAX_DECODED_TRACE_BYTES", 1024)
    bundle = module.TraceBundle(tmp_path)
    with patch.object(module.gzip, "open", wraps=gzip.open) as opened:
        assert bundle.window(3, 3.4) == records[30:35]
        assert bundle.window(1, 1.3) == records[10:14]
        assert bundle.frame(50) == records[49]
        assert opened.call_count == 1, "each window/frame must reuse the decoded seek index"
