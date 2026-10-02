"""Mast camera calibration table + pixel-box georef (P3-S2, spec #90).

Backend-authoritative single copy of the FCB45 mast sensor family
(``milliampere-ch5-fcb45-layout.md`` §4.2 placement table, FBX-measured mast
anchor: air draught 12.98 m, mast at x = +2.1 m forward of midship). The Unity
mast rig (`sango/Assets/Scripts/Runtime/Vessels/Mast/MastCameraTable.cs`)
mirrors these constants; the parity test
``tests/test_observations_endpoint.py`` pins both tables to the same literals
(edit any side only together with the other and this doc).

Conventions (frozen for v1):
- ``azimuth_deg``: relative bearing from the bow, compass-clockwise (0 = bow,
  90 = starboard beam, 180 = stern, 270 = port beam).
- Ship frame for Unity locals: +z forward (bow), +x starboard, +y up, origin at
  the waterline on midship (FCB45 FBX origin convention).
- Camera model: pinhole, square pixels, ``fx = (width / 2) / tan(HFOV / 2)``,
  optical axis at the mount azimuth (level, no pitch/roll in v1 — flat-sea
  convention shared with the sensor-model-v1 generator).
- Georef (contract observations-v1.md §5, backend-side): bearing from the pixel
  x-center, range from the box pixel height against a per-class target height
  prior above the waterline (milliAmpere camera-above-sea ranging), then NE =
  ownship + range * (cos bearing, sin bearing). Covariance is the bearing-frame
  polar sigma rotated into NE (radially elongated, sensor-model-v1 §3 E5 form).

Layout deviation note (S2, documented): the task layout is "EO x5 (bow ±60 deg
forward pair + beams 90/270 + stern 180), IR x4 (bow/port/stbd/stern), PTZ dual
spectrum facing forward". The EO ring therefore has no mount at exactly 0 deg —
the forward-looking EO role is the PTZ white channel (milliAmpere rationale:
"the forward role is covered by the PTZ tele channel"). The default detection
feed mount is ``mast_ptz_eo`` (0 deg, forward). With 90 deg HFOV ring mounts the
ring covers 15-345 deg; the dead-ahead 30 deg sector is the PTZ's own coverage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: observation frame sensor_id vocabulary (contract observations-v1.md §2).
SENSOR_ID_EO = 2
SENSOR_ID_IR = 3

#: 2 nautical miles in metres (external-camera default max range).
DEFAULT_MAX_RANGE_M = 2.0 * 1852.0

#: Per-class target height above the waterline prior (metres) used by the
#: box-height ranging. COCO "boat" (the YOLO filter class) boxes span
#: roughly waterline-to-superstructure on the rendered fleet.
CLASS_HEIGHT_PRIOR_M: dict[str, float] = {"boat": 2.5}
DEFAULT_HEIGHT_PRIOR_M = 5.0

#: Range clamp of the box-height ranging (a 2.5 m prior cannot be trusted past
#: the horizon of the small-target geometry; below this the box is essentially
#: at the own hull).
MIN_RANGE_M = 5.0

#: Default FramePublisher feed mount (forward EO = PTZ white channel) and its
#: published raster (FramePublisher.overrideCaptureSize when the rig owns the feed).
FEED_MOUNT_ID = "mast_ptz_eo"
FEED_WIDTH_PX = 640
FEED_HEIGHT_PX = 480

#: 1-sigma pixel quantization of the box center column (bearing) and of the box
#: height (range) driving the georeferenced covariance. The bearing sigma is
#: floored at 1 deg (mount alignment + ownship heading uncertainty budget) and
#: the cross-range sigma at 2 m (height-prior uncertainty projects laterally).
BEARING_SIGMA_PX = 2.0
BEARING_SIGMA_FLOOR_RAD = math.radians(1.0)
RANGE_RELATIVE_SIGMA = 0.15
RANGE_MIN_SIGMA_M = 2.0
CROSS_RANGE_MIN_SIGMA_M = 2.0


@dataclass(frozen=True)
class MastMount:
    """One mast sensor mount (calibration table row; sensor-model-v1 §3 mount_id)."""

    mount_id: str
    sensor_id: int  # 2 = camera_eo, 3 = camera_ir (contract observations-v1 §2)
    channel: str  # "camera_eo" | "camera_ir" (sensor-model-v1 §2 label)
    azimuth_deg: float  # relative bearing from bow, compass-clockwise
    hfov_deg: float  # horizontal field of view (FOV "档" per milliampere §4.2)
    reference_width_px: int  # reference raster for the intrinsics (fx scales with the actual frame)
    reference_height_px: int
    height_m: float  # above the waterline (mast rail 10.5, PTZ bracket 11.5)
    forward_offset_m: float  # + forward of midship (mast at +2.1, PTZ bracket +2.5)
    starboard_offset_m: float = 0.0  # all mounts sit on the mast centerline
    published_width_px: int = 0  # raster the Unity publisher emits (0 = reference)
    published_height_px: int = 0

    @property
    def fx_reference_px(self) -> float:
        """Reference focal length in pixels (square pixels; scales with frame width)."""
        return focal_px(self.hfov_deg, self.reference_width_px)

    @property
    def frame_width_px(self) -> int:
        """Width of the actually published frames (georef pixel domain)."""
        return self.published_width_px or self.reference_width_px

    @property
    def frame_height_px(self) -> int:
        """Height of the actually published frames (georef pixel domain)."""
        return self.published_height_px or self.reference_height_px


def focal_px(hfov_deg: float, width_px: float) -> float:
    """Pinhole focal length in pixels from a horizontal FOV (square pixels)."""
    return (width_px / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)


def _eo(mount_id: str, azimuth_deg: float) -> MastMount:
    return MastMount(
        mount_id=mount_id,
        sensor_id=SENSOR_ID_EO,
        channel="camera_eo",
        azimuth_deg=azimuth_deg,
        hfov_deg=90.0,
        reference_width_px=1920,
        reference_height_px=1080,
        height_m=10.5,
        forward_offset_m=2.1,
    )


def _ir(mount_id: str, azimuth_deg: float) -> MastMount:
    return MastMount(
        mount_id=mount_id,
        sensor_id=SENSOR_ID_IR,
        channel="camera_ir",
        azimuth_deg=azimuth_deg,
        hfov_deg=90.0,
        reference_width_px=640,
        reference_height_px=512,
        height_m=10.5,
        forward_offset_m=2.1,
    )


#: EO ring x5 (task layout: bow +-60 deg forward pair, beams 90/270, stern 180).
_EO_BOW_STBD = _eo("mast_eo_bow_stbd", 60.0)
_EO_BOW_PORT = _eo("mast_eo_bow_port", 300.0)
_EO_STBD = _eo("mast_eo_stbd", 90.0)
_EO_PORT = _eo("mast_eo_port", 270.0)
_EO_QUARTER = _eo("mast_eo_quarter", 180.0)

#: IR ring x4 (milliampere §4.2: bow 0 / port 90 left / stbd 270 right / stern 180).
_IR_BOW = _ir("mast_ir_bow", 0.0)
_IR_STBD = _ir("mast_ir_stbd", 90.0)
_IR_PORT = _ir("mast_ir_port", 270.0)
_IR_QUARTER = _ir("mast_ir_quarter", 180.0)

#: Dual-spectrum PTZ (milliampere §4.2: mast-top forward bracket, fixed mount in
#: S2; pan/tilt control is out of segment). The white channel doubles as the
#: default detection feed mount (forward-looking EO role).
_PTZ_EO = MastMount(
    mount_id="mast_ptz_eo",
    sensor_id=SENSOR_ID_EO,
    channel="camera_eo",
    azimuth_deg=0.0,
    hfov_deg=60.0,
    reference_width_px=1920,
    reference_height_px=1080,
    height_m=11.5,
    forward_offset_m=2.5,
    published_width_px=FEED_WIDTH_PX,
    published_height_px=FEED_HEIGHT_PX,
)
_PTZ_IR = MastMount(
    mount_id="mast_ptz_ir",
    sensor_id=SENSOR_ID_IR,
    channel="camera_ir",
    azimuth_deg=0.0,
    hfov_deg=45.0,
    reference_width_px=640,
    reference_height_px=512,
    height_m=11.5,
    forward_offset_m=2.5,
)

#: The whole family (EO x5 + IR x4 + PTZ dual x2 = 11 calibration rows).
MAST_MOUNTS: tuple[MastMount, ...] = (
    _EO_BOW_STBD,
    _EO_BOW_PORT,
    _EO_STBD,
    _EO_PORT,
    _EO_QUARTER,
    _IR_BOW,
    _IR_STBD,
    _IR_PORT,
    _IR_QUARTER,
    _PTZ_EO,
    _PTZ_IR,
)

MAST_MOUNTS_BY_ID: dict[str, MastMount] = {mount.mount_id: mount for mount in MAST_MOUNTS}


@dataclass(frozen=True)
class GeoreferencedDetection:
    """One pixel box resolved to ownship-NED NE (sensor-model-v1 measurement)."""

    north_m: float
    east_m: float
    range_m: float
    bearing_rad: float  # world bearing from north, compass-clockwise (NE atan2 domain)
    cov_ne_m2: tuple[tuple[float, float], tuple[float, float]]
    target_height_m: float


def georeference_box(
    mount: MastMount,
    box_xyxy: tuple[float, float, float, float],
    frame_width: int,
    frame_height: int,  # noqa: ARG001 - symmetric with the FrameMetadata raster pair
    own_north: float,
    own_east: float,
    own_yaw_rad: float,
    *,
    class_name: str | None = None,
    target_height_m: float | None = None,
    max_range_m: float = DEFAULT_MAX_RANGE_M,
) -> GeoreferencedDetection:
    """Pixel box -> NE centre + radial covariance (pure; contract observations-v1 §5).

    Bearing: pixel column of the box centre through the pinhole model. Range:
    box pixel height against the target height prior (milliAmpere
    camera-above-sea ranging: ``range = fx * H / h_px``). NE covariance is the
    bearing-frame polar sigma rotated into NE (radially elongated).
    """
    x0, y0, x1, y1 = (float(value) for value in box_xyxy)
    fx = focal_px(mount.hfov_deg, frame_width)
    u_center = 0.5 * (x0 + x1)
    box_height_px = max(y1 - y0, 1.0)

    height_prior = target_height_m
    if height_prior is None:
        height_prior = CLASS_HEIGHT_PRIOR_M.get(class_name or "", DEFAULT_HEIGHT_PRIOR_M)
    range_m = float(min(max(fx * height_prior / box_height_px, MIN_RANGE_M), max_range_m))

    bearing_offset = math.atan((u_center - frame_width / 2.0) / fx)
    bearing = own_yaw_rad + math.radians(mount.azimuth_deg) + bearing_offset

    north = own_north + range_m * math.cos(bearing)
    east = own_east + range_m * math.sin(bearing)

    sigma_range = max(RANGE_RELATIVE_SIGMA * range_m, RANGE_MIN_SIGMA_M)
    sigma_cross = max(range_m * max(BEARING_SIGMA_PX / fx, BEARING_SIGMA_FLOOR_RAD), CROSS_RANGE_MIN_SIGMA_M)
    cos_b = math.cos(bearing)
    sin_b = math.sin(bearing)
    # Radial axis along (cos b, sin b), cross axis perpendicular; R diag(sigmas) R^T.
    cov = (
        (
            sigma_range**2 * cos_b * cos_b + sigma_cross**2 * sin_b * sin_b,
            (sigma_range**2 - sigma_cross**2) * cos_b * sin_b,
        ),
        (
            (sigma_range**2 - sigma_cross**2) * cos_b * sin_b,
            sigma_range**2 * sin_b * sin_b + sigma_cross**2 * cos_b * cos_b,
        ),
    )
    return GeoreferencedDetection(
        north_m=north,
        east_m=east,
        range_m=range_m,
        bearing_rad=bearing % (2.0 * math.pi),
        cov_ne_m2=cov,
        target_height_m=float(height_prior),
    )
