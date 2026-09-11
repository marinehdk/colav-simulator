// Match the frozen x86-64 reference's separate multiply/add packet operations.
// Original PGD is sensitive to FMA rounding; preserve SIMD reduction order.
// This profile is confined to the independent original GNC library.
#pragma once
#if defined(__aarch64__) || defined(__arm64__)
#include <arm_neon.h>
#pragma push_macro("__ARM_FEATURE_FMA")
#undef __ARM_FEATURE_FMA
#include <Eigen/Core>
#pragma pop_macro("__ARM_FEATURE_FMA")
#endif
