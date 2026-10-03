"""sensing.py.

Summary:
Contains class definitions for various sensors.
Every sensor must adhere to the ISensor interface.

Author: Trym Tengesdal, Ragnar Wien
"""

import threading
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from math import radians

import numpy as np
from scipy.special import erfc

import colav_simulator.common.config_parsing as cp
import colav_simulator.common.math_functions as mf
from colav_simulator.core.mast_cameras import MAST_MOUNTS_BY_ID
from colav_simulator.core.radar_occlusion import TerrainGrid, load_occlusion_grid


class ISensor(ABC):
    #: sensor-model-v1 §1 bypass mark: bypass channels (lidar/ais per contract §2)
    #: ride the measurement cache for display/fusion-adjacent consumers but never
    #: update the KF main chain (the tracker skips them). Fusing sensors stay False.
    bypass_fusion: bool = False

    @abstractmethod
    def R(self, xs: np.ndarray) -> np.ndarray:
        """Returns the measurement noise covariance matrix for the input state."""

    @abstractmethod
    def H(self, xs: np.ndarray) -> np.ndarray:
        """Returns the measurement matrix for the input state."""

    @abstractmethod
    def h(self, xs: np.ndarray) -> np.ndarray:
        """Returns the measurement function for the input state."""

    @abstractmethod
    def reset(self, seed: int | None) -> None:
        """Resets the sensor to its initial state, optionally seeding the rng for measurement generation."""

    @abstractmethod
    def seed(self, seed: int | None) -> None:
        """Sets the seed for the sensor's random number generator."""

    @abstractmethod
    def generate_measurements(
        self, t: float, true_do_states: list[tuple[int, np.ndarray, float, float]], ownship_state: np.ndarray
    ) -> list[tuple[int, np.ndarray]]:
        """Generates sensor measurements from the input tuple list of true dynamic obstacle info.

        Takes (do_idx, do_state, do_length, do_width) x n_do, and own-ship state.

        Args:
            t (float): Current time.
            true_do_states (list[tuple[int, np.ndarray, float, float]]): List of tuples
                containing the dynamic obstacle index, state, length, and width.
            ownship_state (np.ndarray): Own-ship state vector.

        Returns:
            list[tuple[int, np.ndarray]]: List of tuples containing the dynamic obstacle
                index and the measurement.
        """


@dataclass
class RadarParams:
    """Configuration parameters for a radar sensor."""

    max_range: float = 1000.0
    measurement_rate: float = 1.0
    R_ne: np.ndarray = field(default_factory=lambda: np.diag([5.0**2, 5.0**2]))  # north-east meas cov used by the tracker
    R_ne_true: np.ndarray = field(
        default_factory=lambda: np.diag([5.0**2, 5.0**2])
    )  #  north-east meas cov that reflects the true noise characteristics. Used to generate measurements
    generate_clutter: bool = False
    clutter_cardinality_expectation: int = 5
    detection_probability: float = 0.9
    include_polar_meas_noise: bool = False
    R_polar_true: np.ndarray = field(default_factory=lambda: np.diag([8.0**2, ((np.pi / 180) * 1) ** 2]))  # meas cov

    @classmethod
    def from_dict(self, config_dict: dict) -> "RadarParams":  # noqa: D102
        return RadarParams(
            max_range=config_dict["max_range"],
            measurement_rate=config_dict["measurement_rate"],
            R_ne=np.diag(config_dict["R_ne"]),
            R_ne_true=np.diag(config_dict["R_ne_true"]),
            generate_clutter=config_dict["generate_clutter"],
            clutter_cardinality_expectation=config_dict["clutter_cardinality_expectation"],
            detection_probability=config_dict["detection_probability"],
            include_polar_meas_noise=config_dict["include_polar_meas_noise"],
            R_polar_true=np.diag(config_dict["R_polar_true"]),
        )

    def to_dict(self) -> dict:  # noqa: D102
        output_dict = asdict(self)
        output_dict["R_ne"] = self.R_ne.diagonal().tolist()
        output_dict["R_ne_true"] = self.R_ne_true.diagonal().tolist()
        output_dict["R_polar_true"] = self.R_polar_true.diagonal().tolist()
        return output_dict


class AISClass(Enum):
    """AIS class A and B transponder types."""

    A = 0
    B = 1


@dataclass
class AISParams:
    """AIS parameter class."""

    max_range: float = 5000.0
    ais_class: AISClass = AISClass.A
    R: np.ndarray = field(
        default_factory=lambda: np.diag([5.0**2, 5.0**2, 0.1**2, 0.08**2])
    )  # meas cov for a state vector of [x, y, Vx, Vy], used by the tracker
    R_true: np.ndarray = field(
        default_factory=lambda: np.diag([5.0**2, 5.0**2, 0.1**2, 0.08**2])
    )  # meas cov that reflects the true noise characteristics. Used to generate measurements

    @classmethod
    def from_dict(cls, config_dict: dict) -> "AISParams":  # noqa: D102
        return AISParams(
            max_range=config_dict["max_range"],
            ais_class=AISClass[config_dict["ais_class"]],
            R=np.diag(config_dict["R"]),
            R_true=np.diag(config_dict["R_true"]),
        )

    def to_dict(self) -> dict:  # noqa: D102
        output_dict = {
            "max_range": self.max_range,
            "ais_class": self.ais_class.name,
            "R": self.R.diagonal().tolist(),
            "R_true": self.R_true.diagonal().tolist(),
        }
        return output_dict


@dataclass
class Config:
    """Class for holding sensor(s) configuration parameters."""

    sensor_list: list = field(default_factory=lambda: [RadarParams()])

    def to_dict_list(self) -> list:
        output_list: list = []
        for sensor in self.sensor_list:
            sensor_dict = {}
            if isinstance(sensor, RadarParams):
                sensor_dict["radar"] = sensor.to_dict()
            elif isinstance(sensor, RadarXParams):
                sensor_dict["radar_x"] = sensor.to_dict()
            elif isinstance(sensor, AISParams):
                sensor_dict["ais"] = sensor.to_dict()
            elif isinstance(sensor, LidarParams):
                sensor_dict["lidar"] = sensor.to_dict()
            elif isinstance(sensor, ExternalCameraParams):
                # P1-1a review fix (spec #90): explicit scene assembly key
                # (radar_x precedent) — absent from a scene, no camera sensor
                # is built and the default tracker behaviour is untouched.
                sensor_dict["external_cameras"] = sensor.to_dict()
            output_list.append(sensor_dict)

        return output_list

    @classmethod
    def from_dict(cls, config_dict: dict) -> "Config":
        config = Config(sensor_list=[])
        for sensor_dict in config_dict:
            if "radar" in sensor_dict:
                config.sensor_list.append(cp.convert_settings_dict_to_dataclass(RadarParams, sensor_dict["radar"]))
            elif "radar_x" in sensor_dict:
                config.sensor_list.append(RadarXParams.from_dict(sensor_dict["radar_x"]))
            elif "ais" in sensor_dict:
                config.sensor_list.append(cp.convert_settings_dict_to_dataclass(AISParams, sensor_dict["ais"]))
            elif "lidar" in sensor_dict:
                config.sensor_list.append(LidarParams.from_dict(sensor_dict["lidar"]))
            elif "external_cameras" in sensor_dict:
                config.sensor_list.append(ExternalCameraParams.from_dict(sensor_dict["external_cameras"]))

        return config


