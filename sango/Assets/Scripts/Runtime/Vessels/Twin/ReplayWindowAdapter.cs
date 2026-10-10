using System;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// sealed 回放 window REST → compact 同款位姿管线适配层（P2-S1 spec #89；纯映射）。
    /// 数据源 = GET /api/runs/{run_id}/replay/window?from&to（gui_server/replay.py window()，
    /// schema "colav.run-replay.window@1"）+ GET .../replay/context（ships 静态尺寸）。
    /// window 帧形状 ≠ compact 信封（R3 风险，00-REPORT.md §7）：
    ///   frames[].payload.ShipN.state = [north, east, psi, u, v, r]（main 侧 NE 序），
    ///   csog_state = [north, east, sog, cog]；length/width 只在 context.ships（length_m/width_m）。
    /// 归一目标 = 既有 ColavTelemetry（seq=sim_time 步号、truth[]、playback 1×），
    /// 使 TwinClock/TwinPose/TwinSessionDriver 一套管线同时吃 live 与 sealed 两路（零分支）。
    /// JsonUtility 无字典：payload 动态键 "ShipN" 以固定槽位 Ship0..Ship{Max-1} 声明，
    /// 缺席槽位为 null 即跳过（上界 MaxPayloadShips，覆盖 romsdal_busy_water_16 的 16 船）。
    /// </summary>
    public static class ReplayWindowAdapter
    {
        /// <summary>payload 船槽上界（含本船）。场景船数超界时多余船静默不入管线。</summary>
        public const int MaxPayloadShips = 16;

        public static ReplayWindowDocument WindowFromJson(string json)
            => JsonUtility.FromJson<ReplayWindowDocument>(json);

        public static ReplayStaticContext ContextFromJson(string json)
            => JsonUtility.FromJson<ReplayStaticContext>(json);

        /// <summary>
        /// 单个 window 帧 + 静态上下文 → ColavTelemetry（truth 按 ShipN 序）。
        /// state/csog_state 形状不齐（缺数组/短数组）的船跳过——密封证据不脑补。
        /// playback 恒 1×：sealed 回放的倍率由消费方时钟控制（compact 的
        /// effective_multiplier 语义属于 live 后端调度，replay 无此概念）。
        /// </summary>
        public static ColavTelemetry ToTelemetry(ReplayFrame frame, ReplayStaticContext context)
        {
            if (frame == null) return null;
            var telemetry = new ColavTelemetry
            {
                schema_version = "1.0",
                run_id = null,
                seq = frame.sequence,
                sim_time = frame.sim_time,
                state = frame.state,
                playback = new ColavTelemetry.Playback
                {
                    requested_multiplier = 1.0,
                    effective_multiplier = 1.0,
                    realtime_limited = false,
                    scheduler_lag_ms = 0.0,
                },
                truth = Empty(),
                environment = context?.environment,
            };
            var slots = frame.Slots();
            var truth = new ColavTelemetry.ShipEntry[slots.Length];
            int count = 0;
            foreach (var slot in slots)
            {
                var entry = ToEntry(slot, context);
                if (entry != null)
                {
                    if (entry.id == 0 && frame.gnc_balance != null)
                    { entry.has_roll = true; entry.roll_rad = frame.gnc_balance.roll_deg * Mathf.Deg2Rad; }
                    truth[count++] = entry;
                }
            }
            Array.Resize(ref truth, count);
            telemetry.truth = truth;
            return telemetry;
        }

        /// <summary>payload.ShipN → ShipEntry（north=state[0]、east=state[1]、psi=state[2]…）。</summary>
        public static ColavTelemetry.ShipEntry ToEntry(ReplayShipSlot slot, ReplayStaticContext context)
        {
            if (slot == null || slot.state == null || slot.state.Length < 3) return null;
            var statics = context != null && context.ships != null ? context.ships : null;
            float length = 0f, width = 0f;
            if (statics != null)
                foreach (var ship in statics)
                    if (ship != null && ship.id == slot.id) { length = ship.length_m; width = ship.width_m; break; }
            double sog = slot.csog_state != null && slot.csog_state.Length > 2 ? slot.csog_state[2] : 0.0;
            double cog = slot.csog_state != null && slot.csog_state.Length > 3 ? slot.csog_state[3] : 0.0;
            return new ColavTelemetry.ShipEntry
            {
                id = slot.id,
                mmsi = slot.mmsi,
                length = length,
                width = width,
                east = slot.state[1],
                north = slot.state[0],
                psi = (float)slot.state[2],
                u = slot.state.Length > 3 ? (float)slot.state[3] : 0f,
                v = slot.state.Length > 4 ? (float)slot.state[4] : 0f,
                r = slot.turn_rate,
                sog = (float)sog,
                cog = (float)cog,
                active = slot.active,
                has_roll = slot.original_gnc?.state_8d?.Length == 8,
                roll_rad = slot.original_gnc?.state_8d?.Length == 8 ? (float)slot.original_gnc.state_8d[2] : 0f,
            };
        }

        static ColavTelemetry.ShipEntry[] Empty() => Array.Empty<ColavTelemetry.ShipEntry>();
    }

    /// <summary>window 响应文档（只声明 twin 消费子集；未知字段 JsonUtility 静默跳过）。</summary>
    [Serializable]
    public class ReplayWindowDocument
    {
        public string schema_version;
        public string run_id;
        public ReplayFrame[] frames;
    }

    /// <summary>逐帧记录：sequence 即 compact 的 seq、sim_time 同义；payload 内是 ShipN 槽位。</summary>
    [Serializable]
    public class ReplayFrame
    {
        public int sequence;
        public double sim_time;
        public string state;
        public ReplayShipPayload payload;
        public ReplayRecordedBalance gnc_balance;

        /// <summary>非空槽位按 ShipN 序返回（replay-source.js localShips 同序约定）。</summary>
        public ReplayShipSlot[] Slots()
        {
            return payload != null ? payload.Slots() : new ReplayShipSlot[0];
        }
    }

    /// <summary>
    /// frames[].payload 动态键容器：JsonUtility 无字典，"ShipN" 以固定槽位声明
    /// （缺席槽位 null 即跳过；上界 ReplayWindowAdapter.MaxPayloadShips）。
    /// </summary>
    [Serializable]
    public class ReplayShipPayload
    {
        public ReplayShipSlot Ship0;
        public ReplayShipSlot Ship1;
        public ReplayShipSlot Ship2;
        public ReplayShipSlot Ship3;
        public ReplayShipSlot Ship4;
        public ReplayShipSlot Ship5;
        public ReplayShipSlot Ship6;
        public ReplayShipSlot Ship7;
        public ReplayShipSlot Ship8;
        public ReplayShipSlot Ship9;
        public ReplayShipSlot Ship10;
        public ReplayShipSlot Ship11;
        public ReplayShipSlot Ship12;
        public ReplayShipSlot Ship13;
        public ReplayShipSlot Ship14;
        public ReplayShipSlot Ship15;

        public ReplayShipSlot[] Slots()
        {
            var slots = new[]
            {
                Ship0, Ship1, Ship2, Ship3, Ship4, Ship5, Ship6, Ship7,
                Ship8, Ship9, Ship10, Ship11, Ship12, Ship13, Ship14, Ship15,
            };
            int count = 0;
            foreach (var slot in slots) if (slot != null) count++;
            var present = new ReplayShipSlot[count];
            int index = 0;
            foreach (var slot in slots) if (slot != null) present[index++] = slot;
            return present;
        }
    }

    /// <summary>payload.ShipN 原始槽位（state 为后端 NE 序 6 元组；gui_server/replay.py）。</summary>
    [Serializable]
    public class ReplayShipSlot
    {
        public ReplayOriginalState original_gnc;
        public int id;
        public int mmsi;
        public double[] state;
        public double[] csog_state;
        public float turn_rate;
        public bool active;
    }

    [Serializable] public class ReplayOriginalState { public double[] state_8d; }
    [Serializable] public class ReplayRecordedBalance { public float roll_deg; }

    /// <summary>replay context 响应（schema "colav.run-replay.context@1"）twin 消费子集。</summary>
    [Serializable]
    public class ReplayStaticContext
    {
        public string schema_version;
        public string run_id;
        public ReplayEncBounds enc;
        public ReplayStaticShip[] ships;
        public TwinEnvironment environment;
    }

    /// <summary>ENC 图幅原点/尺寸（全域 UTM 米）——TwinAnchor.FromOrigin 的 sealed 侧来源。</summary>
    [Serializable]
    public class ReplayEncBounds
    {
        public double origin_east_m;
        public double origin_north_m;
        public double width_m;
        public double height_m;
        public int utm_zone;
    }

    /// <summary>context.ships 静态尺寸（length_m/width_m；window 帧内无尺寸）。</summary>
    [Serializable]
    public class ReplayStaticShip
    {
        public int id;
        public int mmsi;
        public float length_m;
        public float width_m;
    }
}
