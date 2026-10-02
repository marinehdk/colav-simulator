namespace Sango
{
    /// <summary>compact-v1 帧的 seq 闸门判定（P2-S1 spec #89）。</summary>
    public enum TwinFrameDecision
    {
        /// <summary>新快照：接受进时钟/位姿管线。</summary>
        Accept,
        /// <summary>同 seq 重发（求解步间 ~10Hz 重发同快照，evidence p2s0-notes.md 发现 1）：丢弃。</summary>
        Duplicate,
        /// <summary>seq 倒退：会话重建信号（清船、重置锚点与时钟后重 attach 语义）。</summary>
        Rebuild,
    }

    /// <summary>
    /// Twin seq 去重/重建闸门（P2-S1 spec #89；纯函数）。
    /// S0 实证（docs/research/2026-10-02-phase2-unity-web-integration/evidence/p2s0-notes.md）：
    /// 求解步每 0.5s 推进一次、步间以 ~10Hz 重发同 seq 快照，实序 [0,1,1,1,1,2,2,2,2,2,3,3]——
    /// 故 "单调步号" 按 "非递减 + 同值重发" 理解：同 seq = Duplicate；倒退才判 Rebuild。
    /// 首帧（lastSeq&lt;0）恒 Accept。
    /// </summary>
    public static class TwinFrameGate
    {
        public static TwinFrameDecision Classify(int incomingSeq, int lastSeq)
        {
            if (lastSeq < 0) return TwinFrameDecision.Accept;
            if (incomingSeq == lastSeq) return TwinFrameDecision.Duplicate;
            if (incomingSeq < lastSeq) return TwinFrameDecision.Rebuild;
            return TwinFrameDecision.Accept;
        }
    }

    /// <summary>
    /// compact-v1 信封合法性守卫（P2-S1 spec #89；纯函数）。
    /// Twin 消费前置条件：transport.schema_version=="colav.telemetry.compact@1"（main.py:175）
    /// 且 truth 非空（truth[0] = 本船，锚定与驱动都从它出发）。JsonUtility 反序列化产物
    /// 字段可缺省（PLAN §8 风险 5），故在闸门处一次拦下损坏/错误流。
    /// </summary>
    public static class TwinEnvelope
    {
        public const string CompactSchemaVersion = "colav.telemetry.compact@1";

        public static bool IsValidCompact(ColavTelemetry frame)
        {
            return frame != null
                && frame.transport != null
                && frame.transport.schema_version == CompactSchemaVersion
                && frame.truth != null
                && frame.truth.Length > 0;
        }
    }
}
