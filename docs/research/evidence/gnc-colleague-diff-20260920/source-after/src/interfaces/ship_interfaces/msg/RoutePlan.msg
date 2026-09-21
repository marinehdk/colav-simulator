# 航线规划模块发送给 GNC 的完整航线。
# 坐标系：WGS84；所有非空数组下标必须一致。
std_msgs/Header header

# 必填坐标，单位为度。
float64[] latitude
float64[] longitude

# 可选数组；为空时由契约层补齐，非空时必须与坐标数组等长。
float64[] speed_limit_mps
string[] navigation_mode

# 航线元数据。
string route_id
uint32 route_revision
string route_type

# Set by the validated planner_trajectory_v1 admission path.
float64 trajectory_dt_s 0.0
float64 trajectory_valid_for_s 0.0
float64[] trajectory_course_deg
string trajectory_reference_id ""