class SensorSuiteBuilder:
    @classmethod
    def construct_sensors(cls, config: Config | None = None) -> list:
        """Builds a list of sensors from the configuration.

        Args:
            config (Optional[Config]): Configuration of ship sensors

        Returns:
            List[Sensor]: List of sensors.
        """
        if config:
            sensors: list = []
            for sensor_config in config.sensor_list:
                if isinstance(sensor_config, RadarParams):
                    sensors.append(Radar(sensor_config))
                elif isinstance(sensor_config, RadarXParams):
                    sensors.append(RadarXBand(sensor_config))
                elif isinstance(sensor_config, AISParams):
                    sensors.append(AIS(sensor_config))
                elif isinstance(sensor_config, LidarParams):
                    sensors.append(LidarContactSensor(sensor_config))
                elif isinstance(sensor_config, ExternalCameraParams):
                    sensors.append(ExternalCameraSensor(sensor_config))
        else:
            sensors = [Radar()]
        return sensors


class Radar(ISensor):
    """Implements functionality for a radar sensor."""

    def __init__(self, params: RadarParams = RadarParams()) -> None:
        self.type: str = "radar"
        self._H: np.ndarray = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])
        self._params: RadarParams = params
        self._prev_meas_time: float = 0.0
        self._initialized: bool = False
        self._rng: np.random.Generator = np.random.default_rng()

    def reset(self, seed: int | None) -> None:
        self.seed(seed)
        self._prev_meas_time = 0.0
        self._initialized = False

    def seed(self, seed: int) -> None:
        self._rng = np.random.default_rng(seed)

    def R(self, xs: np.ndarray) -> np.ndarray:  # noqa: ARG002
        return self._params.R_ne_true

    def H(self, xs: np.ndarray) -> np.ndarray:  # noqa: ARG002
        return self._H

    def h(self, xs: np.ndarray) -> np.ndarray:
        return self._H @ xs

    def generate_measurements(
        self, t: float, true_do_states: list[tuple[int, np.ndarray, float, float]], ownship_state: np.ndarray
    ) -> list[tuple[int, np.ndarray]]:
        measurements = []
        if not self._initialized or t < 0.0001:
            self._prev_meas_time = t
            self._initialized = True

        detection_probability = self._params.detection_probability if self._params.generate_clutter else 1.0

        if (t - self._prev_meas_time) < (1.0 / self._params.measurement_rate):
            return [(do_tup[0], np.nan * np.ones(2)) for do_tup in true_do_states]

        for _i, (do_idx, do_state, _do_length, _do_width) in enumerate(true_do_states):
            dist_ownship_to_do = np.sqrt((do_state[0] - ownship_state[0]) ** 2 + (do_state[1] - ownship_state[1]) ** 2)
            do_detection_check = self._rng.random()
            if dist_ownship_to_do <= self._params.max_range and do_detection_check <= detection_probability:
                cartesian_meas_noise = self._rng.multivariate_normal(np.zeros(2), self._params.R_ne_true)
                if self._params.include_polar_meas_noise:
                    angle_ownship_to_do = np.arctan2(do_state[1] - ownship_state[1], do_state[0] - ownship_state[0])
                    ownship_to_do_polar_coords = np.array([dist_ownship_to_do, angle_ownship_to_do])
                    polar_meas_noise = self._rng.multivariate_normal(np.zeros(2), self._params.R_polar_true)
                    distorted_ownship_to_do_polar_coords = ownship_to_do_polar_coords + polar_meas_noise
                    distorted_ownship_to_do_cart_coords = np.array(
                        [
                            ownship_state[0]
                            + distorted_ownship_to_do_polar_coords[0] * np.cos(distorted_ownship_to_do_polar_coords[1]),
                            ownship_state[1]
                            + distorted_ownship_to_do_polar_coords[0] * np.sin(distorted_ownship_to_do_polar_coords[1]),
                        ]
                    )  # Cartesian coords of dynamic obstacle distorted by polar measurement noise
                    polar_meas_noise_cart_coords = distorted_ownship_to_do_cart_coords - self.h(
                        do_state
                    )  # cartesian coords of polar measurement noise relative to dynamic obstacle
                    meas_noise = (
                        polar_meas_noise_cart_coords + cartesian_meas_noise
                    ) / 2  # Midpoint between cartesian and polar measurement noise in cartesian coords
                else:
                    meas_noise = cartesian_meas_noise

                z = self.h(do_state) + meas_noise
            else:
                z = np.nan * np.ones(2)
            measurements.append((do_idx, z))

        self._prev_meas_time = t
        z_clutter = self.generate_clutter(ownship_state)
        measurements.extend(z_clutter)
        return measurements

    def generate_clutter(self, ownship_state: np.ndarray) -> list[tuple[int, np.ndarray]]:
        """Generates clutter measurements around the ownship using a Poisson distribution.

        Args:
            ownship_state (np.ndarray): The ownship state vector on the form [x, y, Vx, Vy].

        Returns:
            List[Tuple[int, np.ndarray]]: List of clutter measurements with -1 as the index (non-existent dynamic obstacle).
        """
        clutter = []
        if not self._params.generate_clutter:
            return clutter

        cardinality = self._rng.poisson(self._params.clutter_cardinality_expectation, 1)
        r = self._params.max_range * np.sqrt(self._rng.uniform(0, 1, cardinality))
        theta = self._rng.uniform(0, 2 * np.pi, cardinality)
        x = r * np.cos(theta) + ownship_state[0]
        y = r * np.sin(theta) + ownship_state[1]
        for i in range(cardinality[0]):
            clutter.append((-1, np.array([x[i], y[i]])))
        return clutter

    @property
    def max_range(self) -> float:
        return self._params.max_range

    @property
    def params(self) -> RadarParams:
        return self._params


class AIS(ISensor):
    """Class for simulating AIS transponder measurements.

    AIS/VDES:
        Measurement rate depends on:
        Class A	Anchored / Moored	 Every 3 Minutes
        Class A	Sailing 0-14 knots	 Every 10 Seconds
        Class A	Sailing 14-23 knots	 Every 6 Seconds
        Class A	Sailing 0-14 knots and changing course	 Every 3.33 Seconds
        Class A	Sailing 14-23 knots and changing course	 Every 2 Seconds
        Class A	Sailing faster than 23 knots	 Every 2 Seconds
        Class A	Sailing faster than 23 knots and changing course	 Every 2 Seconds
        Class B	Stopped or sailing up to 2 knots	 Every 3 Minutes
        Class B	Sailing faster than 2 knots	 Every 30 Seconds

     R_realistic values from paper considering quantization effects
     https://link.springer.com/chapter/10.1007/978-3-319-55372-6_13#Sec14
    def R_realistic(self, x: np.ndarray):
        R_GNSS = np.diag([0.5, 0.5, 0.1, 0.1])**2
        R_v = np.diag([x[2]**2, x[3]**2, 0, 0])
        self._R = R_GNSS + (1/12)*R_v
    """

    type: str = "ais"
    _H: np.ndarray = np.eye(4)

    def __init__(self, params: AISParams = AISParams()) -> None:
        self._params: AISParams = params
        self._prev_meas_time: list = []
        self._initialized: bool = False
        self._rng: np.random.Generator = np.random.default_rng()

    def reset(self, seed: int | None) -> None:
        self.seed(seed)
        self._prev_meas_time = []
        self._initialized = False

    def seed(self, seed: int | None) -> None:
        self._rng = np.random.default_rng(seed)

    def R(self, xs: np.ndarray) -> np.ndarray:  # noqa: ARG002
        return self._params.R

    def H(self, xs: np.ndarray) -> np.ndarray:  # noqa: ARG002
        return self._H

    def h(self, xs: np.ndarray) -> np.ndarray:
        z = self._H @ xs
        return z

    def generate_measurements(
        self, t: float, true_do_states: list[tuple[int, np.ndarray, float, float]], ownship_state: np.ndarray
    ) -> list[tuple[int, np.ndarray]]:
        measurements = []
        if not self._initialized or t < 0.0001:
            self._prev_meas_time = [t] * len(true_do_states)
            self._initialized = True

        if len(true_do_states) > len(self._prev_meas_time):
            diff = len(true_do_states) - len(self._prev_meas_time)
            self._prev_meas_time.extend([t] * diff)

        for i, (do_idx, do_state, _, _) in enumerate(true_do_states):
            dist_ownship_to_do = np.sqrt((do_state[0] - ownship_state[0]) ** 2 + (do_state[1] - ownship_state[1]) ** 2)

            if (t - self._prev_meas_time[i]) >= (
                1.0 / self._measurement_rate(do_state)
            ) and dist_ownship_to_do <= self._params.max_range:
                z = self.h(do_state) + self._rng.multivariate_normal(np.zeros(4), self._params.R_true)
                self._prev_meas_time[i] = t
            else:
                z = np.nan * np.ones(4)
            measurements.append((do_idx, z))

        return measurements

    def _measurement_rate(self, xs: np.ndarray) -> float:
        """Returns the measurement rate for the input state.

        This depends on the input state's speed and AIS class (and also if the
        course is changing, but this is not considered here (yet)).

        Args:
            xs (np.ndarray): The state vector of the dynamic obstacle = [x, y, Vx, Vy].

        Returns:
            float: The measurement rate in Hz.
        """
        sog = mf.ms2knots(float(np.linalg.norm(xs[2:4])))
        rate = 1.0
        if self._params.ais_class == AISClass.A:
            if sog <= 0.001:
                rate = 1.0 / 180.0
            elif sog > 0.001 and sog <= 14.0:
                rate = 1.0 / 10.0
            elif sog > 14.0 and sog <= 23.0:
                rate = 1.0 / 6.0
            elif sog > 23.0:
                rate = 1.0 / 2.0
        elif self._params.ais_class == AISClass.B:
            if sog <= 2.0:
                rate = 1.0 / 180.0
            elif sog > 2.0:
                rate = 1.0 / 30.0
        return rate

    @property
    def max_range(self) -> float:
        return self._params.max_range

    @property
    def params(self) -> AISParams:
        return self._params


