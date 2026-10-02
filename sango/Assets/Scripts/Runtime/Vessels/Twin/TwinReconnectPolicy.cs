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
    }
}
