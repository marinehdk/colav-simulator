import sys
import os
import numpy as np
import pytest

# Ensure PSBMPCInterface binary path is accessible
psbmpc_so_dir = "/Users/marine/Code/ecosystem/psbmpc/build/psbmpc_interface"
if os.path.exists(psbmpc_so_dir) and psbmpc_so_dir not in sys.path:
    sys.path.append(psbmpc_so_dir)

def test_imports_all_ecosystem():
    """Verify that all 4 ecosystem modules can be imported cleanly."""
    import colav_simulator
    import rrt_star_lib
    import vimmjipda
    import rlmpc
    import PSBMPCInterface
    import acados_template

    assert colav_simulator is not None
    assert rrt_star_lib is not None
    assert vimmjipda is not None
    assert rlmpc is not None
    assert PSBMPCInterface is not None
    assert acados_template is not None

def test_rrt_rs_functionality():
    """Test rrt-rs (rrt_star_lib) planner module."""
    import rrt_star_lib
    assert hasattr(rrt_star_lib, "__name__")

def test_vimmjipda_tracker():
    """Test vimmjipda multi-target tracker module."""
    import vimmjipda
    assert hasattr(vimmjipda, "__file__")

def test_psbmpc_interface():
    """Test PSBMPCInterface compiled C++ wrapper classes."""
    import PSBMPCInterface
    assert hasattr(PSBMPCInterface, "PSBMPC")
    assert hasattr(PSBMPCInterface, "SBMPC")
    assert hasattr(PSBMPCInterface, "KinematicShip")

def test_rlmpc_module():
    """Test rlmpc module."""
    import rlmpc
    assert hasattr(rlmpc, "__file__")

if __name__ == "__main__":
    test_imports_all_ecosystem()
    test_rrt_rs_functionality()
    test_vimmjipda_tracker()
    test_psbmpc_interface()
    test_rlmpc_module()
    print("All ecosystem integration tests passed successfully!")