N_METERS_PER_NM = 1852.0
RANGE_SCALES_NM_DEFAULT = (0.75, 1.5, 3.0, 6.0, 12.0, 24.0)
MOUNT_ID_RADAR_X_DEFAULT = "mast_top_xband"
#: Marcum-Q erfc-domain approximation offset calibrated against Albersheim's
#: formula (SNR @ PD=0.9, Pfa=1e-4, single pulse ≈ 11.7 dB, ±0.2 dB accuracy).
PD_ERFC_OFFSET = 0.85


def detection_probability_swerling0(snr_db: float | np.ndarray, pfa: float = 1e-4) -> float | np.ndarray:
    """Single-pulse non-fluctuating (Swerling-0) detection probability from SNR.

    Power-detection approximation ``PD = 0.5 erfc(sqrt(-ln Pfa) - sqrt(SNR + c))``
    (c = 0.85), anchored to Albersheim's empirical formula at PD = 0.9. Pfa
    anchor follows the CCDF=1e-4 threshold-error convention of Angelliaume 2019
    (domain doc 02 §2.3/E7).

    Args:
        snr_db: Signal-to-noise ratio in dB (scalar or array).
        pfa: False-alarm probability anchor.

    Returns:
        Detection probability in [0, 1], same shape as ``snr_db``.
    """
    snr_lin = np.power(10.0, np.asarray(snr_db, dtype=float) / 10.0)
    pd = 0.5 * erfc(np.sqrt(-np.log(pfa)) - np.sqrt(snr_lin + PD_ERFC_OFFSET))
    return np.clip(pd, 0.0, 1.0)


@dataclass
class RadarXParams:
    """X-band radar spoke-radar parameters (P3-S1; defaults = milliampere-ch5 §5.1 table).

    Frozen anchors: scan period 2.5 s (24 rpm, contract sensor-model-v1 §4
    ``async_jitter``), VIMM noise sigma_r=8 m / sigma_theta=1 deg (§4 ``noise``),
    clutter 5e-7/m2 (§4 ``clutter``), antenna height 12 m and VBW 25 deg blind
    ring 54-68 m (milliampere-ch5 §4.3 coverage table).
    """

    spokes_per_revolution: int = 2048
    rpm: float = 24.0  # far-range mode; near-range 60 rpm => scan period 1.0 s
    range_scales_nm: tuple = RANGE_SCALES_NM_DEFAULT
    range_scale_nm: float = 6.0
    antenna_height_m: float = 12.0  # parameterized 8/10/12 m (milliampere-ch5 §4.2)
    vbw_deg: float = 25.0  # vertical beam width; near blind ring = h / tan(VBW/2)
    blind_sectors_deg: tuple = ()  # ((center_rel_bow_deg, half_width_deg), ...) mast/rigging shadows
    mount_id: str = MOUNT_ID_RADAR_X_DEFAULT  # sensor-model-v1 §3 mount vocabulary
    # VIMM calibrated measurement noise (sensor-model-v1 §4), polar form.
    sigma_range_m: float = 8.0
    sigma_azimuth_rad: float = radians(1.0)
    # Power detection: PD(SNR) Swerling-0 approximation (Pfa per Angelliaume E7).
    pfa: float = 1e-4
    snr_ref_db: float = 13.0  # SNR of rcs_ref at snr_ref_range_m
    snr_ref_range_m: float = 5556.0  # 3 nm reference
    rcs_ref_m2: float = 10.0
    snr_decay_db_per_decade: float = 40.0  # point-target r^4 (20 log10 r^2)
    rcs_area_factor: float = 0.5  # rcs_m2 ~= length * width * factor
    rcs_min_m2: float = 1.0
    target_height_per_length: float = 0.12  # scattering-center height estimate
    target_height_min_m: float = 2.0
    target_height_max_m: float = 35.0
    # Async scan defects (contract §4 async_jitter): beam-crossing refresh + random drop.
    drop_probability: float = 0.0
    # Sea clutter (He 2024 parameterized point model, domain doc 02 §2.3/§5 row 2).
    clutter_rate_per_m2: float = 5e-7  # contract §4 VIMM anchor
    clutter_range_decay: float = 2.0  # lambda(r) ~ (r_ref / r)^decay (near-range dominance)
    clutter_ref_range_m: float = 1000.0
    sea_state_beaufort: float = 3.0  # scenario environment coupling (Beaufort)
    clutter_db_per_beaufort: float = 3.0  # sea-state intensity factor
    clutter_texture_nu_ref: float = 4.0  # compound texture shape at Beaufort 3
    clutter_snr_ref_db: float = 5.0  # amplitude-to-equivalent-SNR offset for confidence
    max_measurements_per_scan: int = 400  # per-scan output cap (targets prioritized)
    # Terrain occlusion: M6 strait DEM (EPSG:32648) or any projected GeoTIFF.
    occlusion_dem_path: str | None = None
    occlusion_mode: str = "elevation"  # "elevation" | "landmask"
    occlusion_downsample: int = 4
    occlusion_grid: TerrainGrid | None = None  # preloaded grid overrides the path

    def __post_init__(self) -> None:  # noqa: D105 (dataclass validation hook)
        if self.range_scale_nm not in self.range_scales_nm:
            msg = f"range_scale_nm {self.range_scale_nm} must be one of {self.range_scales_nm}"
            raise ValueError(msg)
        if self.occlusion_mode not in {"elevation", "landmask"}:
            msg = f"occlusion_mode must be 'elevation' or 'landmask', got {self.occlusion_mode!r}"
            raise ValueError(msg)

    @classmethod
    def from_dict(cls, config_dict: dict) -> "RadarXParams":
        known = {f: config_dict[f] for f in cls.__dataclass_fields__ if f in config_dict}
        if "range_scales_nm" in known:
            known["range_scales_nm"] = tuple(known["range_scales_nm"])
        if "blind_sectors_deg" in known:
            known["blind_sectors_deg"] = tuple(tuple(sector) for sector in known["blind_sectors_deg"])
        return cls(**known)

    def to_dict(self) -> dict:
        output_dict = asdict(self)
        output_dict.pop("occlusion_grid", None)
        output_dict["range_scales_nm"] = list(self.range_scales_nm)
        output_dict["blind_sectors_deg"] = [list(sector) for sector in self.blind_sectors_deg]
        return output_dict


