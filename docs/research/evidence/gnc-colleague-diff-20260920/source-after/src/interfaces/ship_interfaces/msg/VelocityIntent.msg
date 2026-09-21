# Ground-referenced velocity intent. No route is synthesized by the caller.
std_msgs/Header header
string intent_id
string parent_route_id
uint32 parent_route_revision
string behavior_mode
string command_source
float64 course_rad
float64 speed_mps
string speed_reference
builtin_interfaces/Time valid_until
