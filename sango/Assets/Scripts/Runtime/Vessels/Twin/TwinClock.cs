using System;

namespace Sango
{
    /// <summary>一次 OnFrame 的同步方式（P2-S1 spec #89 软对齐时钟）。</summary>
    public enum TwinFrameSync
    {
        /// <summary>首帧：直接锚定。</summary>
        First,
        /// <summary>与预测在容差内：平滑重锚（帧间继续线性插值）。</summary>
        Smooth,
        /// <summary>大跳超阈值：重同步（位姿直接吸附新帧，跨跳不插值不外推）。</summary>
        Resync,
    }

    /// <summary>
    /// Twin 渲染时钟软对齐核心（P2-S1 spec #89；纯逻辑，墙钟由调用方注入，可 EditMode 测）。
    /// - 帧流 (seq, sim_time) 按 effective_multiplier 倍率在墙钟上推进渲染用插值 sim_time；
    /// - 新帧到达时与 "锚点 + 墙钟差 × 倍率" 的预测比较：偏差 ≤ 阈值 = 平滑重锚；
    ///   偏差 &gt; 阈值（默认 2×帧距，下限 MinResyncLeadS 防网络抖动误判）= 重同步，不跨跳外推；
    /// - 帧距 = 本帧与上帧 sim_time 差（数据驱动，head_on 求解步 0.5s，S0 实证）。
    /// 位姿插值的 "跨跳不插值" 由消费方依据返回值（Resync 后清插值对）实现。
    /// </summary>
    public sealed class TwinClock
    {
        /// <summary>重同步阈值系数：偏差 &gt; 2×帧距判大跳（spec #89 建议 2×帧距）。</summary>
        public const double DefaultResyncLeadFactor = 2.0;

        /// <summary>重同步阈值下限（秒）：帧距极小时防抖动误判为重同步。</summary>
        public const double MinResyncLeadS = 0.25;

        double m_AnchorSimTime;
        double m_AnchorWallS;
        double m_LastFrameSimTime = double.NaN;

        /// <summary>是否已锚定（Reset 后 false）。</summary>
        public bool Synced { get; private set; }

        /// <summary>当前倍率（playback.effective_multiplier；非法输入保持原值，初始 1）。</summary>
        public double Multiplier { get; private set; } = 1.0;

        /// <summary>最近接受帧的仿真时刻。</summary>
        public double LastFrameSimTime => m_LastFrameSimTime;

        /// <summary>
        /// 接受一帧：按需重锚并返回同步方式。wallNowS 由调用方注入（诊断/测试确定性）。
        /// </summary>
        public TwinFrameSync OnFrame(double simTime, double wallNowS, double effectiveMultiplier)
        {
            if (double.IsNaN(effectiveMultiplier) || effectiveMultiplier < 0.0)
                effectiveMultiplier = Multiplier;
            if (!Synced)
            {
                Anchor(simTime, wallNowS, effectiveMultiplier);
                return TwinFrameSync.First;
            }
            double elapsed = System.Math.Max(0.0, wallNowS - m_AnchorWallS);
            double predicted = m_AnchorSimTime + elapsed * Multiplier;
            double frameGap = simTime - m_LastFrameSimTime;
            double lead = System.Math.Max(DefaultResyncLeadFactor * System.Math.Max(frameGap, 0.0), MinResyncLeadS);
            // gap==0 合法：S0 实证 seq N 首帧仍带上一帧 sim_time（seq 先进、sim 后动）——
            // 偏差判据自然放行；只有真倒退（gap<0，正常已被 seq 闸门重建拦下）或偏差超阈值才重同步。
            bool resync = frameGap < 0.0 || System.Math.Abs(simTime - predicted) > lead;
            Anchor(simTime, wallNowS, effectiveMultiplier);
            return resync ? TwinFrameSync.Resync : TwinFrameSync.Smooth;
        }

        /// <summary>
        /// 采样渲染用插值 sim_time：锚点 + 墙钟差 × 倍率；未同步返回 NaN。
        /// 相对最新帧的少量前向预测属设计内（等下一帧到达即被吸收）；
        /// 大跳不在此处外推——重同步后锚点直接落到新帧。
        /// </summary>
        public double Sample(double wallNowS)
        {
            if (!Synced) return double.NaN;
            double elapsed = System.Math.Max(0.0, wallNowS - m_AnchorWallS);
            return m_AnchorSimTime + elapsed * Multiplier;
        }

        /// <summary>会话重建时清锚（下次 OnFrame 走 First）。</summary>
        public void Reset()
        {
            Synced = false;
            Multiplier = 1.0;
            m_LastFrameSimTime = double.NaN;
        }

        void Anchor(double simTime, double wallNowS, double multiplier)
        {
            m_AnchorSimTime = simTime;
            m_AnchorWallS = wallNowS;
            m_LastFrameSimTime = simTime;
            Multiplier = multiplier;
            Synced = true;
        }
    }
}