class RadarXBand(ISensor):
    """X-band spoke radar model (P3-S1, sensor-model-v1 sensor_id=1 ``radar_x``).

    Physical effects (milliampere-ch5 §5.1 + domain doc 02 §5 minimal set):
    - asynchronous beam-crossing sampling: a target yields a measurement only on
      the antenna revolution that sweeps its bearing (scan period 60/rpm);
    - power detection PD(SNR) with a range-equation SNR model and per-class RCS
      estimate from ship dimensions;
    - vertical-beam near blind ring R_min = h_ant / tan(VBW/2) and configurable
      mast/rigging blind sectors (relative to bow);
    - radar horizon d = 4.12 (sqrt(h_ant) + sqrt(h_tgt)) [m] with k = 4/3;
    - terrain line-of-sight occlusion against the M6 strait DEM (blocked =>
      no measurement);
    - sea clutter as a Poisson point process over the (blind-ring, range-scale)
      annulus with He 2024-parameterized intensity (range decay, Beaufort sea
      state, compound texture) and per-scan cardinality cap.

    Legacy compatibility: ``generate_measurements`` returns the ISensor
    ``list[(do_idx, z)]`` shape with 2-D NE measurements (NaN placeholders when
    the beam has not swept the target), clutter marked do_idx=-1 — directly
    consumable by the existing KF/GodTracker measurement cache. The
    sensor-model-v1 frame is available via :meth:`generate_sfd_frame`.
    """

    def __init__(self, params: RadarXParams | None = None) -> None:
        self.type: str = "radar_x"
        self._params: RadarXParams = params if params is not None else RadarXParams()
        self._H: np.ndarray = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])
        self._rng: np.random.Generator = np.random.default_rng()
        self._seed: int | None = None
        self._prev_t: float = 0.0
        self._initialized: bool = False
        self._occlusion_grid: TerrainGrid | None = self._params.occlusion_grid
        self._occlusion_resolved: bool = self._params.occlusion_grid is not None
        r_mid = 0.5 * self.active_range_m
        cross_range_var = (r_mid * self._params.sigma_azimuth_rad) ** 2
        radial_var = self._params.sigma_range_m**2
        sigma2 = 0.5 * (radial_var + cross_range_var)
        self._R_ne: np.ndarray = np.diag([sigma2, sigma2])  # azimuth-averaged Jacobian projection

    # ------------------------------------------------------------------ ISensor
    def reset(self, seed: int | None) -> None:
        self.seed(seed)
        self._prev_t = 0.0
        self._initialized = False

    def seed(self, seed: int | None) -> None:
        self._seed = seed
        self._rng = np.random.default_rng(seed)

    def R(self, xs: np.ndarray) -> np.ndarray:  # noqa: ARG002
        return self._R_ne

    def H(self, xs: np.ndarray) -> np.ndarray:  # noqa: ARG002
        return self._H

    def h(self, xs: np.ndarray) -> np.ndarray:
        return self._H @ xs

    def generate_measurements(
        self, t: float, true_do_states: list[tuple[int, np.ndarray, float, float]], ownship_state: np.ndarray
    ) -> list[tuple[int, np.ndarray]]:
        """Legacy ISensor output: per-target NE measurements + clutter (do_idx=-1).

        Targets whose bearing was not swept since the previous call return NaN
        placeholders; the tracker-side cache keeps the last valid measurement.
        """
        if not self._initialized or t < 0.0001:
            self._prev_t = t
            self._initialized = True
            return [(do_tup[0], np.nan * np.ones(2)) for do_tup in true_do_states]

        records, clutter, _ = self._scan(t, true_do_states, ownship_state)
        measurements: list[tuple[int, np.ndarray]] = []
        detected_by_idx = {record["do_idx"]: record for record in records}
        for do_idx, _do_state, _do_length, _do_width in true_do_states:
            record = detected_by_idx.get(do_idx)
            measurements.append((do_idx, record["position_world"] if record else np.nan * np.ones(2)))
        for point in clutter:
            measurements.append((-1, point["position_world"]))
        return measurements

    def generate_sfd_frame(
        self,
        t: float,
        true_do_states: list[tuple[int, np.ndarray, float, float]],
        ownship_state: np.ndarray,
        ownship_yaw: float = 0.0,
    ) -> dict:
        """Builds a sensor-model-v1 measurement frame (contract §3; sensor_id=1).

        Positions are ownship-NED NE meters (world NE minus ownship NE, the v1
        flat-sea convention); record ``t_s`` is the beam-crossing time (<= frame
        ``t_s``, contract age semantics). This method consumes its own scan, so
        it is an alternative to — not a wrapper around —
        :meth:`generate_measurements`.
        """
        if not self._initialized or t < 0.0001:
            self._prev_t = t
            self._initialized = True
        records, clutter, _ = self._scan(t, true_do_states, ownship_state)
        own_ne = np.asarray(ownship_state, dtype=float)[:2]
        measurements = []
        for record in records:
            measurements.append(
                {
                    "sensor_id": 1,
                    "target_hint": None,
                    "position_ne_m": [
                        float(record["position_world"][0] - own_ne[0]),
                        float(record["position_world"][1] - own_ne[1]),
                    ],
                    "position_cov_ne_m2": record["cov_ne"].tolist(),
                    "t_s": float(record["t_cross"]),
                    "confidence": float(record["confidence"]),
                    "class_name": None,
                    "class_confidence": None,
                }
            )
        for point in clutter:
            measurements.append(
                {
                    "sensor_id": 1,
                    "target_hint": None,
                    "position_ne_m": [
                        float(point["position_world"][0] - own_ne[0]),
                        float(point["position_world"][1] - own_ne[1]),
                    ],
                    "position_cov_ne_m2": [[self._params.sigma_range_m**2, 0.0], [0.0, self._params.sigma_range_m**2]],
                    "t_s": float(t),
                    "confidence": float(point["confidence"]),
                    "class_name": None,
                    "class_confidence": None,
                }
            )
        return {
            "schema_version": "sensor-model@1",
            "frame_id": "ownship_ned",
            "t_s": float(t),
            "sensor_id": 1,
            "sensor_label": "radar_x",
            "mount_id": self._params.mount_id,
            "measurements": measurements,
            "ownship_pose_at_measurement": {
                "p_n": float(own_ne[0]),
                "p_e": float(own_ne[1]),
                "yaw": float(ownship_yaw),
                "pitch": 0.0,
                "roll": 0.0,
            },
            "epoch_unix_ns": None,
        }

    # ------------------------------------------------------------------ internals
    def _scan(
        self, t: float, true_do_states: list[tuple[int, np.ndarray, float, float]], ownship_state: np.ndarray
    ) -> tuple[list[dict], list[dict], float]:
        """Runs one asynchronous scan step.

        Returns (target records, clutter points, scan-period fraction swept).
        A target record exists only when the beam crossed its bearing since the
        previous call; clutter regenerates once per completed revolution.
        """
        own_ne = np.asarray(ownship_state, dtype=float)[:2]
        velocity = np.asarray(ownship_state, dtype=float)[2:4]
        yaw = float(np.arctan2(velocity[1], velocity[0])) if np.linalg.norm(velocity) > 0.1 else 0.0

        omega = 2.0 * np.pi * self._params.rpm / 60.0
        t_prev = self._prev_t
        swept = omega * (t - t_prev)
        self._prev_t = t
        new_revolution = swept > 0.0 and (
            int(np.floor(omega * t / (2.0 * np.pi))) > int(np.floor(omega * t_prev / (2.0 * np.pi)))
        )

        records: list[dict] = []
        for do_idx, do_state, do_length, do_width in true_do_states:
            delta = np.asarray(do_state, dtype=float)[:2] - own_ne
            distance = float(np.hypot(delta[0], delta[1]))
            if distance <= 1e-6:
                continue
            bearing = float(np.arctan2(delta[1], delta[0])) % (2.0 * np.pi)
            angle_past = (bearing - (omega * t_prev)) % (2.0 * np.pi)
            crossed = swept >= 2.0 * np.pi or (0.0 < angle_past <= swept)
            if not crossed:
                continue
            t_cross = min(t, t_prev + (angle_past / swept) * (t - t_prev)) if swept > 0 else t
            record = self._detect(do_idx, do_state, do_length, do_width, own_ne, distance, bearing, yaw, t_cross)
            if record is not None:
                records.append(record)

        clutter: list[dict] = []
        if new_revolution:
            clutter = self._generate_clutter(own_ne)

        budget = self._params.max_measurements_per_scan - len(records)
        if len(clutter) > budget:
            clutter = clutter[: max(0, budget)]
        return records, clutter, swept

    def _detect(
        self,
        do_idx: int,
        do_state: np.ndarray,
        do_length: float,
        do_width: float,
        own_ne: np.ndarray,
        distance: float,
        bearing: float,
        yaw: float,
        t_cross: float,
    ) -> dict | None:
        """Per-crossing detection chain: geometry gates, PD(SNR), noise. None = no detection."""
        p = self._params
        if distance <= self.blind_ring_m:
            return None
        if distance > self.active_range_m:
            return None
        target_height = float(np.clip(p.target_height_per_length * do_length, p.target_height_min_m, p.target_height_max_m))
        if distance > self.horizon_range_m(target_height):
            return None
        if self._bearing_blind(bearing, yaw):
            return None
        if self._occluded(own_ne, np.asarray(do_state, dtype=float)[:2], target_height):
            return None
        snr_db = self.snr_db(distance, self.rcs_m2(do_length, do_width))
        pd = float(detection_probability_swerling0(snr_db, p.pfa))
        if self._rng.random() > pd:
            return None
        if p.drop_probability > 0.0 and self._rng.random() < p.drop_probability:
            return None
        # Polar VIMM noise (sigma_r, sigma_theta) projected to NE around the ownship.
        noisy_distance = distance + float(self._rng.normal(0.0, p.sigma_range_m))
        noisy_bearing = bearing + float(self._rng.normal(0.0, p.sigma_azimuth_rad))
        position = own_ne + noisy_distance * np.array([np.cos(noisy_bearing), np.sin(noisy_bearing)])
        return {
            "do_idx": do_idx,
            "position_world": position,
            "cov_ne": self.position_cov_ne(noisy_distance),
            "snr_db": snr_db,
            "confidence": pd,
            "t_cross": t_cross,
        }

    def _bearing_blind(self, bearing: float, yaw: float) -> bool:
        """Checks the configurable mast/rigging blind sectors (degrees, relative to bow)."""
        for center_deg, half_width_deg in self._params.blind_sectors_deg:
            relative = np.degrees(bearing - yaw) - center_deg
            angular_distance = abs((relative + 180.0) % 360.0 - 180.0)
            if angular_distance <= half_width_deg:
                return True
        return False

    def _occluded(self, own_ne: np.ndarray, target_ne: np.ndarray, target_height_m: float) -> bool:
        """Terrain line-of-sight check; lazily resolves the DEM path once. False = visible."""
        if not self._occlusion_resolved:
            self._occlusion_grid = load_occlusion_grid(
                self._params.occlusion_dem_path,
                downsample=self._params.occlusion_downsample,
                mode=self._params.occlusion_mode,
            )
            self._occlusion_resolved = True
        if self._occlusion_grid is None:
            return False
        return self._occlusion_grid.line_of_sight_blocked(
            antenna_e=own_ne[1],
            antenna_n=own_ne[0],
            target_e=target_ne[1],
            target_n=target_ne[0],
            antenna_height_m=self._params.antenna_height_m,
            target_height_m=target_height_m,
        )

    def _generate_clutter(self, own_ne: np.ndarray) -> list[dict]:
        """Poisson clutter points over the (blind ring, range scale) annulus.

        Intensity lambda(r) = rate * sea_factor(B) * (r_ref/r)^decay (He 2024
        parameterized; azimuth-uniform). Equivalent to per-resolution-cell
        Poisson thinning by inverse-CDF radial sampling; compound amplitude =
        Gamma texture x exponential speckle power (K-family, unity mean).
        """
        p = self._params
        expected = float(self.expected_clutter_count())
        if expected <= 0.0:
            return []
        count = int(self._rng.poisson(expected))
        count = min(count, p.max_measurements_per_scan)
        if count <= 0:
            return []
        r_blind = self.blind_ring_m
        r_max = self.active_range_m
        grid = np.linspace(r_blind, r_max, 257)
        decay = p.clutter_range_decay
        weights = grid ** (1.0 - decay)
        cdf = np.cumsum(weights)
        cdf /= cdf[-1]
        radii = np.interp(self._rng.random(count), cdf, grid)
        bearings = self._rng.random(count) * 2.0 * np.pi
        texture = self._rng.wald(1.0, max(self.clutter_texture_shape(), 1e-6), size=count)
        power = texture * self._rng.exponential(1.0, size=count)
        snr_db = p.clutter_snr_ref_db + 10.0 * np.log10(np.maximum(power, 1e-12))
        confidence = np.clip(detection_probability_swerling0(snr_db, p.pfa), 0.0, 1.0)
        clutter = []
        for i in range(count):
            clutter.append(
                {
                    "position_world": own_ne + radii[i] * np.array([np.cos(bearings[i]), np.sin(bearings[i])]),
                    "confidence": float(confidence[i]),
                }
            )
        return clutter

    # ------------------------------------------------------------------ public helpers
    def rcs_m2(self, do_length: float, do_width: float) -> float:
        """Rough RCS estimate from ship dimensions (domain doc 02 §5 row 5, class table stand-in)."""
        return max(self._params.rcs_min_m2, do_length * do_width * self._params.rcs_area_factor)

    def snr_db(self, distance_m: float, rcs_m2: float) -> float:
        """Range-equation SNR: reference point + RCS ratio - r^4 decay (dB)."""
        p = self._params
        floor_distance = max(distance_m, self.blind_ring_m, 1.0)
        return (
            p.snr_ref_db
            + 10.0 * np.log10(rcs_m2 / p.rcs_ref_m2)
            - p.snr_decay_db_per_decade * np.log10(floor_distance / p.snr_ref_range_m)
        )

    def horizon_range_m(self, target_height_m: float) -> float:
        """Radar horizon d[m] = 4.12 (sqrt(h_ant[m]) + sqrt(h_tgt[m])) (k = 4/3)."""
        return 4120.0 * (np.sqrt(self._params.antenna_height_m) + np.sqrt(target_height_m))

    def position_cov_ne(self, distance_m: float) -> np.ndarray:
        """Polar (sigma_r, sigma_theta) Jacobian-projected NE covariance at a range.

        Azimuth-averaged (rotation-invariant isotropic) form: eigenvalues
        0.5 (sigma_r^2 + (r sigma_theta)^2), the trace-preserving average of the
        exact J diag(sigma_r^2, sigma_theta^2) J^T over bearing.
        """
        sigma2_r = self._params.sigma_range_m**2
        sigma2_cross = (distance_m * self._params.sigma_azimuth_rad) ** 2
        sigma2 = 0.5 * (sigma2_r + sigma2_cross)
        return np.diag([sigma2, sigma2])

    def expected_clutter_count(self) -> float:
        """Analytic Poisson mean over the annulus: integral of the intensity function."""
        p = self._params
        sea_factor = 10.0 ** (0.1 * p.clutter_db_per_beaufort * (p.sea_state_beaufort - 3.0))
        r_min = self.blind_ring_m
        r_max = self.active_range_m
        decay = p.clutter_range_decay
        if abs(decay - 2.0) < 1e-9:
            integral = np.log(r_max / r_min)
        else:
            integral = (r_max ** (2.0 - decay) - r_min ** (2.0 - decay)) / (2.0 - decay)
        return float(2.0 * np.pi * p.clutter_rate_per_m2 * sea_factor * p.clutter_ref_range_m**decay * integral)

    def clutter_texture_shape(self) -> float:
        """Compound texture shape nu: spikier (smaller) with higher sea state."""
        return float(np.clip(self._params.clutter_texture_nu_ref - 0.5 * (self._params.sea_state_beaufort - 3.0), 0.5, 20.0))

    def ppi_descriptor(self) -> dict:
        """Additive WS descriptor for the web PPI panel (seed + parameterization)."""
        p = self._params
        return {
            "schema_version": "radar-ppi@1",
            "sensor_label": "radar_x",
            "mount_id": p.mount_id,
            "seed": self._seed,
            "spokes": int(p.spokes_per_revolution),
            "scan_period_s": float(self.scan_period_s),
            "range_scales_nm": [float(scale) for scale in p.range_scales_nm],
            "range_scale_nm": float(p.range_scale_nm),
            "blind_ring_m": float(self.blind_ring_m),
            "blind_sectors_deg": [list(sector) for sector in p.blind_sectors_deg],
            "clutter_rate_per_m2": float(p.clutter_rate_per_m2),
            "clutter_range_decay": float(p.clutter_range_decay),
            "clutter_ref_range_m": float(p.clutter_ref_range_m),
            "sea_state_beaufort": float(p.sea_state_beaufort),
            "clutter_texture_nu": float(self.clutter_texture_shape()),
            "snr_model": {
                "snr_ref_db": float(p.snr_ref_db),
                "ref_range_m": float(p.snr_ref_range_m),
                "ref_rcs_m2": float(p.rcs_ref_m2),
                "decay_db_per_decade": float(p.snr_decay_db_per_decade),
                "pfa": float(p.pfa),
            },
            "occlusion": self._occlusion_grid is not None,
        }

    @property
    def scan_period_s(self) -> float:
        return 60.0 / self._params.rpm

    @property
    def blind_ring_m(self) -> float:
        """Near blind ring R_min = h_ant / tan(VBW/2) (milliampere-ch5 §4.3: 54-68 m)."""
        return self._params.antenna_height_m / np.tan(np.radians(0.5 * self._params.vbw_deg))

    @property
    def active_range_m(self) -> float:
        return self._params.range_scale_nm * N_METERS_PER_NM

    @property
    def max_range(self) -> float:
        return self.active_range_m

    @property
    def params(self) -> RadarXParams:
        return self._params


