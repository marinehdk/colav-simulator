#if defined(__APPLE__) && (defined(__aarch64__) || defined(__arm64__))
#include "reference_trig_common.hpp"
#pragma clang fp contract(on)
#pragma GCC visibility push(hidden)
namespace original_gnc_glibc {
#include "glibc_cpp/s_sin.inc"
}
#undef max
#undef min
extern "C" __attribute__((visibility("hidden"))) double sin(double x) {
    return original_gnc_glibc::__sin(x);
}
extern "C" __attribute__((visibility("hidden"))) double cos(double x) {
    return original_gnc_glibc::__cos(x);
}
#pragma GCC visibility pop
#endif
