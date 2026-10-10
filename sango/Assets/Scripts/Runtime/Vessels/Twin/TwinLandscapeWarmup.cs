using UnityEngine;

namespace Sango
{
    // Display readiness only. Never pauses or advances the authoritative session.
    public sealed class TwinLandscapeWarmup
    {
        public string RunId { get; private set; }
        public string State { get; private set; } = "waiting-session";
        public float Progress { get; private set; }
        public bool Ready => State == "ready" || State == "offline-terrain";
        float m_Start, m_Settled = -1, m_LastActivity, m_ActivityProgress;
        public void Reset() { RunId = null; State = "waiting-session"; Progress = 0; m_Settled = -1; }
        public void Begin(string runId, float now)
        {
            if (RunId == runId) return;
            RunId = runId; State = "warming"; Progress = 0; m_Start = now; m_LastActivity = now; m_ActivityProgress = 0; m_Settled = -1;
        }
        public void Observe(float now, float progress, bool online, bool failed)
        {
            if (RunId == null || Ready || State == "failed") return;
            if (!online) { State = "offline-terrain"; Progress = 100; return; }
            Progress = float.IsNaN(progress) || float.IsInfinity(progress) ? 0 : Mathf.Clamp(progress, 0, 100);
            if (Mathf.Abs(Progress - m_ActivityProgress) > .1f)
            { m_LastActivity = now; m_ActivityProgress = Progress; }
            // High-resolution views can take longer than the coarse preview. Fail a
            // stalled request promptly, but allow healthy downloads to keep progressing.
            if (failed || now - m_LastActivity >= 90 || now - m_Start >= 600) { State = "failed"; return; }
            if (Progress < 99) { m_Settled = -1; return; }
            if (m_Settled < 0) m_Settled = now;
            if (now - m_Settled >= 4) State = "ready";
        }
        public static Vector3 Ahead(Vector3 own, Vector3[] route, float distance, float heading)
        {
            if (route == null || route.Length < 2)
                return own + Quaternion.Euler(0, heading, 0) * Vector3.forward * distance;
            int segment = 0;
            float nearest = float.PositiveInfinity, fraction = 0;
            for (int i = 0; i < route.Length - 1; i++)
            {
                var a = route[i]; a.y = own.y;
                var delta = route[i + 1] - route[i]; delta.y = 0;
                float t = delta.sqrMagnitude > 0 ? Mathf.Clamp01(Vector3.Dot(own - a, delta) / delta.sqrMagnitude) : 0;
                float separation = (own - a - delta * t).sqrMagnitude;
                if (separation < nearest) { nearest = separation; segment = i; fraction = t; }
            }
            var point = Vector3.Lerp(route[segment], route[segment + 1], fraction); point.y = own.y;
            for (int i = segment; i < route.Length - 1; i++)
            {
                var end = route[i + 1]; end.y = own.y;
                float length = Vector3.Distance(point, end);
                if (length >= distance && length > 0) return Vector3.MoveTowards(point, end, distance);
                distance -= length; point = end;
            }
            return point;
        }
    }
}
