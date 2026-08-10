#!/bin/sh
set -eu

FROZEN_COMMIT=ced58f8576f3772ef7c1bc72bb0f8b0368688b5a
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
MASS_WORKTREE=${1:?usage: export_oracle.sh /path/to/frozen/MASS-L3-worktree}
OUTPUT=${2:-/dev/stdout}

ACTUAL_COMMIT=$(git -C "$MASS_WORKTREE" rev-parse HEAD)
if [ "$ACTUAL_COMMIT" != "$FROZEN_COMMIT" ]; then
  echo "expected MASS-L3 $FROZEN_COMMIT, got $ACTUAL_COMMIT" >&2
  exit 2
fi

PACKAGE_ROOT="$MASS_WORKTREE/src/l3_tdl_kernel/m5_tactical_planner"
CASADI_ROOT=$(python3 -c 'import pathlib, casadi; print(pathlib.Path(casadi.__file__).parent)')
BUILD_DIR=${TMPDIR:-/tmp}/colav-mid-mpc-ipopt-oracle-$FROZEN_COMMIT
CXX=${CXX:-clang++}
BOOST_INCLUDE=${BOOST_INCLUDE:-/opt/homebrew/include}
EIGEN_INCLUDE=${EIGEN_INCLUDE:-/opt/homebrew/include/eigen3}
mkdir -p "$BUILD_DIR"

"$CXX" -std=c++17 -O2 \
  -I"$SCRIPT_DIR/compat_include" \
  -I"$PACKAGE_ROOT/include" \
  -I"$CASADI_ROOT/include" \
  -I"$BOOST_INCLUDE" \
  -I"$EIGEN_INCLUDE" \
  "$SCRIPT_DIR/oracle_main.cpp" \
  "$PACKAGE_ROOT/src/mid_mpc/mid_mpc_nlp_formulation.cpp" \
  "$PACKAGE_ROOT/src/mid_mpc/mid_mpc_solver.cpp" \
  "$PACKAGE_ROOT/src/shared/constraint_compiler.cpp" \
  -L"$CASADI_ROOT" -lcasadi \
  -Wl,-rpath,"$CASADI_ROOT" \
  -o "$BUILD_DIR/mid_mpc_ipopt_oracle"

"$BUILD_DIR/mid_mpc_ipopt_oracle" | awk '/^\{/{print; found=1} END {exit !found}' > "$OUTPUT"