@dataclass
class ExternalCameraParams:
    """External camera observation feed parameters (P3-S2, spec #90).

    Anchors: sensor_id vocabulary sensor-model-v1 §2 (camera_eo=2/camera_ir=3),
    mast mount calibration = ``colav_simulator.core.mast_cameras`` (FBX mast
    anchor 12.98 m, placement table milliampere-ch5 §4.2), measurement noise
    shape = radial-elongated NE covariance (contract §3 E5 form, produced by the
    observations-endpoint georef).
    """

    sensor_id: int = 2  # camera_eo (contract observations-v1 §2: 2|3 only)
    max_range_m: float = 2.0 * 1852.0  # 2 nm external camera detection envelope
    inbox_capacity: int = 256  # pending georeferenced records before the oldest drops
    # P1-1a review fix (spec #90): simulation-level association gate. A drained
    # record within this distance of the nearest ground-truth target rides that
    # target's do_idx (radar-generation fidelity — the KF main chain consumes
    # it); beyond the gate it stays in the -1 clutter slot.
    association_gate_m: float = 50.0

    def to_dict(self) -> dict:
        return {
            "sensor_id": self.sensor_id,
            "max_range_m": self.max_range_m,
            "association_gate_m": self.association_gate_m,
        }

    @classmethod
    def from_dict(cls, config_dict: dict) -> "ExternalCameraParams":
        known = {f: config_dict[f] for f in cls.__dataclass_fields__ if f in config_dict}
        return cls(**known)


