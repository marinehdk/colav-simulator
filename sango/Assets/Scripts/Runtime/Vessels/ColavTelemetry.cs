using System;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M3 缝钉子③：compact-v1 遥测子集契约（spec #86；PHASE1-PLAN §8.3）。
    /// 后端 = gui_server/main.py WS /ws/sessions/{id}?transport=compact-v1：
    /// 信封仍是 schema_version "1.0" 文档，但 transport.schema_version = "colav.telemetry.compact@1"，
    /// 且每船剥掉 measurements/tracks/colav（main.py:166-192 _compact_stream_payload）。
    /// 必填字段按 compact 子集声明；全量字段一律可缺省（JsonUtility 未声明字段静默跳过）——
    /// 按 1.0 全量声明必填，阶段2 接真流即反序列化失败（PLAN §8 风险 5）。
    /// 本类只声明 twin 消费的子集：id、east/north（米）、psi（rad，北偏东顺时针）、sog（m/s）等。
    /// fixture：Assets/Tests/Fixtures/telemetry-sample.json（真实录制，provenance 见 evidence m3-build-log.md）。
    /// </summary>
    [Serializable]
    public class ColavTelemetry
    {
        /// <summary>信封 schema 版本（恒 "1.0"；冻结勿加字段，PLAN §8.3）。</summary>
        public string schema_version;

        public string run_id;

        /// <summary>单调步号；倒退 = 会话重建（PLAN §8.4 软对齐键）。</summary>
        public int seq;

        /// <summary>仿真秒。</summary>
        public double sim_time;

        /// <summary>会话状态（如 "RUNNING"）。</summary>
        public string state;

        /// <summary>传输层信封（compact-v1 专属）。</summary>
        public Transport transport;

        /// <summary>全船真值：truth[0] = 本船，其余 = 目标。</summary>
        public ShipEntry[] truth;

        /// <summary>回放状态（effective_multiplier 偏离 = 后端 realtime_limited，PLAN §8.3）。</summary>
        public Playback playback;

        [Serializable]
        public class Transport
        {
            /// <summary>恒 "colav.telemetry.compact@1"（gui_server/main.py:175）。</summary>
            public string schema_version;

            /// <summary>首条消息含静态字段（enc_navigation_area 等），其后为 false。</summary>
            public bool static_included;
        }

        [Serializable]
        public class ShipEntry
        {
            public int id;
            public int mmsi;

            /// <summary>船 长/宽（米）。</summary>
            public float length;
            public float width;

            /// <summary>本地平面坐标：东向/北向（米，ENC origin 系；main.py:1221-1222 north/east）。</summary>
            public float east;
            public float north;

            /// <summary>艏向 psi（rad，北偏东顺时针为正；main.py:1223）。</summary>
            public float psi;

            /// <summary>纵荡/横荡速度（m/s）。</summary>
            public float u;
            public float v;

            /// <summary>转艏角速度（rad/s）。</summary>
            public float r;

            /// <summary>航速/航向（对地；main.py:1227-1228）。</summary>
            public float sog;
            public float cog;

            /// <summary>是否在活跃时段内。</summary>
            public bool active;
        }

        [Serializable]
        public class Playback
        {
            public double requested_multiplier;
            public double effective_multiplier;
            public bool realtime_limited;
            public double scheduler_lag_ms;
        }

        public static ColavTelemetry FromJson(string json)
        {
            return JsonUtility.FromJson<ColavTelemetry>(json);
        }
    }
}
