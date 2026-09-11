#pragma once
#define math_check_force_underflow_nonneg(value) do { if ((value) < DBL_MIN) { volatile double force_underflow = (value) * (value); (void)force_underflow; } } while (0)
#define math_check_force_underflow(value) math_check_force_underflow_nonneg(std::fabs(value))
