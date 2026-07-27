import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root = str(PROJECT_ROOT)
sys.path[:] = [entry for entry in sys.path if entry != project_root]
sys.path.insert(0, project_root)

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None


@pytest.fixture(autouse=True)
def close_plots_before_each_test():
    yield
    if plt is not None:
        plt.close("all")
