#if defined(__APPLE__) && (defined(__aarch64__) || defined(__arm64__))
#pragma GCC visibility push(hidden)
#include "reference_trig_common.hpp"
#pragma clang fp contract(off)
#undef __FP_FAST_FMA
#define strong_alias(a,b)
#define __glibc_unlikely(x) __builtin_expect(!!(x),0)
namespace original_gnc_glibc {
#include "glibc_upstream/e_hypot.c"
}
extern "C" __attribute__((visibility("hidden"))) double hypot(double x,double y) { return original_gnc_glibc::__hypot(x,y); }
#pragma GCC visibility pop
#endif
