#ifndef COLAV_MID_MPC_ORACLE_TRACE_HPP_
#define COLAV_MID_MPC_ORACLE_TRACE_HPP_

#include <casadi/casadi.hpp>

void oracle_capture_prepared(const casadi::DMDict& prepared);
void oracle_capture_result(const casadi::DMDict& result);

#endif
