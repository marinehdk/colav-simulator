"""Expose actual original ROS nodes as synchronous test kernels, without an embedded library."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

import build_reference_replay as replay
from instrument_reference import closing, code_mask

PROTOCOL_SUPPORT = r"""
inline int64_t& explicit_time_ns() { static int64_t value = 2000000000000000000LL; return value; }
inline bool protocol_enabled() { return std::getenv("ORIGINAL_GNC_PROTOCOL") != nullptr; }
struct Protocol {
    Json inputs=Json::object(), timers=Json::object();
    Json outputs=Json::array(), timer_updates=Json::array();
    std::map<std::string,std::string> handles;
    uint64_t generation=0;
};
inline Protocol& protocol() { static Protocol value; return value; }
template<class Subscription>
inline void observe_subscription(const char* callback, Subscription& sub, const char* type) {
    protocol().inputs[callback]={{"topic",sub->get_topic_name()},{"type",type},
        {"latched",sub->get_actual_qos().get_rmw_qos_profile().durability==RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL}};
}
template<class Timer>
inline void observe_timer(const char* handle, const char* callback, Timer& timer) {
    int64_t period=0;
    if(rcl_timer_get_period(timer->get_timer_handle().get(),&period)!=RCL_RET_OK)
        throw std::runtime_error("Cannot observe actual original timer period");
    auto& state=protocol(); state.handles[handle]=callback;
    Json descriptor={{"callback",callback},{"handle",handle},{"period_ns",period},
        {"created_ns",explicit_time_ns()},{"generation",++state.generation},{"active",true}};
    state.timers[callback]=descriptor; state.timer_updates.push_back(descriptor);
}
inline void observe_cancel(const char* handle) {
    auto& state=protocol(); auto found=state.handles.find(handle);
    if(found==state.handles.end()) return;
    Json value=state.timers.at(found->second); value["active"]=false;
    state.timer_updates.push_back(value); state.timers.erase(found->second); state.handles.erase(found);
}
"""


def wiring(text: str) -> tuple[str, list[dict]]:
    """Observe real subscription topics and real timer periods at registration."""
    mask = code_mask(text)
    edits = []
    records = []
    pattern = r"\b(\w+)\s*=\s*(?:this->)?(create_subscription|create_wall_timer)(?:<([^>]+)>)?\s*\("
    for match in re.finditer(pattern, mask):
        opening = mask.index("(", match.start())
        end = closing(mask, opening)
        statement_end = mask.index(";", end) + 1
        body = mask[opening:end]
        callback = re.search(r"std::bind\s*\(\s*&[\w:]+::(\w+)", body)
        if callback is None:
            raise ValueError("Unrecognized original callback registration")
        handle, kind, message = match[1], match[2], match[3]
        name = callback[1]
        if kind == "create_subscription":
            hook = (
                f'\n    original_reference_trace::observe_subscription("{name}",{handle},'
                f"rosidl_generator_traits::name<{message}>());"
            )
        else:
            hook = f'\n    original_reference_trace::observe_timer("{handle}","{name}",{handle});'
        edits.append((statement_end, hook))
        records.append({"kind": kind, "handle": handle, "callback": name})
    for match in re.finditer(r"\b(\w+)\s*->\s*cancel\s*\(\s*\)\s*;", mask):
        edits.append((match.end(), f'\n    original_reference_trace::observe_cancel("{match[1]}");'))
    for at, extra in sorted(edits, reverse=True):
        text = text[:at] + extra + text[at:]
    return text, records


def driver(source: Path, callbacks: list[dict]) -> str:
    """Dispatch only original callbacks; return observations over a test-only pipe."""
    branches = []
    for callback in callbacks:
        name, message = callback["function"], callback["message_type"]
        arg = f'original_reference_trace::decode<{message}>(command.at("input"))' if message else ""
        branches.append(f'if(function=="{name}") node->{name}({arg});')
    chain = (
        "\n            else ".join(branches)
        + '\n            else throw std::runtime_error("Unknown original callback: "+function);'
    )
    return f'''#define main unused_original_main
#include "{source}"
#undef main
{replay.PARAMETER_CHECK}
using Json=nlohmann::json;
Json state(const {replay.CLASS_NAMES[source.name]}& node) {{
{replay.SNAPSHOTS[source.stem]}
}}
int main(int argc,char** argv) {{
    try {{
        if(argc!=3) throw std::runtime_error("expected node-name and parameters YAML");
        std::string remap=std::string("__node:=")+argv[1];
        const char* arguments[]={{"source-kernel","--ros-args","--params-file",argv[2],
            "-r",remap.c_str(),"--log-level","error"}};
        rclcpp::init(8,arguments);
        auto node=std::make_shared<{replay.CLASS_NAMES[source.name]}>();
        check_parameters(node.get(),std::string(argv[2])+".typed.json");
        auto& observed=original_reference_trace::protocol();
        std::cout << "ORIGINAL_READY " << Json({{{{"inputs",observed.inputs}},{{"timer_descriptors",observed.timers}},
            {{"initial_outputs",observed.outputs}},{{"state",state(*node)}}}}).dump() << std::endl;
        for(std::string line;std::getline(std::cin,line);) {{
            Json command=Json::parse(line);auto function=command.at("function").get<std::string>();
            original_reference_trace::explicit_time_ns()=command.at("time_ns").get<int64_t>();
            observed.outputs=Json::array();observed.timer_updates=Json::array();
            {chain}
            std::cout << "ORIGINAL_RESULT " << Json({{
                {{"outputs",observed.outputs}},{{"timer_updates",observed.timer_updates}},
                {{"state",state(*node)}}}}).dump() << std::endl;
        }}
        node.reset();rclcpp::shutdown();return 0;
    }} catch(const std::exception& error) {{ std::cerr << error.what() << std::endl;return 1; }}
}}
'''


def build(workspace: Path, output: Path) -> None:
    """Keep original bodies; add isolated read-only plumbing and compile independently."""
    if output.exists():
        raise FileExistsError(output)
    staging = output / "source"
    shutil.copytree(workspace / "src", staging / "src")
    old_header = workspace / "original_reference_trace.hpp"
    header = old_header.read_text()
    header = header.replace("class Store {", PROTOCOL_SUPPORT + "\nclass Store {")
    header = header.replace(
        "return replay_ || !directory_.empty();", "return replay_ || !directory_.empty() || protocol_enabled();"
    )
    header = header.replace(
        'event["node"] = node;',
        'event["node"] = node;\n        '
        'if(protocol_enabled() && event.at("kind")=="publish") protocol().outputs.push_back(event);',
    )
    header = header.replace(
        ": node->now();", ": (protocol_enabled() ? rclcpp::Time(explicit_time_ns(),RCL_ROS_TIME) : node->now());"
    )
    header = header.replace(
        '{"message", message_record(message)}});',
        '{"message", message_record(message)}, {"topic",publisher->get_topic_name()}});',
    )
    header = header.replace(
        "if (!store().replaying()) publisher->publish(message);",
        "if (!store().replaying() && !protocol_enabled()) publisher->publish(message);",
    )
    target_header = staging / "coupled_reference_trace.hpp"
    target_header.write_text(header)
    manifest = json.loads((workspace / "instrumentation.json").read_text())
    observations = {}
    for item in manifest["files"]:
        original = Path(item["file"])
        target = staging / original.relative_to(workspace)
        text = target.read_text().replace(str(old_header), str(target_header))
        transformed, records = wiring(text)
        target.write_text(transformed)
        item["file"] = str(target)
        observations[target.name] = {
            "registration_hooks": records,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        }
    (staging / "instrumentation.json").write_text(json.dumps(manifest, indent=2))
    replay.driver = driver
    replay.build(staging, output / "drivers", [Path(item["file"]).stem for item in manifest["files"]])
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "scope": "independently compiled actual original ROS nodes, synchronous test ports",
                "source_workspace": str(workspace),
                "embedded_library_used": False,
                "embedded_algorithm_files_used": False,
                "header_sha256": hashlib.sha256(target_header.read_bytes()).hexdigest(),
                "source_observations": observations,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.workspace.resolve(), args.output.resolve())
