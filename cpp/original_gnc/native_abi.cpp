// Small C ABI; Python owns each independent kernel's lifecycle.
#include "native_factories.hpp"
#include <exception>
#include <string>

namespace {
thread_local std::string last_error;
thread_local std::string last_result;
}

extern "C" {
const char* original_gnc_error() { return last_error.c_str(); }

void* original_gnc_create(const char* module, const char* parameters, const char* options) noexcept {
    try {
        last_error.clear();
        auto kernel = original_gnc::make_kernel(module, original_gnc::Json::parse(parameters), original_gnc::Json::parse(options));
        return kernel.release();
    } catch (const std::exception& error) { last_error = error.what(); return nullptr; }
}

const char* original_gnc_describe(void* handle) noexcept {
    try {
        last_error.clear();
        if (!handle) throw std::runtime_error("Null original GNC handle");
        last_result = static_cast<original_gnc::KernelBase*>(handle)->describe().dump();
        return last_result.c_str();
    } catch (const std::exception& error) { last_error = error.what(); return nullptr; }
}

const char* original_gnc_invoke(void* handle, const char* function, const char* input, int64_t time_ns) noexcept {
    try {
        last_error.clear();
        if (!handle) throw std::runtime_error("Null original GNC handle");
        last_result = static_cast<original_gnc::KernelBase*>(handle)->invoke(function, original_gnc::Json::parse(input), time_ns).dump();
        return last_result.c_str();
    } catch (const std::exception& error) { last_error = error.what(); return nullptr; }
}

void original_gnc_destroy(void* handle) noexcept { delete static_cast<original_gnc::KernelBase*>(handle); }
}
