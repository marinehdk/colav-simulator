using System;
using System.Collections.Generic;

namespace Sango
{
    /// <summary>Bounded live truth buffer. Three wall seconds match Deployment's
    /// presentation cache; missing playback fields retain the last known rate.</summary>
    public sealed class TwinLivePresentation
    {
        const double BufferSeconds = 3.0;
        const int Capacity = 128;
        readonly List<ColavTelemetry> m_Frames = new List<ColavTelemetry>();
        double m_Time = double.NaN;
        double m_Wall;
        bool m_Started, m_Paused;
        public double Rate { get; private set; } = 1.0;
        public bool Buffering => m_Frames.Count > 0 && !m_Started && !m_Paused;

        public void Reset()
        {
            m_Frames.Clear(); m_Time = double.NaN;
            m_Started = m_Paused = false; Rate = 1.0;
        }

        public void ObservePlayback(ColavTelemetry frame, double wall)
        {
            Sample(wall); // finish elapsed time at the old rate before a change
            double rate = frame.playback?.effective_multiplier ?? double.NaN;
            if (!double.IsNaN(rate) && !double.IsInfinity(rate) && rate > 0) Rate = rate;
            bool paused = frame.state == "PAUSED" || frame.state == "FINISHED" || frame.state == "FAILED";
            if (paused)
            {
                m_Frames.Clear(); m_Frames.Add(frame);
                m_Time = frame.sim_time; m_Started = false;
            }
            m_Paused = paused;
            m_Wall = wall;
        }

        public void Offer(ColavTelemetry frame, double wall)
        {
            if (m_Frames.Count > 0)
            {
                double gap = frame.sim_time - m_Frames[m_Frames.Count - 1].sim_time;
                if (gap < 0 || gap > Math.Max(1.0, BufferSeconds * Rate))
                {
                    m_Frames.Clear(); m_Time = frame.sim_time; m_Started = false;
                }
            }
            ObservePlayback(frame, wall);
            if (m_Frames.Count > 0 && frame.sim_time <= m_Frames[m_Frames.Count - 1].sim_time) return;
            m_Frames.Add(frame);
            if (double.IsNaN(m_Time)) m_Time = frame.sim_time;
            if (m_Frames.Count > Capacity)
            {
                m_Frames.RemoveAt(0);
                m_Time = Math.Max(m_Time, m_Frames[0].sim_time);
            }
        }

        public double Sample(double wall)
        {
            if (m_Frames.Count == 0) return double.NaN;
            double latest = m_Frames[m_Frames.Count - 1].sim_time;
            if (!m_Paused)
            {
                if (!m_Started && latest - m_Time >= BufferSeconds * Rate)
                {
                    m_Time = Math.Max(m_Time, latest - BufferSeconds * Rate);
                    m_Started = true; m_Wall = wall;
                }
                if (m_Started) m_Time = Math.Min(latest, m_Time + Math.Max(0, wall - m_Wall) * Rate);
            }
            m_Wall = wall;
            return m_Time;
        }

        public bool Bracket(double wall, out ColavTelemetry previous, out ColavTelemetry next, out double time)
        {
            time = Sample(wall); previous = next = null;
            if (m_Frames.Count == 0) return false;
            while (m_Frames.Count > 2 && m_Frames[1].sim_time <= time) m_Frames.RemoveAt(0);
            previous = m_Frames[0]; next = m_Frames.Count > 1 ? m_Frames[1] : previous;
            return true;
        }
    }
}
