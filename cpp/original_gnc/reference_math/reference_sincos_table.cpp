#if defined(__APPLE__) && (defined(__aarch64__) || defined(__arm64__))
#pragma GCC visibility push(hidden)
namespace original_gnc_glibc {
#include "glibc_cpp/sincostab.inc"
}
#pragma GCC visibility pop
#endif
