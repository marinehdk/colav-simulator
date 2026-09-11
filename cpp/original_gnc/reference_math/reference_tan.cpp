#if defined(__APPLE__) && (defined(__aarch64__) || defined(__arm64__))
#include "reference_trig_common.hpp"
#pragma clang fp contract(on)
#pragma GCC visibility push(hidden)
#define __FP_FAST_FMA 1
namespace original_gnc_glibc {
#include "glibc_upstream/branred.c"
#include "glibc_upstream/s_tan.c"
}
#undef max
#undef min
extern "C" __attribute__((visibility("hidden"))) double tan(double x) {
    return original_gnc_glibc::__tan(x);
}
#pragma GCC visibility pop
#endif
