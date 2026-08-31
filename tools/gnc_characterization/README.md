# Frozen AGX L4-5 characterization fixture producer

Purpose: generate source-behavior characterization from external frozen baseline `l45-source-20260824-v2`. Output remains migration evidence, never vessel validation.

## Required external inputs

- Frozen source directory outside Git.
- `manifest.json` with baseline ID plus SHA-256 for every declared source file.
- Expected SHA-256 of that manifest supplied independently.
- Executable source-owned `build_characterization.sh` producing `fixture-output.json` schema `agx-l45-characterization-output.v1`.
- Linux/AGX or container compiler/toolchain.
- Actual config, dependency, asset, test, and seed metadata files.

## Recipe

```bash
python -m colav_simulator.modular_gnc.characterization \
  --source /external/l45-source-20260824-v2 \
  --output /tmp/agx-l45-characterization \
  --compiler c++ \
  --manifest-sha256 <independently-recorded-manifest-sha256> \
  --config /external/evidence/config.json \
  --dependencies /external/evidence/dependencies.json \
  --assets /external/evidence/assets.json \
  --tests /external/evidence/tests.json \
  --seeds /external/evidence/seeds.json
```

No no-execute mode exists. Missing external source/toolchain/recipe/metadata fails honestly. Commit only reviewed JSON/NPZ outputs and manifest identities. Never copy external source, build trees, binaries, or assets into Git.

## Ownership and recovery

TDL Lead owns fixture production. Producer remains operational single point. Recovery requires verified frozen source archive, independent manifest identity, declared compiler/container, and complete metadata inputs.
