#pragma once
#include <cmath>
#include <cfenv>
#include <cerrno>
#include <cfloat>
#include <cstdint>
namespace original_gnc_glibc {
struct ScopedRounding {
    int previous;
    explicit ScopedRounding(int mode): previous(std::fegetround()) {
        if (previous != mode) std::fesetround(mode);
    }
    ~ScopedRounding() { if (std::fegetround() != previous) std::fesetround(previous); }
};
}
