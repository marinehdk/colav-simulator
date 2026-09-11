#include <cmath>
#include <cstdint>
#include <cfloat>
#include <cerrno>

#if defined(__APPLE__) && (defined(__aarch64__) || defined(__arm64__))
// glibc 2.35's FMA exp and Arm v21.02 share the N=128/order-5 table and
// evaluation. Keep fusion confined to this translation unit. The source
// controller/PGD/Eigen translation units retain -ffp-contract=off.
#pragma clang fp contract(fast)
#define HAVE_FAST_ROUND 0
#define HAVE_FAST_LROUND 0
#define TOINT_INTRINSICS 0
#define USE_GLIBC_ABI 0
#define WANT_ERRNO 1
namespace original_gnc_reference_math {
#include "upstream/math_config.h"
#include "upstream/math_err.c"
#include "upstream/exp_data.c"
#include "upstream/exp.c"
}
#endif

namespace original_gnc {
double reference_exp(double value) {
#if defined(__APPLE__) && (defined(__aarch64__) || defined(__arm64__))
    return original_gnc_reference_math::exp(value);
#else
    return std::exp(value);
#endif
}
}
