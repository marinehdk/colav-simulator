#if defined(__APPLE__) && (defined(__aarch64__) || defined(__arm64__))
#include "reference_trig_common.hpp"
#pragma clang fp contract(on)
#pragma GCC visibility push(hidden)
#define __FP_FAST_FMA 1
namespace original_gnc_glibc {
#include "glibc_upstream/e_atan2.c"
}
extern "C" __attribute__((visibility("hidden"))) double atan2(double y, double x) {
    return original_gnc_glibc::__ieee754_atan2(y,x);
}
#pragma GCC visibility pop
#endif
