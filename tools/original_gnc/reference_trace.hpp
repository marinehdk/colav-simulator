// Reference-host instrumentation only. Never linked by the embedded library.
// Records actual callback inputs, clock reads, and published messages; replay
// supplies the recorded clock reads to the unchanged original algorithms.
#pragma once

#include <rclcpp/rclcpp.hpp>
#include <rclcpp/serialization.hpp>
#include <rclcpp/serialized_message.hpp>
#include <rosidl_runtime_cpp/traits.hpp>
#include <nlohmann/json.hpp>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>
#include <map>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

namespace original_reference_trace {
using Json = nlohmann::json;

inline std::string hex(const rclcpp::SerializedMessage& message) {
    constexpr char digits[] = "0123456789abcdef";
    const auto& bytes = message.get_rcl_serialized_message();
    std::string result(2 * bytes.buffer_length, '0');
    for (size_t i = 0; i < bytes.buffer_length; ++i) {
        result[2*i] = digits[bytes.buffer[i] >> 4];
        result[2*i+1] = digits[bytes.buffer[i] & 15];
    }
    return result;
}

template<class T> inline Json message_record(const T& message) {
    rclcpp::SerializedMessage serialized;
    rclcpp::Serialization<T> serializer;
    serializer.serialize_message(&message, &serialized);
    return {{"type", rosidl_generator_traits::name<T>()}, {"cdr_hex", hex(serialized)}};
}

template<class T> inline std::shared_ptr<T> decode(const Json& record) {
    const auto encoded = record.at("cdr_hex").get<std::string>();
    if (encoded.size() % 2) throw std::runtime_error("Odd CDR hex length");
    rclcpp::SerializedMessage buffer(encoded.size()/2);
    auto& bytes = buffer.get_rcl_serialized_message();
    bytes.buffer_length = encoded.size()/2;
    for (size_t i = 0; i < bytes.buffer_length; ++i)
        bytes.buffer[i] = static_cast<uint8_t>(std::stoul(encoded.substr(2*i, 2), nullptr, 16));
    auto result = std::make_shared<T>();
    rclcpp::Serialization<T> serializer;
    serializer.deserialize_message(&buffer, result.get());
    return result;
}

class Store {
public:
    Store() {
        const char* directory = std::getenv("ORIGINAL_GNC_TRACE_DIR");
        if (directory) { directory_ = directory; std::filesystem::create_directories(directory_); }
        const char* replay = std::getenv("ORIGINAL_GNC_REPLAY_FILE");
        if (replay) {
            std::ifstream stream(replay);
            if (!stream) throw std::runtime_error("Cannot read original reference trace");
            for (std::string line; std::getline(stream, line); ) expected_.push_back(Json::parse(line));
            replay_ = true;
        }
    }
    bool enabled() const { return replay_ || !directory_.empty(); }
    bool replaying() const { return replay_; }
    bool finished() const { return index_ == expected_.size(); }
    const Json& next() const {
        if (finished()) throw std::runtime_error("Reference replay exhausted");
        return expected_[index_];
    }
    void emit(const std::string& node, Json event) {
        if (!enabled()) return;
        event["node"] = node;
        if (replay_) {
            const auto expected = next();
            // CDR data are decoded and numerically compared by the Python
            // comparator; serialization padding is not a physical invariant.
            for (const char* key : {"kind", "node", "function", "site", "port"}) {
                if (expected.contains(key) && (!event.contains(key) || expected[key] != event[key])) {
                    failed_ = true;
                    failure_ = "Reference event mismatch at " + std::to_string(index_) + ": " + expected.dump() + " vs " + event.dump();
                    throw std::runtime_error(failure_);
                }
            }
            ++index_;
        }
        if (!directory_.empty()) {
            auto& stream = streams_[node];
            if (!stream.is_open()) stream.open(directory_ + "/" + node + ".jsonl", std::ios::out);
            event["ordinal"] = ordinals_[node]++;
            stream << event.dump() << '\n';
            if (event["kind"] == "return") stream.flush();
        }
    }
    void check() const { if (failed_) throw std::runtime_error(failure_); }
    size_t index() const { return index_; }
private:
    std::string directory_;
    std::map<std::string, std::ofstream> streams_;
    std::map<std::string, size_t> ordinals_;
    std::vector<Json> expected_;
    size_t index_{0};
    bool replay_{false};
    bool failed_{false};
    std::string failure_;
};

inline Store& store() { static Store instance; return instance; }

inline rclcpp::Time now(const rclcpp::Node* node, const char* site) {
    auto& trace = store();
    rclcpp::Time value = trace.replaying()
        ? rclcpp::Time(trace.next().at("nanoseconds").get<int64_t>(), RCL_ROS_TIME)
        : node->now();
    trace.emit(node->get_name(), {{"kind", "clock"}, {"site", site}, {"nanoseconds", value.nanoseconds()}});
    return value;
}

class Frame {
public:
    Frame(rclcpp::Node* node, const char* function, Json input = Json()) : node_(node), function_(function) {
        store().emit(node_->get_name(), {{"kind", "call"}, {"function", function_}, {"input", input}});
    }
    ~Frame() noexcept(false) {
        if (std::uncaught_exceptions() == 0)
            store().emit(node_->get_name(), {{"kind", "return"}, {"function", function_}});
    }
private:
    rclcpp::Node* node_;
    std::string function_;
};

template<class Publisher, class Message>
inline void publish(rclcpp::Node* node, const char* port, Publisher& publisher, const Message& message) {
    if (store().enabled()) store().emit(node->get_name(), {{"kind", "publish"}, {"port", port}, {"message", message_record(message)}});
    if (!store().replaying()) publisher->publish(message);
}
}  // namespace original_reference_trace
