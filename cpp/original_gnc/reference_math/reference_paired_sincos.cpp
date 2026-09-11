#if defined(__APPLE__) && (defined(__aarch64__) || defined(__arm64__))
#include "reference_trig_common.hpp"
#pragma clang fp contract(off)
#pragma GCC visibility push(hidden)
namespace original_gnc_glibc {
#include "glibc_cpp/s_sincos.inc"
}
#undef max
#undef min
extern "C" __attribute__((visibility("hidden"))) struct __double2 __sincos_stret(double x) {
    struct __double2 result;
    original_gnc_glibc::__sincos(x, &result.__sinval, &result.__cosval);
    return result;
}
#pragma GCC visibility pop
#endif