class ExternalCameraSensor(ISensor):
    """Consumes the observations endpoint georeferenced records (P3-S2).

    The endpoint (gui_server, the only writer) georeferences accepted pixel
    boxes into ownship-NED NE records and feeds them to :meth:`submit`; the
    sensor exposes them through the ISensor legacy shape —
    :meth:`generate_measurements` drains the inbox into ``(do_idx, z)`` tuples
    with **simulation-level nearest-truth association** (P1-1a review fix,
    spec #90, same fidelity as the Radar generation chain): a record within
    ``association_gate_m`` (default 50 m) of the nearest ground-truth target
    is emitted on that target's do_idx in the absolute NE frame (the georef
    noise is already baked into the record, mirroring the radar's
    ``z = h(do_state) + noise``), while a beyond-gate record keeps the
    RadarXBand clutter convention ``(do_idx=-1, z)`` — it never hijacks the
    tracker's GT-labelled data association. The sensor-model-v1 shaped
    consumers read :meth:`drain_records` / :meth:`sfd_records` (S2 status
    hook; S5 fusion wiring). Thread-safe: the endpoint posts from the FastAPI
    threadpool while the simulator tick drains from the session thread.

    Assembly discipline (default off): the sensor only joins the tracker's
    measurement loop when the scene explicitly assembles it through the
    ``external_cameras:`` ship sensor key (radar_x precedent) — unassembled
    sessions keep the gui_server session-scoped cache, so the default tracker
    behaviour is untouched.

    Legacy compatibility: ``generate_measurements`` returns the ISensor
    ``list[(do_idx, z)]`` shape with NaN placeholders for the true targets —
    directly consumable by the existing KF/GodTracker measurement cache.
    """

    def __init__(self, params: ExternalCameraParams | None = None) -> None:
        self.type: str = "camera_eo" if (params is None or params.sensor_id == 2) else "camera_ir"
        self._params: ExternalCameraParams = params if params is not None else ExternalCameraParams()
        self._H: np.ndarray = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])
        self._rng: np.random.Generator = np.random.default_rng()
        # Isotropic default R (tracker side); the per-measurement covariances
        # ride with the records (radial-elongated form, contract §3).
        self._R_ne: np.ndarray = np.diag([8.0**2, 11.0**2])
        self._inbox: deque = deque(maxlen=max(1, self._params.inbox_capacity))
        self._lock = threading.Lock()
        self._accepted_frames = 0
        self._last_frame_seq: int | None = None

    # ------------------------------------------------------------------ deepcopy/pickle
    # The scenario generator deep-copies assembled ships per episode
    # (scenario_generator.generate); locks are neither picklable nor
    # deepcopyable, so the assembled sensor carries a fresh one per copy.
    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        state["_lock"] = None
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ ISensor
    def reset(self, seed: int | None) -> None:
        self.seed(seed)
        with self._lock:
            self._inbox.clear()
        self._accepted_frames = 0
        self._last_frame_seq = None

    def seed(self, seed: int | None) -> None:
        self._rng = np.random.default_rng(seed)

    def R(self, xs: np.ndarray) -> np.ndarray:  # noqa: ARG002
        return self._R_ne

    def H(self, xs: np.ndarray) -> np.ndarray:  # noqa: ARG002
        return self._H

    def h(self, xs: np.ndarray) -> np.ndarray:
        return self._H @ xs

    def generate_measurements(
        self,
        t: float,  # noqa: ARG002 - ISensor signature; external records carry their own stamps
        true_do_states: list[tuple[int, np.ndarray, float, float]],
        ownship_state: np.ndarray,
    ) -> list[tuple[int, np.ndarray]]:
        """Legacy ISensor output: per-target NE (associated) + clutter slot.

        NaN placeholders per true target; an associated record REPLACES its
        target's placeholder (the KF automatic data association keys on do_idx
        and must not hit the NaN twin first), an unassociated record rides the
        clutter slot as (do_idx=-1, NE) — the simulator measurement cache keeps
        the non-NaN entries (simulator.py extract_valid_sensor_measurements).
        Associated z is absolute NE (radar frame convention): ownship + the
        record's ownship-relative georef NE.
        """
        placeholders = [(do_tup[0], np.nan * np.ones(2)) for do_tup in true_do_states]
        measurements: list[tuple[int, np.ndarray]] = list(placeholders)
        placeholder_at = {do_tup[0]: pos for pos, do_tup in enumerate(true_do_states)}
        own_ne = np.asarray(ownship_state, dtype=float)[:2]
        for record in self._drain():
            do_idx = self._associate(record, own_ne, true_do_states)
            if do_idx < 0:
                measurements.append((-1, np.asarray(record["position_ne_m"], dtype=float)))
            else:
                measurements[placeholder_at[do_idx]] = (
                    do_idx,
                    own_ne + np.asarray(record["position_ne_m"], dtype=float),
                )
        return measurements

    def _associate(
        self, record: dict, own_ne: np.ndarray, true_do_states: list[tuple[int, np.ndarray, float, float]]
    ) -> int:
        """Nearest ground-truth target within the association gate, else -1.

        Records are ownship-relative georef NE; truth is absolute NE, so the
        record is lifted into the absolute frame against the same ownship pose
        the tracker tick provided (radar-generation fidelity, P1-1a).
        """
        gate_m = self._params.association_gate_m
        if gate_m <= 0.0 or not true_do_states:
            return -1
        absolute = own_ne + np.asarray(record["position_ne_m"], dtype=float)
        best_idx, best_dist = -1, gate_m
        for do_idx, do_state, _do_length, _do_width in true_do_states:
            distance = float(np.linalg.norm(np.asarray(do_state, dtype=float)[:2] - absolute))
            if distance <= best_dist:
                best_idx, best_dist = int(do_idx), distance
        return best_idx

    # ------------------------------------------------------------------ endpoint side
    def submit(self, records: list[dict], frame_seq: int | None = None) -> int:
        """Appends georeferenced records (mast_cameras.georeference_box shaped).

        Required record keys: ``position_ne_m`` [n, e], ``position_cov_ne_m2``
        2x2, ``confidence``, ``class_name``, ``t_s``. Returns the inbox depth
        after the append. Called from the gui_server endpoint thread (the
        records leave the inbox through the ISensor drain, never here).
        """
        if not records:
            self._accepted_frames += 1
            if frame_seq is not None:
                self._last_frame_seq = int(frame_seq)
            return len(self._inbox)
        with self._lock:
            for record in records:
                self._inbox.append(dict(record))
            depth = len(self._inbox)
        self._accepted_frames += 1
        if frame_seq is not None:
            self._last_frame_seq = int(frame_seq)
        return depth

    def _drain(self) -> list[dict]:
        with self._lock:
            records = list(self._inbox)
            self._inbox.clear()
        return records

    # ------------------------------------------------------------------ readers
    def drain_records(self) -> list[dict]:
        """Pops all pending georeferenced records (S2 status hook / test seams)."""
        return self._drain()

    def pending_records(self) -> list[dict]:
        """Snapshot of pending records without draining (status endpoint)."""
        with self._lock:
            return [dict(record) for record in self._inbox]

    def sfd_records(self, t_s: float, ownship_pose: dict | None = None) -> dict:
        """Builds a sensor-model-v1 §3 frame from the pending records.

        Empty array = authoritative no-measurement (contract §3). The frame is
        returned, not stored; ownership passes to the caller (S5 wiring).
        """
        records = self._drain()
        measurements = []
        for record in records:
            measurements.append(
                {
                    "sensor_id": int(self._params.sensor_id),
                    "target_hint": None,
                    "position_ne_m": [float(v) for v in record["position_ne_m"]],
                    "position_cov_ne_m2": [[float(v) for v in row] for row in record["position_cov_ne_m2"]],
                    "t_s": float(record.get("t_s", t_s)),
                    "confidence": float(record.get("confidence", 1.0)),
                    "class_name": record.get("class_name"),
                    "class_confidence": record.get("class_confidence"),
                }
            )
        return {
            "schema_version": "sensor-model@1",
            "frame_id": "ownship_ned",
            "t_s": float(t_s),
            "sensor_id": int(self._params.sensor_id),
            "sensor_label": self.type,
            "mount_id": str(records[0].get("mount_id", "")) if records else "",
            "measurements": measurements,
            "ownship_pose_at_measurement": ownship_pose or {},
            "epoch_unix_ns": None,
        }

    @property
    def accepted_frames(self) -> int:
        return self._accepted_frames

    @property
    def last_frame_seq(self) -> int | None:
        return self._last_frame_seq

    @property
    def max_range(self) -> float:
        return self._params.max_range_m

    @property
    def params(self) -> ExternalCameraParams:
        return self._params


