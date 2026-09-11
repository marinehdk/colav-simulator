#if defined(__APPLE__) && (defined(__aarch64__) || defined(__arm64__))
#pragma GCC visibility push(hidden)
#include "reference_trig_common.hpp"
#pragma clang fp contract(fast)
namespace original_gnc_glibc {
#include "glibc_upstream/e_asin.c"
}
extern "C" __attribute__((visibility("hidden"))) double asin(double x) { return original_gnc_glibc::__ieee754_asin(x); }
extern "C" __attribute__((visibility("hidden"))) double acos(double x) { return original_gnc_glibc::__ieee754_acos(x); }
#pragma GCC visibility pop
#endif
