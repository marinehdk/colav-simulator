"""3D metadata and run-bound ENC image retain the existing session authority."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from gui_server import main as gui


def test_enc_metadata_declares_horizontal_crs_and_visual_height():
    manager = gui.WebSessionManager.__new__(gui.WebSessionManager)
    manager.prepared = SimpleNamespace(
        manifest=SimpleNamespace(run_id="run-a"),
        session=SimpleNamespace(enc=SimpleNamespace(origin=(39000, 6956450), size=(6000, 6000), utm_zone=33)),
    )
    info = manager.enc_info()
    assert info["run_id"] == "run-a"
    assert info["horizontal_crs"] == "EPSG:25833"
    assert info["hemisphere"] == "north"
    assert info["display_height_reference"] == "ellipsoid-zero-visual-only"
    manager.prepared.session.enc.utm_zone = 99
    assert manager.enc_info()["horizontal_crs"] is None


def test_late_enc_image_request_cannot_read_another_sessions_chart(monkeypatch, tmp_path):
    monkeypatch.setattr(gui, "manager", SimpleNamespace(session_id="new-run", prepared=SimpleNamespace(run_dir=tmp_path)))
    with pytest.raises(HTTPException) as error:
        gui.api_enc_tile("old-run")
    assert error.value.status_code == 409
    assert gui.api_enc_tile("new-run").path == tmp_path / "enc.png"
    assert gui.api_enc_tile().path == tmp_path / "enc.png"