MOUNT_ID_LIDAR_DEFAULT = "mast_lidar"

#: Mast-table source of the LiDAR mount geometry (backend-authoritative single
#: copy in ``colav_simulator/core/mast_cameras.py``; Unity MastCameraTable
#: mirrors the same literals — parity pinned by tests on both sides).
_LIDAR_MOUNT = MAST_MOUNTS_BY_ID[MOUNT_ID_LIDAR_DEFAULT]


@dataclass
class LidarParams:
    """LiDAR near-field contact parameters (P3-S3, sensor-model-v1 sensor_id=4 ``lidar``).

    Anchors (milliampere-ch5 §5.2 table + contract §4):
    - mount = ``colav_simulator.core.mast_cameras`` ``mast_lidar`` row (11 m
      flange under the mast top, +2.1 m forward, 10 deg install downtilt);
    - 16 lines, +-15 deg band, 10 Hz, 100 m range (VLP-16 class, report 03
      minimum-fidelity baseline);
    - noise = AWSIM/RGL range Gaussian (sigma base 0.02 m + 2 mm/m rise) +
      VIMM cross-range calibration ``lidar_sigma_c_m = 6.6 m`` (contract §4);
    - visibility = VIMM per-target Markov chain (w11/w01) + global PD
      (contract §4 ``visibility``);
    - near blind ring follows the tilted install: lower band edge
      |pitch| + 15 deg => R_min = h / tan(edge) (milliampere-ch5 §4.3).
    """

    sensor_id: int = 4
    mount_id: str = MOUNT_ID_LIDAR_DEFAULT
    max_range_m: float = 100.0
    measurement_rate_hz: float = 10.0
    channel_count: int = 16
    vertical_fov_deg: float = 30.0
    mount_height_m: float = _LIDAR_MOUNT.height_m
    mount_pitch_deg: float = _LIDAR_MOUNT.pitch_deg
    # Noise: AWSIM/RGL range Gaussian + VIMM lidar_sigma_c cross-range (m).
    sigma_range_base_m: float = 0.02
    sigma_range_rise_per_m: float = 0.002
    sigma_cross_range_m: float = 6.6
    # Visibility (contract §4 VIMM chain): w11 stay-visible / w01 enter-visible.
    visibility_w11: float = 0.90
    visibility_w01: float = 0.52
    detection_probability: float = 0.92
    # Terrain occlusion (S1 tool reuse; same defaults/semantics as RadarXParams).
    occlusion_dem_path: str | None = None
    occlusion_mode: str = "elevation"  # "elevation" | "landmask"
    occlusion_downsample: int = 4
    occlusion_grid: TerrainGrid | None = None

    def __post_init__(self) -> None:  # noqa: D105
        if self.occlusion_mode not in {"elevation", "landmask"}:
            msg = f"occlusion_mode must be 'elevation' or 'landmask', got {self.occlusion_mode!r}"
            raise ValueError(msg)

    @classmethod
    def from_dict(cls, config_dict: dict) -> "LidarParams":
        known = {f: config_dict[f] for f in cls.__dataclass_fields__ if f in config_dict}
        return cls(**known)

    def to_dict(self) -> dict:
        output_dict = asdict(self)
        output_dict.pop("occlusion_grid", None)
        return output_dict


