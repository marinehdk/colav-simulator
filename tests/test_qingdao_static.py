"""Qingdao geographic inspection has no fleet or validation execution."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from pyproj import Transformer

from colav_simulator.experiment.contracts import SessionState
from gui_server.main import api_create_qingdao_static, manager
from gui_server.static_scene import DATA, descriptor, router


def test_geographic_context_is_vessel_free_and_uses_the_real_qingdao_grid():
    info = descriptor()
    assert info["scene_mode"] == "GEOGRAPHIC_STATIC"
    assert info["horizontal_crs"] == "EPSG:32651"
    lon, lat = Transformer.from_crs(32651, 4326, always_xy=True).transform(
        info["origin_e"] + info["width"] / 2, info["origin_n"] + info["height"] / 2
    )
    assert abs(lon - 120.295) < 0.00001
    assert abs(lat - 36.045) < 0.00001
    assert not {"ships", "observations", "time", "algorithm_id"}.intersection(info)
    assert not (DATA / "fleet.json").exists()


def test_enc_preview_is_bundled_and_has_the_existing_land_water_palette():
    image = Image.open(DATA / "chart.png").convert("RGB")
    colours = {tuple(pixel) for pixel in image.getdata()}
    assert (105, 116, 95) in colours
    assert (142, 187, 197) in colours


def test_geography_api_has_no_ais_frame_or_timeline():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get("/api/geography/qingdao").json()["ready"]
    assert client.get("/api/geography/qingdao/chart.png").headers["content-type"] == "image/png"
    assert client.get("/api/geography/qingdao/frame").status_code == 404


def test_create_geography_preserves_existing_session_authority(monkeypatch):
    active = SimpleNamespace(session=SimpleNamespace(state=SessionState.CREATED))
    monkeypatch.setattr(manager, "prepared", active)
    assert api_create_qingdao_static()["region_id"] == "qingdao"
    assert manager.prepared is active


def test_running_session_blocks_geographic_create(monkeypatch):
    monkeypatch.setattr(manager, "prepared", SimpleNamespace(session=SimpleNamespace(state=SessionState.RUNNING)))
    with pytest.raises(HTTPException) as error:
        api_create_qingdao_static()
    assert error.value.status_code == 409
