// Lossless value semantics for native boundary records. JSON null is never
// silently interpreted as a numerical zero or an optional NaN sentinel.
#pragma once
#include <nlohmann/json.hpp>
#include <array>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <type_traits>
#include <vector>

namespace original_gnc {
template<class T> struct vector_value : std::false_type {};
template<class T, class Allocator> struct vector_value<std::vector<T,Allocator>> : std::true_type {};
template<class T> struct array_value : std::false_type {};
template<class T, size_t N> struct array_value<std::array<T,N>> : std::true_type {};

template<class T> nlohmann::json encode_value(const T& value) {
    if constexpr (std::is_floating_point_v<T>) {
        if (std::isfinite(value)) return nlohmann::json(value);
        return {{"$nonfinite", std::isnan(value) ? "nan" : (value > 0 ? "+inf" : "-inf")}};
    } else if constexpr (vector_value<T>::value || array_value<T>::value) {
        nlohmann::json result = nlohmann::json::array();
        for (size_t i=0; i<value.size(); ++i) result.push_back(encode_value<typename T::value_type>(value[i]));
        return result;
    } else return nlohmann::json(value);
}

template<class T> T decode_value(const nlohmann::json& value) {
    if constexpr (std::is_floating_point_v<T>) {
        if (value.is_number()) return value.get<T>();
        if (value.is_object() && value.size()==1 && value.contains("$nonfinite")) {
            const auto tag = value.at("$nonfinite").get<std::string>();
            if (tag=="nan") return std::numeric_limits<T>::quiet_NaN();
            if (tag=="+inf") return std::numeric_limits<T>::infinity();
            if (tag=="-inf") return -std::numeric_limits<T>::infinity();
        }
        throw std::runtime_error("Expected a number or explicit original nonfinite sentinel");
    } else if constexpr (vector_value<T>::value || array_value<T>::value) {
        if (!value.is_array()) throw std::runtime_error("Expected a native array");
        T result;
        if constexpr (vector_value<T>::value) result.resize(value.size());
        else if (value.size()!=result.size()) throw std::runtime_error("Native fixed array has the wrong size");
        for (size_t i=0; i<result.size(); ++i) result[i]=decode_value<typename T::value_type>(value[i]);
        return result;
    } else return value.get<T>();
}
}
