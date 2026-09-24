using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M2-E1 轨迹时间球节拍纯核心（spec #84：每 N 秒仿真时一个 marker，首个恰在 N）。
    /// 纯静态、确定性；EncounterDirector 每帧对账：BallsDue(simTime) 比已落球数多几颗就补几颗。
    /// </summary>
    public static class TrackClock
    {
        /// <summary>
        /// 仿真时刻 t、间隔 N 下应已落球数 = floor(t/N)（t&lt;N 为 0；N≤0 视为禁用永不落球）。
        /// worked examples：t=0.99N → 0；t=N → 1；t=2.5N → 2（测试钉死）。
        /// </summary>
        public static int BallsDue(float simTimeSeconds, float intervalSeconds)
        {
            if (intervalSeconds <= 0f || simTimeSeconds < intervalSeconds) return 0;
            return Mathf.FloorToInt(simTimeSeconds / intervalSeconds);
        }
    }
}
