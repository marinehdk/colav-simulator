#!/bin/sh
set -eu

if [ "$#" -ne 4 ]; then
    echo "usage: build_frozen_source_fixture.sh SOURCE_ROOT OUTPUT_JSON OUTPUT_NPZ COMPILER" >&2
    exit 2
fi

source_root=$1
json_output=$2
npz_output=$3
compiler=$4
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

test -d "$source_root"
test -f "$source_root/SOURCE_MANIFEST.csv"
test -f "$source_root/src/environment/env_engines/include/env_engines/current_load_model.hpp"
test -f "$source_root/src/environment/env_engines/include/env_engines/wind_load_model.hpp"
test -f "$source_root/src/environment/env_engines/include/env_engines/wave_response_model.hpp"
test -f "$source_root/src/environment/env_engines/include/env_engines/wave_drift_model.hpp"
test -x "$compiler"
command -v python3 >/dev/null 2>&1
mkdir -p "$(dirname -- "$json_output")" "$(dirname -- "$npz_output")"

run_root=$(mktemp -d "${TMPDIR:-/tmp}/colav-gnc-source-probe.XXXXXX")
trap 'rm -rf "$run_root"' EXIT HUP INT TERM

"$compiler" \
    -std=c++17 \
    -O2 \
    -Wall \
    -Wextra \
    -Wpedantic \
    -I"$source_root/src/environment/env_engines/include" \
    "$script_dir/frozen_source_probe.cpp" \
    "$source_root/src/environment/env_engines/src/current/current_load_model.cpp" \
    "$source_root/src/environment/env_engines/src/wind/wind_load_model.cpp" \
    "$source_root/src/environment/env_engines/src/wave/wave_response_model.cpp" \
    "$source_root/src/environment/env_engines/src/wave/wave_drift_model.cpp" \
    -o "$run_root/frozen_source_probe"

"$run_root/frozen_source_probe" "$json_output"

python3 - "$json_output" "$npz_output" <<'PY'
import io
import json
import sys
import zipfile

import numpy as np

json_path, npz_path = sys.argv[1:]
with open(json_path, encoding="utf-8") as handle:
    payload = json.load(handle)
values = [value for case in payload["cases"] for value in case["values"]]
array = np.asarray(values, dtype=np.float64)

def npy_bytes(value):
    buffer = io.BytesIO()
    np.lib.format.write_array(buffer, value, allow_pickle=False)
    return buffer.getvalue()

with zipfile.ZipFile(npz_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for name, value in (("source_values", array), ("source_value_count", np.asarray([array.size], dtype=np.int64))):
        info = zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o600 << 16
        archive.writestr(info, npy_bytes(value))
PY
