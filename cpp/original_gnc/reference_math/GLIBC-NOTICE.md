# Scoped reference math compatibility

Files under `glibc_upstream/` are unmodified glibc 2.35 sources. Exact URLs and SHA256 values are in `source-manifest.json`. Original copyright notices and LGPL-2.1-or-later terms are retained; `COPYING.LIB` is included. The separate Arm exp implementation under `upstream/` retains its own MIT notice and source manifest.

The reference host resolves some GNU functions to FMA implementations and others to non-FMA implementations. Darwin results and compiler contraction can differ by one ULP; the original closed loop can amplify those differences. Compatibility is confined to the original-GNC library. Original GNC gains, equations, thresholds and algorithm decisions are unchanged.

| Function | Apple ARM compilation matching the tested reference |
|---|---|
| standalone sin/cos, tan, atan/atan2 | `contract(on)`, expression-local contraction; tan/atan use the original explicit FMA helpers |
| asin/acos | `contract(fast)`, matching the reference FMA implementation |
| paired sincos | `contract(off)`, matching the reference non-FMA function |
| hypot | original non-FMA kernel, `contract(off)` |
| allocator exp | separate Arm/glibc-compatible FMA implementation; original non-FMA GNC translation units stay unchanged |

Clang may merge same-argument sin/cos calls into Darwin's `__sincos_stret` ABI. A hidden implementation forwards that ABI to the original GNU paired function. Paired and standalone cosine can differ by one ULP, so these are separate paths. Built-in substitutions are disabled for tan/atan/atan2/asin/acos/hypot.

Build-time C-to-C++ adaptations name the anonymous sin/cos table union, make its constant definition explicitly external, and redirect the paired function's include to the generated C++-compatible file. Table values and numerical expressions remain unchanged. Compatibility headers provide byte order, rounding restoration, underflow evaluation and private symbol annotations; they do not implement a ROS interface.

C symbols sin/cos/tan/atan/atan2/asin/acos/hypot and `__sincos_stret` are hidden on Apple ARM. The build checks the exported symbol table. Python and other backends continue using their original math functions. On Linux the system GNU functions are used; the final packaged-library acceptance reported here is for the tested Apple ARM build.

Seeded primitive checks, original-node replay, actual-library M/RHS/RK checks, and autonomous closures are separate evidence. Primitive probes alone do not qualify a complete backend. Exact observed remaining autonomous drift is reported in the fidelity report; it is not discarded or covered by widened tolerances.
