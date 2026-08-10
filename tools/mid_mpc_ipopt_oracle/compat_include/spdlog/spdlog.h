#ifndef COLAV_MID_MPC_ORACLE_SPDLOG_STUB_HPP_
#define COLAV_MID_MPC_ORACLE_SPDLOG_STUB_HPP_

namespace spdlog {

template <typename... Args>
void debug(const char*, Args&&...) {}
template <typename... Args>
void info(const char*, Args&&...) {}
template <typename... Args>
void warn(const char*, Args&&...) {}
template <typename... Args>
void error(const char*, Args&&...) {}
template <typename... Args>
void critical(const char*, Args&&...) {}

}  // namespace spdlog

#endif
