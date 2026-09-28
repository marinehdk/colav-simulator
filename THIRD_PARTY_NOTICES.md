# Third-Party Notices

## MPC-Autonomous-Ship-Navigation

The Potočnik simplified MPC integration is derived from the algorithm,
equations, and MATLAB reference implementation in:

- Primož Potočnik, "Model Predictive Control for Autonomous Ship Navigation
  with COLREG Compliance and Chart-Based Path Planning", JMSE 13(7):1246,
  2025.
- https://github.com/ppotoc/MPC-Autonomous-Ship-Navigation
- audited upstream commit: `3683e92f9949cf884540d40a7ce096c3785273b3`

MIT License

Copyright (c) 2025 Primož Potočnik

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Web 3D visualization assets (2026-09-20)

CesiumJS 1.133.0: Apache-2.0, bundled license and third-party notices under
`web_gui/vendor/cesium/`. Proj4js 2.19.10: MIT, bundled license under
`web_gui/vendor/proj4/`. OpenBridge remains pinned to 1.0.1.

Kenney Watercraft Kit and the selected 3DAssets.dev target meshes are published
as CC0. Exact source pages, download URLs, hashes, geometric qualifications and
excluded partial models are recorded in `web_gui/assets/models/README.md` and
`targets/asset-manifest.json`. The FCB45 GLB is user-provided engineering artwork,
with provenance recorded separately; no CAD/physics fidelity claim is made.

## Sango FramePublisher vendored binaries (M3, spec #86)

`sango/Assets/Plugins/NetMQ/` ships two unmodified managed assemblies used by the
optional (default-OFF) ZeroMQ frame publisher. Full license texts live alongside
the DLLs (`LICENSE-NetMQ.txt`, `LICENSE-AsyncIO.md`).

### NetMQ 4.0.1.13 (lib/netstandard2.0/NetMQ.dll)

- https://github.com/zeromq/netmq
- License: GNU Lesser General Public License v3.0 (LGPL-3.0)
- Used as an unmodified, replaceable library binary; the application remains
  separable from the library per LGPL §4/§5.
- Copyright (c) 2010-2018 NetMQ contributors

### AsyncIO 0.1.69 (lib/netstandard2.0/AsyncIO.dll)

- https://github.com/somdoron/AsyncIO
- License: Mozilla Public License, version 2.0 (MPL-2.0)
- Used unmodified; MPL 2.0 file-level copyleft satisfied by shipping the
  unmodified library with its license text.
- Copyright (c) Somdoron Ltd.

### NaCl.Net 0.1.13 (lib/netstandard2.1/NaCl.dll)

- https://github.com/somdoron/NaCl.net
- License: Mozilla Public License, version 2.0 (MPL-2.0)
- NetMQ transitive dependency (CurveZMQ support); used unmodified with its
  license text (`LICENSE-NaCl.md`).
- Copyright (c) Somdoron Ltd.
