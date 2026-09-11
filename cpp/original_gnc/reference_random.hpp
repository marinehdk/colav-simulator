#pragma once
#include <random>

namespace original_gnc {
// libstdc++ returns the y variate, then caches x; libc++ returns x, then
// caches y. Both use the same polar transform and consume the same engine
// words. Adapt pair delivery only; the original engine/seed/transform stay.
// This profile is verified against independently generated GCC vectors.
template<class Real = double> class ReferenceNormalDistribution {
public:
    ReferenceNormalDistribution(Real mean, Real standard_deviation)
        : distribution_(mean, standard_deviation) {}
    template<class Engine> Real operator()(Engine& engine) {
#ifdef _LIBCPP_VERSION
        if (cached_) { cached_ = false; return saved_; }
        saved_ = distribution_(engine);
        Real reference_first = distribution_(engine);
        cached_ = true;
        return reference_first;
#else
        return distribution_(engine);
#endif
    }
private:
    std::normal_distribution<Real> distribution_;
    bool cached_{false};
    Real saved_{0};
};
}
