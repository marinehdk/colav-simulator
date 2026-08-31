# Frozen AGX L4-5 characterization fixture producer

Purpose: generate source-behavior characterization from external frozen baseline `l45-source-20260824-v2`. Output remains migration evidence, never vessel validation. The frozen export is read-only: the Python producer stages it in a temporary directory before running a recipe, and fixture output is always written outside the source tree.

## Required external inputs

- Frozen source directory outside Git.
- `SOURCE_MANIFEST.csv` with SHA-256 for every declared source file.
- Expected SHA-256 of that manifest supplied independently (`2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411` for the verified 2026-08-24 export; re-measure on the target host).
- The repository-owned adapter recipe `build_frozen_source_fixture.sh` and probe `frozen_source_probe.cpp`. The recipe compiles the source's pure environment-load-model seam and emits `fixture-output.json` plus `fixture-output.npz`; it does not claim to be source-owned.
- Linux/AGX or container compiler/toolchain.
- Actual config, dependency, asset, test, and seed metadata files.

## Recipe

```bash
python -m colav_simulator.modular_gnc.characterization \
  --source /external/l45-source-20260824-v2 \
  --source-manifest /external/l45-source-20260824-v2/SOURCE_MANIFEST.csv \
  --recipe /repo/tools/gnc_characterization/build_frozen_source_fixture.sh \
  --recipe-sha256 <independently-recorded-recipe-sha256> \
  --build-input probe=/repo/tools/gnc_characterization/frozen_source_probe.cpp \
  --output /tmp/agx-l45-characterization \
  --compiler c++ \
  --compiler-sha256 <independently-recorded-compiler-executable-sha256> \
  --manifest-sha256 <independently-recorded-manifest-sha256> \
  --config /external/evidence/config.json \
  --dependencies /external/evidence/dependencies.json \
  --assets /external/evidence/assets.json \
  --tests /external/evidence/tests.json \
  --seeds /external/evidence/seeds.json
```

The explicit recipe interface is `RECIPE SOURCE_ROOT OUTPUT_JSON OUTPUT_NPZ COMPILER`. The recipe may compile only from `SOURCE_ROOT`; it must not write there. Every repository-owned recipe and probe/build input must be supplied with an independent SHA-256 identity (the CLI accepts repeated `--build-input NAME=PATH`). `build_frozen_source_fixture.sh` uses the four pure C++ source files under `src/environment/env_engines`, then creates a deterministic NPZ containing the C++ output values. Missing source, manifest, toolchain, recipe, recipe identity, build input, metadata, JSON, or NPZ fails visibly. No no-execute mode exists. Commit only reviewed JSON/NPZ outputs and manifest identities. Never copy external source, build trees, binaries, or assets into Git.

## AGX recipe-only invocation

When the repository Python package is not installed on AGX, copy this recipe and probe to one dedicated temporary directory and run:

```bash
source /opt/ros/humble/setup.bash
tools/gnc_characterization/build_frozen_source_fixture.sh \
  /home/mass/sango/L4-5_source_only_20260824_v2 \
  /tmp/colav-gnc-characterization-<run>/fixture-output.json \
  /tmp/colav-gnc-characterization-<run>/fixture-output.npz \
  /usr/bin/c++
```

This direct command proves the real AGX C++ execution boundary. The final consumer manifest must additionally record the source-manifest, metadata, compiler executable, compiler version, recipe, JSON, and NPZ SHA-256 values. Run twice after deleting only the run directory's outputs; both JSON and NPZ must be byte-identical.

The source-only export's documented full `colcon build` is not used as this fixture seam: its test sources are intentionally excluded, and an isolated AGX colcon attempt also reaches a package setup step that expects an excluded package `README.md`. Reintroducing files into the frozen tree would change its identity. The selected adapter therefore compiles only the verified, ROS-independent pure-model sources and records that scope in the output; it does not claim a complete ROS workspace build.

## Ownership and recovery

TDL Lead owns fixture production. Producer remains operational single point. Recovery requires verified frozen source archive, independent manifest identity, declared compiler/container, and complete metadata inputs. This fixture is a source-characterization prerequisite only; it is not vessel calibration, vessel validation, COLAV acceptance, SIL/HIL, or sea-trial evidence.
