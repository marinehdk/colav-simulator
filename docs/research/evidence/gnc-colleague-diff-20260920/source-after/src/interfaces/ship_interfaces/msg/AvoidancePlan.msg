std_msgs/Header header

# 避碰计划必须绑定当前活动名义航线及其版本。
string plan_id
string parent_route_id
uint32 parent_route_revision
string behavior_mode
string command_source

float64[] latitude
float64[] longitude
float64[] command_speed_mps
float64[] command_heading_deg
string[] navigation_mode

builtin_interfaces/Time valid_until
bool require_exact_heading
bool require_exact_speed
bool allow_degraded_execution

bool has_return_to_route_point
float64 return_latitude
float64 return_longitude

# Explicit timed-trajectory contract; zero/empty keeps the legacy route API.
float64 trajectory_dt_s 0.0
string trajectory_reference_id ""