class LidarContactSensor(ISensor):
    """LiDAR near-field contact model (P3-S3, sensor-model-v1 sensor_id=4 ``lidar``).

    Bypass semantics (contract §1/§2 hard boundary): the sensor feeds the
    measurement cache (display / S5 fusion-adjacent consumers) but NEVER the
    IPDA — ``bypass_fusion`` is True and the KF main chain skips it. Contact
    points are synthesized from the simulator's own geometric truth (the Unity
    point cloud never crosses the Unity↔backend boundary — the two channels are
    independent by design). Per target within [blind ring, 100 m], visible per
    the VIMM Markov chain and DEM-occlusion-checked: a polar-noisy NE point at
    10 Hz. No sea clutter in v1 (milliampere §5.2 浪致点噪 left to a later
    segment; the visual cloud carries the per-point CARLA dropout instead).
    """

    type: str = "lidar"
    bypass_fusion = True  # sensor-model-v1 §1: 旁路通道，不进 IPDA（硬边界）

    def __init__(self, params: LidarParams | None = None) -> None:
        self._params: LidarParams = params if params is not None else LidarParams()
        self._H: np.ndarray = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])
        self._rng: np.random.Generator = np.random.default_rng()
        self._prev_t: float = 0.0
        self._initialized: bool = False
        self._visible: dict[int, bool] = {}  # per-target visibility Markov state
        self._occlusion_grid: TerrainGrid | None = self._params.occlusion_grid
        self._occlusion_resolved: bool = self._params.occlusion_grid is not None

    # ------------------------------------------------------------------ ISensor
    def reset(self, seed: int | None) -> None:
        self.seed(seed)
        self._prev_t = 0.0
        self._initialized = False
        self._visible = {}

    def seed(self, seed: int | None) -> None:
        self._rng = np.random.default_rng(seed)

    def R(self, xs: np.ndarray) -> np.ndarray:  # noqa: ARG002
        return self.position_cov_ne(self.blind_ring_m)

    def H(self, xs: np.ndarray) -> np.ndarray:  # noqa: ARG002
        return self._H

    def h(self, xs: np.ndarray) -> np.ndarray:
        return self._H @ xs

    def generate_measurements(
        self, t: float, true_do_states: list[tuple[int, np.ndarray, float, float]], ownship_state: np.ndarray
    ) -> list[tuple[int, np.ndarray]]:
        """Legacy ISensor output: per-target NE contact points (NaN placeholders).

        The 10 Hz rate gate holds the contacts back between frames (cache keeps
        the last valid point per target); undetected/unvisible/occluded targets
        yield NaN placeholders.
        """
        placeholders = [(do_tup[0], np.nan * np.ones(2)) for do_tup in true_do_states]
        if not self._initialized or t < 0.0001:
            self._prev_t = t
            self._initialized = True
            return placeholders
        if (t - self._prev_t) < (1.0 / self._params.measurement_rate_hz) - 1e-9:
            # The 1e-9 epsilon absorbs float accumulation in t (0.1+0.1+... drifts
            # below the exact period and would silently skip frames).
            return placeholders
        self._prev_t = t

        own_ne = np.asarray(ownship_state, dtype=float)[:2]
        measurements: list[tuple[int, np.ndarray]] = []
        for do_idx, do_state, _do_length, _do_width in true_do_states:
            delta = np.asarray(do_state, dtype=float)[:2] - own_ne
            distance = float(np.hypot(delta[0], delta[1]))
            if distance <= self.blind_ring_m or distance > self._params.max_range_m:
                measurements.append((do_idx, np.nan * np.ones(2)))
                continue
            if not self._is_visible(do_idx):
                measurements.append((do_idx, np.nan * np.ones(2)))
                continue
            if self._occluded(own_ne, delta, distance):
                measurements.append((do_idx, np.nan * np.ones(2)))
                continue
            bearing = float(np.arctan2(delta[1], delta[0]))
            noisy_distance = distance + float(self._rng.normal(0.0, self.range_sigma_m(distance)))
            noisy_bearing = bearing + float(
                self._rng.normal(0.0, self._params.sigma_cross_range_m / max(distance, 1.0))
            )
            position = own_ne + noisy_distance * np.array([np.cos(noisy_bearing), np.sin(noisy_bearing)])
            measurements.append((do_idx, position))
        return measurements

    # ------------------------------------------------------------------ internals
    def _is_visible(self, do_idx: int) -> bool:
        """Per-target visibility Markov chain (VIMM w11/w01) + global PD gate."""
        p = self._params
        was_visible = self._visible.get(do_idx, False)
        enter_probability = p.visibility_w11 if was_visible else p.visibility_w01
        visible = bool(self._rng.random() < enter_probability)
        self._visible[do_idx] = visible
        return visible and bool(self._rng.random() < p.detection_probability)

    def _occluded(self, own_ne: np.ndarray, delta: np.ndarray, distance: float) -> bool:
        """Terrain line-of-sight check; lazily resolves the DEM path once. False = visible."""
        if not self._occlusion_resolved:
            self._occlusion_grid = load_occlusion_grid(
                self._params.occlusion_dem_path,
                downsample=self._params.occlusion_downsample,
                mode=self._params.occlusion_mode,
            )
            self._occlusion_resolved = True
        if self._occlusion_grid is None:
            return False
        target_ne = own_ne + delta
        return self._occlusion_grid.line_of_sight_blocked(
            antenna_e=own_ne[1],
            antenna_n=own_ne[0],
            target_e=target_ne[1],
            target_n=target_ne[0],
            antenna_height_m=self._params.mount_height_m,
            target_height_m=2.0,
        )

    # ------------------------------------------------------------------ helpers
    def range_sigma_m(self, distance_m: float) -> float:
        """AWSIM/RGL range Gaussian sigma at a distance (base + rise·d)."""
        return self._params.sigma_range_base_m + self._params.sigma_range_rise_per_m * max(0.0, distance_m)

    def position_cov_ne(self, distance_m: float) -> np.ndarray:
        """Polar (sigma_r, sigma_c) Jacobian-projected NE covariance (isotropic form).

        Same azimuth-averaged shape as RadarXBand: eigenvalues
        0.5 (sigma_r^2 + sigma_c^2) with the VIMM cross-range calibration held
        constant in range.
        """
        sigma2_r = self.range_sigma_m(distance_m) ** 2
        sigma2_c = self._params.sigma_cross_range_m**2
        sigma2 = 0.5 * (sigma2_r + sigma2_c)
        return np.diag([sigma2, sigma2])

    @property
    def blind_ring_m(self) -> float:
        """Near blind ring of the tilted install: lower edge = |pitch| + band/2."""
        lower_edge_deg = abs(self._params.mount_pitch_deg) + 0.5 * self._params.vertical_fov_deg
        return self._params.mount_height_m / np.tan(np.radians(lower_edge_deg))

    @property
    def max_range(self) -> float:
        return self._params.max_range_m

    @property
    def params(self) -> LidarParams:
        return self._params
