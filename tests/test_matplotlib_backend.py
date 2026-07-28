from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from colav_simulator.common import plotters
from colav_simulator.viz.visualizer import Config, Visualizer


def test_pytest_keeps_matplotlib_headless() -> None:
    assert mpl.get_backend().casefold() == "agg"

    Visualizer(Config(matplotlib_backend="TkAgg"))
    assert mpl.get_backend().casefold() == "agg"

    _, axis = plt.subplots()
    plotters.plot_image(np.zeros((2, 2)), ax=axis)
    assert mpl.get_backend().casefold() == "agg"
