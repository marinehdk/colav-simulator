using System;

namespace Sango
{
    /// <summary>
    /// Twin 数据面断线重连退避纯函数（P2-S3 spec #89；twin-bridge-v1.md §5 冻结）：
    /// 退避 1s → 2s → 5s → 5s … 封顶 5s。墙钟/线程归调用方（TwinSessionDriver 后台线程），
    /// 本类只给确定序列（EditMode 可测）。
    /// </summary>
    public static class TwinReconnectPolicy
    {
        /// <summary>退避序列（秒）；attempt 超界后恒用末值（封顶）。</summary>
        public static readonly double[] BackoffSeconds = { 1.0, 2.0, 5.0 };

        /// <summary>封顶值（契约 §5 "封顶 5s"）。</summary>
        public const double MaxDelaySeconds = 5.0;

        /// <summary>第 attempt 次重连（0 起）前的等待秒数；attempt 负数视为 0。</summary>
        public static double DelaySeconds(int attempt)
        {
            if (attempt < 0) attempt = 0;
            return attempt >= BackoffSeconds.Length ? BackoffSeconds[BackoffSeconds.Length - 1] : BackoffSeconds[attempt];
        }

        /// <summary>一次断线重连决策（是否重连 + 退避秒数；ReconnectSequence.OnDisconnected 产物）。</summary>
        public readonly struct ReconnectDecision
        {
            public ReconnectDecision(bool reconnect, double delaySeconds)
            {
                Reconnect = reconnect;
                DelaySeconds = delaySeconds;
            }

            public bool Reconnect { get; }
            public double DelaySeconds { get; }
        }

        /// <summary>
        /// driver 层重连序列（P2-S4 B 收口）：TwinSessionDriver.ReceiveLoop 的 attempt 状态机抽出，
        /// "断线→退避→重连→成功复位"语义可在 EditMode 无网络模拟断言（twin-bridge-v1.md §5）。
        /// 墙钟/线程仍归调用方（ReceiveLoop 后台线程），本类只给确定序列。
        /// </summary>
        public sealed class ReconnectSequence
        {
            int m_Attempt;

            /// <summary>已失败次数（连接成功即复位 0；重连日志编号用）。</summary>
            public int Attempt => m_Attempt;

            /// <summary>连接成功：退避复位（契约 §5：连续失败才升级）。</summary>
            public void OnConnected() => m_Attempt = 0;

            /// <summary>断线判定：running/autoReconnect 任一为 false 即停；否则按当前 attempt 取退避并升级。</summary>
            public ReconnectDecision OnDisconnected(bool running, bool autoReconnect)
            {
                if (!running || !autoReconnect) return new ReconnectDecision(false, 0.0);
                return new ReconnectDecision(true, DelaySeconds(m_Attempt++));
            }
        }
    }
}
