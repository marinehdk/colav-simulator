# Frozen AGX L4-5 characterization fixture producer

Purpose: generate source-behavior characterization evidence from external frozen source-only baseline `l45-source-20260824-v2`. Outputs are migration evidence only, never vessel validation.

## Required external inputs

- Frozen source directory outside Git.
- `manifest.sha256` containing `2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411`.
- Linux/AGX or container compiler/toolchain.
- Source-owned `build_characterization.sh` producing `fixture-output.json` schema `agx-l45-characterization-output.v1`.

## Recipe

```bash
python -m colav_simulator.modular_gnc.characterization \
  --source /external/l45-source-20260824-v2 \
  --output /tmp/agx-l45-characterization \
  --compiler c++
```

Commit only reviewed JSON/NPZ fixture outputs and manifest identities. Never copy source directory, build tree, binaries, or external assets into repository.

## Failure behavior

Missing source, wrong manifest, missing compiler, missing build recipe, or output schema mismatch fails visibly. No fallback or cross-version fixture reuse.

## Ownership and recovery

TDL Lead owns fixture production. Producer remains operational single point: recovery requires restoring frozen external source archive, declared compiler/container, and rerunning recipe. Preserve generated `manifest.json` with source/config/compiler/dependency/asset/test/seed/output SHA-256 identities.
