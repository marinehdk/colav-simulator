// Native data/time/parameter interfaces for extracted original GNC algorithms.
// There is no ROS node, executor, DDS, service, or background timer here.
#pragma once
#include "reference_random.hpp"
#include "reference_exp.hpp"

#include "native_messages.hpp"
#include <tf2/LinearMath/Quaternion.h>
#include <tf2/LinearMath/Matrix3x3.h>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <functional>
#include <limits>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

namespace original_gnc {
using Json = nlohmann::json;
enum class ClockType { Ros = 1, System = 2, Steady = 3 };

class Duration {
public:
    explicit Duration(int64_t ns = 0) : ns_(ns) {}
    Duration(int32_t sec, uint32_t ns) : ns_(int64_t(sec) * 1000000000LL + ns) {}
    static Duration from_seconds(double value) {
        if (!std::isfinite(value) || std::abs(value) > double(std::numeric_limits<int64_t>::max()) / 1e9)
            throw std::overflow_error("Duration out of range");
        return Duration(static_cast<int64_t>(value * 1e9));
    }
    static Duration from_nanoseconds(int64_t value) { return Duration(value); }
    int64_t nanoseconds() const { return ns_; }
    double seconds() const { return std::chrono::duration<double>(std::chrono::nanoseconds(ns_)).count(); }
private:
    int64_t ns_;
};

class Time {
public:
    explicit Time(int64_t ns = 0, ClockType type = ClockType::System) : ns_(ns), type_(type) {}
    Time(int32_t sec, uint32_t ns, ClockType type = ClockType::System)
        : Time(int64_t(sec) * 1000000000LL + ns, type) {
        if (sec < 0) throw std::runtime_error("Negative timestamp seconds");
    }
    Time(const messages::builtin_interfaces::Time& stamp, ClockType type = ClockType::Ros)
        : Time(stamp.sec, stamp.nanosec, type) {}
    int64_t nanoseconds() const { return ns_; }
    double seconds() const { return std::chrono::duration<double>(std::chrono::nanoseconds(ns_)).count(); }
    ClockType get_clock_type() const { return type_; }
    operator messages::builtin_interfaces::Time() const {
        messages::builtin_interfaces::Time result;
        const auto division = std::div(ns_, int64_t(1000000000));
        result.sec = int32_t(division.quot - (division.rem < 0));
        result.nanosec = uint32_t(division.rem < 0 ? division.rem + 1000000000 : division.rem);
        return result;
    }
    Duration operator-(const Time& other) const {
        same_source(other);
        return Duration(checked_difference(ns_, other.ns_));
    }
    Time operator+(const Duration& value) const { return Time(checked_sum(ns_, value.nanoseconds()), type_); }
    Time operator-(const Duration& value) const { return Time(checked_difference(ns_, value.nanoseconds()), type_); }
    Time& operator+=(const Duration& value) { *this = *this + value; return *this; }
    bool operator==(const Time& other) const { same_source(other); return ns_ == other.ns_; }
    bool operator!=(const Time& other) const { return !(*this == other); }
    bool operator<(const Time& other) const { same_source(other); return ns_ < other.ns_; }
    bool operator<=(const Time& other) const { same_source(other); return ns_ <= other.ns_; }
    bool operator>(const Time& other) const { return other < *this; }
    bool operator>=(const Time& other) const { return other <= *this; }
private:
    void same_source(const Time& other) const {
        if (type_ != other.type_) throw std::runtime_error("Different timestamp sources");
    }
    static int64_t checked_sum(int64_t a, int64_t b) {
        if ((b > 0 && a > INT64_MAX - b) || (b < 0 && a < INT64_MIN - b))
            throw std::overflow_error("Timestamp addition overflow");
        return a + b;
    }
    static int64_t checked_difference(int64_t a, int64_t b) {
        if ((b < 0 && a > INT64_MAX + b) || (b > 0 && a < INT64_MIN + b))
            throw std::overflow_error("Timestamp subtraction overflow");
        return a - b;
    }
    int64_t ns_;
    ClockType type_;
};

class StepClock {
public:
    void configure(const Json& options) {
        current_ns_ = options.value("time_ns", int64_t(0));
        if (options.contains("replay_clocks")) {
            replay_ = options.at("replay_clocks");
            replay_enabled_ = true;
        }
        for (const auto& site : options.value("omitted_log_clock_sites", Json::array())) omitted_sites_.insert(site.get<std::string>());
    }
    void set(int64_t value) { current_ns_ = value; }
    int64_t current() const { return current_ns_; }
    Time read(const char* site) {
        if (!replay_enabled_) return Time(current_ns_, ClockType::Ros);
        while (cursor_ < replay_.size() && omitted_sites_.count(replay_[cursor_].at("site").get<std::string>())) ++cursor_;
        if (cursor_ >= replay_.size() || replay_[cursor_].at("site") != site)
            throw std::runtime_error(std::string("Native clock read differs at ") + site + " index " + std::to_string(cursor_));
        return Time(replay_[cursor_++].at("nanoseconds").get<int64_t>(), ClockType::Ros);
    }
    size_t reads_consumed() const { return cursor_; }
    size_t required_reads_remaining() const {
        size_t remaining = 0;
        for (size_t i = cursor_; i < replay_.size(); ++i)
            remaining += !omitted_sites_.count(replay_[i].at("site").get<std::string>());
        return remaining;
    }
private:
    int64_t current_ns_{0};
    Json replay_;
    size_t cursor_{0};
    bool replay_enabled_{false};
    std::set<std::string> omitted_sites_;
};

enum class ParameterType {
    PARAMETER_NOT_SET=0, PARAMETER_BOOL=1, PARAMETER_INTEGER=2, PARAMETER_DOUBLE=3,
    PARAMETER_STRING=4, PARAMETER_BYTE_ARRAY=5, PARAMETER_BOOL_ARRAY=6,
    PARAMETER_INTEGER_ARRAY=7, PARAMETER_DOUBLE_ARRAY=8, PARAMETER_STRING_ARRAY=9
};

template<class T> constexpr ParameterType parameter_type() {
    if constexpr (std::is_same_v<T, bool>) return ParameterType::PARAMETER_BOOL;
    else if constexpr (std::is_integral_v<T>) return ParameterType::PARAMETER_INTEGER;
    else if constexpr (std::is_floating_point_v<T>) return ParameterType::PARAMETER_DOUBLE;
    else if constexpr (std::is_same_v<T, std::string>) return ParameterType::PARAMETER_STRING;
    else if constexpr (std::is_same_v<T, std::vector<double>>) return ParameterType::PARAMETER_DOUBLE_ARRAY;
    else if constexpr (std::is_same_v<T, std::vector<int64_t>>) return ParameterType::PARAMETER_INTEGER_ARRAY;
    else if constexpr (std::is_same_v<T, std::vector<std::string>>) return ParameterType::PARAMETER_STRING_ARRAY;
    else if constexpr (std::is_same_v<T, std::vector<bool>>) return ParameterType::PARAMETER_BOOL_ARRAY;
    else if constexpr (std::is_same_v<T, std::vector<uint8_t>>) return ParameterType::PARAMETER_BYTE_ARRAY;
    else static_assert(!sizeof(T), "Unsupported native parameter type");
}

class Parameter {
public:
    Parameter() = default;
    Parameter(std::string name, ParameterType type, Json value) : name_(std::move(name)), type_(type), value_(std::move(value)) {}
    template<class T> Parameter(std::string name, const T& value) : Parameter(std::move(name), parameter_type<T>(), Json(value)) {}
    const std::string& get_name() const { return name_; }
    ParameterType get_type() const { return type_; }
    template<class T> T get_value() const {
        if (type_ != parameter_type<T>()) throw std::runtime_error("Native parameter type mismatch: " + name_);
        return value_.get<T>();
    }
    double as_double() const { return get_value<double>(); }
    int64_t as_int() const { return get_value<int64_t>(); }
    bool as_bool() const { return get_value<bool>(); }
    std::string as_string() const { return get_value<std::string>(); }
    std::vector<double> as_double_array() const { return get_value<std::vector<double>>(); }
    std::vector<std::string> as_string_array() const { return get_value<std::vector<std::string>>(); }
    std::vector<int64_t> as_integer_array() const { return get_value<std::vector<int64_t>>(); }
    Json record() const { return {{"type", static_cast<int>(type_)}, {"value", value_}}; }
private:
    std::string name_;
    ParameterType type_{ParameterType::PARAMETER_NOT_SET};
    Json value_;
};

class Parameters {
public:
    explicit Parameters(Json overrides = Json::object()) : overrides_(std::move(overrides)) {}
    template<class T> T declare_value(const std::string& name, const T& default_value) {
        if (declared_.count(name)) throw std::runtime_error("Native parameter already declared: " + name);
        Parameter value(name, default_value);
        if (overrides_.contains(name)) {
            const auto& record = overrides_.at(name);
            value = Parameter(name, static_cast<ParameterType>(record.at("type").get<int>()), record.at("value"));
        }
        auto result = value.get_value<T>();
        declared_.emplace(name, std::move(value));
        return result;
    }
    std::string declare_value(const std::string& name, const char* value) { return declare_value(name, std::string(value)); }
    const Parameter& get(const std::string& name) const {
        const auto found = declared_.find(name);
        if (found == declared_.end()) throw std::runtime_error("Undeclared native parameter: " + name);
        return found->second;
    }
    bool has(const std::string& name) const { return declared_.count(name); }
    template<class T> bool get_or(const std::string& name, T& output, const T& fallback) const {
        output = has(name) ? get(name).get_value<T>() : fallback;
        return has(name);
    }
    using Validator = std::function<messages::rcl_interfaces::SetParametersResult(const std::vector<Parameter>&)>;
    void set_validator(Validator callback) { validator_ = std::move(callback); }
    Json snapshot() const {
        Json result = Json::object();
        for (const auto& item : declared_) result[item.first] = item.second.record();
        return result;
    }
private:
    Json overrides_;
    std::map<std::string, Parameter> declared_;
    Validator validator_;
};

struct Context {
    Context(std::string module_name, const Json& parameters, const Json& options)
        : name(std::move(module_name)), parameters(parameters), assets(options.value("package_roots", Json::object())),
          asset_paths(options.value("asset_paths", Json::object())) {
        clock.configure(options);
    }
    std::string name;
    Parameters parameters;
    StepClock clock;
    Json assets;
    Json asset_paths;
    Json outputs = Json::array();
    Json ports = Json::object();
    Json inputs = Json::object();
    Json timers = Json::object();
    Json timer_descriptors = Json::object();
    Json timer_updates = Json::array();
    std::map<std::string, std::string> timer_handles;
    uint64_t timer_generation{0};
    void bind_input(const char* callback, std::string topic, const char* type, bool latched) {
        inputs[callback] = {{"topic",std::move(topic)},{"type",type},{"latched",latched}};
    }
    void set_timer(const char* handle, const char* callback, int64_t period_ns) {
        if (period_ns <= 0) throw std::runtime_error("Original timer period is not positive");
        timer_handles[handle] = callback;
        timers[callback] = period_ns;
        Json descriptor = {{"callback",callback},{"handle",handle},{"period_ns",period_ns},
                           {"created_ns",clock.current()},{"generation",++timer_generation},{"active",true}};
        timer_descriptors[callback] = descriptor;
        timer_updates.push_back(descriptor);
    }
    bool timer_active(const char* handle) const { return timer_handles.count(handle); }
    void cancel_timer(const char* handle) {
        auto found = timer_handles.find(handle);
        if (found == timer_handles.end()) return;
        const auto callback = found->second;
        Json descriptor = timer_descriptors.at(callback);
        descriptor["active"] = false;
        timer_updates.push_back(descriptor);
        timer_descriptors.erase(callback);
        timers.erase(callback);
        timer_handles.erase(found);
    }
    std::string package_root(const std::string& package) const {
        if (!assets.contains(package)) throw std::runtime_error("Missing original asset root: " + package);
        return assets.at(package).get<std::string>();
    }
    std::string asset_path(const std::string& path) const {
        return asset_paths.contains(path) ? asset_paths.at(path).get<std::string>() : path;
    }
};

template<class Message> class Output {
public:
    explicit operator bool() const { return context_ != nullptr; }
    void bind(Context& context, const char* port, std::string topic, bool latched = false) {
        context_ = &context; port_ = port; topic_ = std::move(topic); latched_ = latched;
        context.ports[port_] = {{"topic", topic_}, {"type", Message::type_name}, {"latched", latched_}};
    }
    void emit(const Message& value) {
        if (!context_) throw std::runtime_error("Unbound native output");
        context_->outputs.push_back({{"node", context_->name}, {"port", port_}, {"topic", topic_},
            {"message", {{"type", Message::type_name}, {"fields", Json(value)}}}});
    }
private:
    Context* context_{nullptr};
    std::string port_, topic_;
    bool latched_{false};
};

class ModuleBase {
public:
    explicit ModuleBase(Context& context) : context_(context), parameters_(context.parameters), clock_(context.clock) {}
    virtual ~ModuleBase() = default;
protected:
    Context& context_;
    Parameters& parameters_;
    StepClock& clock_;
};

inline messages::geometry_msgs::Quaternion to_message(const tf2::Quaternion& value) {
    messages::geometry_msgs::Quaternion result;
    result.x=value.x(); result.y=value.y(); result.z=value.z(); result.w=value.w();
    return result;
}
inline void from_message(const messages::geometry_msgs::Quaternion& value, tf2::Quaternion& output) {
    output.setValue(value.x, value.y, value.z, value.w);
}

class KernelBase {
public:
    virtual ~KernelBase() = default;
    virtual Json invoke(const std::string& function, const Json& input, int64_t time_ns) = 0;
    virtual Json describe() const = 0;
};

template<class Module> struct Kernel : KernelBase {
    Kernel(std::string name, const Json& parameters, const Json& options)
        : context(std::move(name), parameters, options), module(std::make_unique<Module>(context)) {}
    Json invoke(const std::string& function, const Json& input, int64_t time_ns) override;
    Json snapshot() const;
    Json describe() const override {
        return {{"parameters", context.parameters.snapshot()}, {"ports", context.ports}, {"inputs",context.inputs},
                {"timers", context.timers}, {"initial_outputs", context.outputs}, {"state",snapshot()},
                {"timer_descriptors",context.timer_descriptors},
                {"required_clock_reads_remaining",context.clock.required_reads_remaining()}};
    }
    Context context;
    std::unique_ptr<Module> module;
};
} // namespace original_gnc
