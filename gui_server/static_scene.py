"""Static geographic context, separate from validation Session Authority."""

import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

DATA = Path(__file__).resolve().parents[1] / "colav_simulator/data/qingdao_static"
router = APIRouter(prefix="/api/geography/qingdao", tags=["geography"])


@router.get("")
def descriptor() -> dict:
    """Publish chart and landscape coordinates without vessels or execution."""
    source = json.loads((DATA / "region.json").read_text())
    size = source["size_m"]
    return {
        "ready": True,
        "run_id": "geography-qingdao",
        "region_id": "qingdao",
        "scene_mode": "GEOGRAPHIC_STATIC",
        "horizontal_crs": source["crs"],
        "utm_zone": 51,
        "hemisphere": "north",
        "display_height_reference": "ellipsoid-zero-visual-only",
        "origin_e": source["origin_e"] - size / 2,
        "origin_n": source["origin_n"] - size / 2,
        "width": size,
        "height": size,
        "tile_url": "/api/geography/qingdao/chart.png",
        "source": source["source"],
    }


@router.get("/chart.png")
def chart_image() -> FileResponse:
    """Plain ENC colours, matching the existing Config and Deployment chart."""
    return FileResponse(DATA / "chart.png", media_type="image/png")
