using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net.WebSockets;
using System.Threading;
using UnityEditor;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace Sango.Editor
{
    /// <summary>
    /// P2-S1 Twin live 探针（spec #89 验收 2；-executeMethod 批处理可跑，先例 BuoyancyPerfProbe 工艺）。
    /// 编辑态直跑（不进 Play）：建会话 → start → WS compact-v1 收 N 帧 → 用生产纯核心
    /// （TwinFrameGate/TwinClock/TwinAnchor/TwinPose）逐帧过管线 → 数值断言 → JSON 报告落
    /// output/sango-twin-s1/ → Exit(passed?0:1)。
    /// 断言面：信封/首帧 static_included/seq 去重（同 seq 重发必出现）/无倒退/锚定=首帧本船/
    /// 本船位姿=锚定局部坐标/psi=90°→rotation.y=90°+艏向+东（PHASE1-PLAN 冻结动作的数值级，
    /// 现无精确 90° 场景——spec #89 授权数值断言代替视觉）/sealed window 适配同一管线。
    /// 场景头会话优先无现成 45°/90° 起点（head_on 本船 psi=π/4），艏向正确性以 45° 真流 +
    /// 90° 纯函数双路覆盖。
    /// </summary>
    public static class TwinLiveProbe
    {
        const string k_DefaultOutput = "output/sango-twin-s1";
        const int k_FrameTarget = 30;
        const double k_ReceiveTimeoutS = 15;

        [Serializable]
        public class PoseSnapshot
        {
            public int seq;
            public double simTimeS;
            public double eastM, northM, psiRad, sogMps;
            public double posX, posZ, yawDeg;
        }

        [Serializable]
        public class Report
        {
            public bool passed;
            public string[] failures;
            public string backendBase;
            public string sessionId;
            public int received, accepted, duplicates, rebuilds, malformed;
            public int firstSeq, lastSeq;
            public double firstSimTimeS, lastSimTimeS, multiplier;
            public double anchorEastM, anchorNorthM;
            public PoseSnapshot ownFirst, ownLast;
            public string psi90Check;
            public string sealedRunId;
            public int sealedFrames;
            public double sealedOwnPosX, sealedOwnPosZ, sealedTargetPosX, sealedTargetPosZ;
            public double wallSeconds;
        }

        public static void Run()
        {
            // 默认落仓库根 output/（Unity batchmode cwd=工程目录 sango/，
            // 以 Application.dataPath 锚定：<repo>/sango/Assets/../../output）。
            string output = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", k_DefaultOutput));
            var args = Environment.GetCommandLineArgs();
            int flag = Array.IndexOf(args, "--sango-twin-out");
            if (flag >= 0 && flag + 1 < args.Length) output = Path.GetFullPath(args[flag + 1]);
            string sealedRun = null;
            int sealedFlag = Array.IndexOf(args, "--sango-twin-sealed-run");
            if (sealedFlag >= 0 && sealedFlag + 1 < args.Length) sealedRun = args[sealedFlag + 1];
            string backend = SangoSeamConfig.TwinBackendBase;
            Directory.CreateDirectory(output);
            var failures = new List<string>();
            var report = new Report { backendBase = backend };
            var stopwatch = Stopwatch.StartNew();
            try
            {
                report.psi90Check = ProbePsi90(failures);
                ProbeLive(report, failures, backend);
                ProbeSealed(report, failures, backend, sealedRun, output);
            }
            catch (Exception error)
            {
                failures.Add($"probe: {error.GetType().Name} {error.Message}");
                Debug.LogError($"[Sango.TwinProbe] {error}");
            }
            stopwatch.Stop();
            report.wallSeconds = stopwatch.Elapsed.TotalSeconds;
            report.passed = failures.Count == 0;
            report.failures = failures.ToArray();
            string path = Path.Combine(output, "report.json");
            File.WriteAllText(path, JsonUtility.ToJson(report, true));
            Debug.Log("[Sango.TwinProbe] " + (report.passed ? "PASS " : "FAIL ") + path +
                      $" rx={report.received} acc={report.accepted} dup={report.duplicates} rb={report.rebuilds} " +
                      $"own=({report.ownLast?.posX.ToString("0.00")},{report.ownLast?.posZ.ToString("0.00")})m " +
                      $"psi90={report.psi90Check} sealed={report.sealedRunId ?? "n/a"}");
            EditorApplication.Exit(report.passed ? 0 : 1);
        }

        // ── live：WS compact-v1 真流过生产管线 ─────────────────────────────────────

        static void ProbeLive(Report report, List<string> failures, string backend)
        {
            var stopwatch = Stopwatch.StartNew(); // live 段墙钟（软对齐注入）
            TwinRest.Get(backend, "/api/runs?limit=1"); // 探活（挂了即异常进 failures）
            PauseCurrentSessionBestEffort(backend);
            string sessionId = TwinRest.CreateSession(backend, "rule14", "head_on", "vo", "god");
            TwinRest.StartSession(backend, sessionId);
            report.sessionId = sessionId;
            Debug.Log("[Sango.TwinProbe] session " + sessionId + " started");
            try
            {
                ReceiveFrames(report, failures, backend, sessionId, stopwatch);
            }
            finally
            {
                try { TwinRest.Post(backend, $"/api/sessions/{sessionId}/pause"); } // 收尾（S0 抓取同礼）
                catch (Exception error) { Debug.LogWarning("[Sango.TwinProbe] post-run pause failed: " + error.Message); }
            }
        }

        static void ReceiveFrames(Report report, List<string> failures, string backend, string sessionId, Stopwatch stopwatch)
        {

            var clock = new TwinClock();
            var gateCounts = new int[3]; // Accept/Duplicate/Rebuild
            int lastSeq = -1, received = 0, malformed = 0;
            bool firstStaticSeen = false, laterStaticLeak = false;
            TwinAnchor anchor = default;
            bool anchorSet = false;
            var ownFirst = new PoseSnapshot();
            var ownLast = new PoseSnapshot();
            bool ownFirstSet = false;
            int firstSeq = -1;
            double firstSim = -1, lastSim = -1, multiplier = -1;
            bool seqRegressed = false;

            using (var socket = new ClientWebSocket())
            {
                string url = TwinWs.CompactUrl(backend, sessionId);
                Debug.Log("[Sango.TwinProbe] connecting " + url);
                socket.ConnectAsync(new Uri(url), CancellationToken.None).GetAwaiter().GetResult();
                while (received < k_FrameTarget)
                {
                    string json = TwinWs.ReceiveText(socket, CancellationToken.None);
                    if (json == null)
                        throw new IOException($"WS closed early at frame {received}: state={socket.State} " +
                                              $"close={socket.CloseStatus} {socket.CloseStatusDescription} url={url}");
                    var frame = ColavTelemetry.FromJson(json);
                    if (!TwinEnvelope.IsValidCompact(frame)) { malformed++; continue; }
                    double wall = stopwatch.Elapsed.TotalSeconds;
                    received++;
                    if (received == 1 && !frame.transport.static_included) failures.Add("live: first frame static_included=false");
                    if (received > 1 && frame.transport.static_included) laterStaticLeak = true;

                    var decision = TwinFrameGate.Classify(frame.seq, lastSeq);
                    gateCounts[(int)decision]++;
                    if (decision == TwinFrameDecision.Duplicate) continue;
                    if (decision == TwinFrameDecision.Rebuild) seqRegressed = true;
                    lastSeq = frame.seq;
                    var sync = clock.OnFrame(frame.sim_time, wall,
                        frame.playback != null ? frame.playback.effective_multiplier : 1.0);
                    if (sync == TwinFrameSync.Resync) failures.Add($"live: unexpected resync at seq {frame.seq}");
                    multiplier = clock.Multiplier;
                    if (firstSeq < 0)
                    {
                        firstSeq = frame.seq;
                        firstSim = frame.sim_time;
                        anchor = TwinAnchor.FromShip(frame.truth[0]);
                        anchorSet = true;
                    }
                    lastSim = frame.sim_time;

                    var own = frame.truth[0];
                    if (!ownFirstSet)
                    {
                        ownFirst = Snapshot(frame.seq, frame.sim_time, own, anchor);
                        ownFirstSet = true;
                    }
                    ownLast = Snapshot(frame.seq, frame.sim_time, own, anchor);
                }
            }

            report.received = received;
            report.accepted = gateCounts[(int)TwinFrameDecision.Accept];
            report.duplicates = gateCounts[(int)TwinFrameDecision.Duplicate];
            report.rebuilds = gateCounts[(int)TwinFrameDecision.Rebuild];
            report.malformed = malformed;
            report.firstSeq = firstSeq;
            report.lastSeq = lastSeq;
            report.firstSimTimeS = firstSim;
            report.lastSimTimeS = lastSim;
            report.multiplier = multiplier;
            report.anchorEastM = anchor.EastM;
            report.anchorNorthM = anchor.NorthM;
            report.ownFirst = ownFirst;
            report.ownLast = ownLast;

            if (laterStaticLeak) failures.Add("live: static_included=true after first frame (S0 契约违反)");
            if (seqRegressed) failures.Add("live: seq regression observed (head_on 正常流不应重建)");
            if (malformed > 0) failures.Add($"live: {malformed} malformed envelope(s)");
            if (gateCounts[(int)TwinFrameDecision.Duplicate] == 0)
                failures.Add("live: no same-seq resend observed (S0 实证步间 ~10Hz 重发应出现)");
            if (gateCounts[(int)TwinFrameDecision.Accept] < 3) failures.Add("live: fewer than 3 accepted solver steps");
            if (!anchorSet) failures.Add("live: no anchor established");
            if (Math.Abs(ownFirst.posX - anchor.LandingM.x) > 0.01 || Math.Abs(ownFirst.posZ - anchor.LandingM.y) > 0.01)
                failures.Add($"live: ownship not anchored at geo landing ({ownFirst.posX:0.000},{ownFirst.posZ:0.000} vs {anchor.LandingM})");
            AssertClose(failures, "live: own yaw = psi·Rad2Deg", ownLast.yawDeg, ownLast.psiRad * 57.29578, 0.01);
            // P3-12：场景位 = 减锚 + 登记平移（TwinAnchor.ToLocal 同式）。
            AssertClose(failures, "live: own pos from anchor math", ownLast.posX, ownLast.eastM - anchor.EastM + anchor.LandingM.x, 0.01);
            AssertClose(failures, "live: own pos z from anchor math", ownLast.posZ, ownLast.northM - anchor.NorthM + anchor.LandingM.y, 0.01);
            if (lastSim <= firstSim) failures.Add("live: sim_time did not advance");
            if (multiplier < 0.5 || multiplier > 1.5) failures.Add($"live: effective_multiplier out of sane range ({multiplier:0.000})");
            AssertClose(failures, "live: own heading 45° NE at t0 (head_on 事实)",
                VectorAngle(ownFirst.psiRad), 45.0, 0.5);
        }

        static PoseSnapshot Snapshot(int seq, double simTime, ColavTelemetry.ShipEntry own, TwinAnchor anchor)
        {
            var position = TwinPose.ScenePosition(own, anchor);
            return new PoseSnapshot
            {
                seq = seq,
                simTimeS = simTime,
                eastM = own.east,
                northM = own.north,
                psiRad = own.psi,
                sogMps = own.sog,
                posX = position.x,
                posZ = position.z,
                yawDeg = TwinPose.YawDegrees(own.psi),
            };
        }

        // ── sealed：window REST → 适配层 → 同一管线 ────────────────────────────────

        /// <summary>
        /// 候选 run 决策（零脑补，全部既有端点）：① --sango-twin-sealed-run 显式指定；
        /// ② 上次探针会话（output/report.json 的 sessionId——本次 create 时其后端 capture
        /// 已被"会话替换"路径收口，trusted prefix 可回放）；③ /api/runs?limit=3 最近列表
        /// （只拉小页：全量列表会对每个 run 做完整性哈希，本机 50 run 需 ~1 分钟）。
        /// 窗口统一 from=0&amp;to=1：任何 seekable run（READY/INCOMPLETE trusted prefix）都含
        /// ≥2 帧（head_on dt=0.5s → 0.0/0.5/1.0），又不越 INCOMPLETE 的 trusted_t_end。
        /// </summary>
        static void ProbeSealed(Report report, List<string> failures, string backend, string preferredRun, string output)
        {
            var candidates = new List<string>();
            if (!string.IsNullOrEmpty(preferredRun)) candidates.Add(preferredRun);
            try
            {
                string previousReport = Path.Combine(output, "report.json");
                if (File.Exists(previousReport))
                {
                    var previous = JsonUtility.FromJson<Report>(File.ReadAllText(previousReport));
                    if (previous != null && !string.IsNullOrEmpty(previous.sessionId))
                        candidates.Add(previous.sessionId);
                }
            }
            catch (Exception error) { Debug.LogWarning("[Sango.TwinProbe] previous report unreadable: " + error.Message); }
            try
            {
                foreach (var run in JsonUtilityListRuns(TwinRest.Get(backend, "/api/runs?limit=3")))
                    if (run != null && !string.IsNullOrEmpty(run.run_id)) candidates.Add(run.run_id);
            }
            catch (Exception error) { Debug.LogWarning("[Sango.TwinProbe] runs listing failed: " + error.Message); }

            string windowJson = null, contextJson = null, runId = null;
            var errors = new List<string>();
            var seen = new HashSet<string>();
            foreach (var candidate in candidates)
            {
                if (string.IsNullOrEmpty(candidate) || !seen.Add(candidate)) continue;
                try
                {
                    windowJson = TwinRest.Get(backend, $"/api/runs/{candidate}/replay/window?from=0&to=1");
                    contextJson = TwinRest.Get(backend, $"/api/runs/{candidate}/replay/context");
                    runId = candidate;
                    break;
                }
                catch (Exception error) { errors.Add($"{candidate[..Math.Min(8, candidate.Length)]}: {error.Message}"); }
            }
            if (runId == null)
            {
                failures.Add("sealed: no seekable run produced a window (candidates: " +
                             string.Join("; ", errors) + ")");
                return;
            }

            var window = ReplayWindowAdapter.WindowFromJson(windowJson);
            var context = ReplayWindowAdapter.ContextFromJson(contextJson);
            report.sealedRunId = runId;
            report.sealedFrames = window.frames != null ? window.frames.Length : 0;
            if (report.sealedFrames < 2) { failures.Add("sealed: window returned fewer than 2 frames"); return; }

            var clock = new TwinClock();
            var firstTelemetry = ReplayWindowAdapter.ToTelemetry(window.frames[0], context);
            if (firstTelemetry == null || firstTelemetry.truth == null || firstTelemetry.truth.Length == 0)
            { failures.Add("sealed: first window frame adapted to empty truth"); return; }
            var anchor = TwinAnchor.FromShip(firstTelemetry.truth[0]);
            var ownLast = Vector2.zero;
            var targetLast = Vector2.zero;
            for (int i = 0; i < window.frames.Length; i++)
            {
                var telemetry = ReplayWindowAdapter.ToTelemetry(window.frames[i], context);
                if (telemetry == null || telemetry.truth == null || telemetry.truth.Length == 0)
                { failures.Add($"sealed: frame {i} adapted to empty truth"); return; }
                var sync = clock.OnFrame(telemetry.sim_time, i * 0.5, telemetry.playback.effective_multiplier);
                if (i > 0 && sync != TwinFrameSync.Smooth)
                { failures.Add($"sealed: frame {i} not smooth ({sync}) — 帧距应匹配 1× 预测"); }
                foreach (var ship in telemetry.truth)
                {
                    var local = TwinPose.ScenePosition(ship, anchor);
                    if (ship.id == 0) ownLast = new Vector2(local.x, local.z);
                    else targetLast = new Vector2(local.x, local.z);
                }
            }
            report.sealedOwnPosX = ownLast.x;
            report.sealedOwnPosZ = ownLast.y;
            report.sealedTargetPosX = targetLast.x;
            report.sealedTargetPosZ = targetLast.y;
            // P3-12：锚点变换含登记平移——合理性门对落点相对量判（原点语义已退役）。
            if ((ownLast - anchor.LandingM).magnitude > 7000f)
                failures.Add($"sealed: ownship local position implausible ({ownLast}) — 锚定失效");
            if ((targetLast - anchor.LandingM).sqrMagnitude < 1f) failures.Add("sealed: target did not move off anchor origin");
        }

        [Serializable]
        class RunCapabilities { public bool seekable; }
        [Serializable]
        class RunReplay { public string state; }
        [Serializable]
        class RunSummary
        {
            public string run_id;
            public string scenario_id;
            public RunCapabilities capabilities;
            public RunReplay replay;
        }
        [Serializable]
        class RunList { public RunSummary[] runs; }

        static RunSummary[] JsonUtilityListRuns(string json)
        {
            // /api/runs 返回裸数组；JsonUtility 不吃顶层数组 → 包一层再解（只读探针，容忍空）。
            var wrapped = "{\"runs\":" + (string.IsNullOrWhiteSpace(json) ? "[]" : json) + "}";
            var list = JsonUtility.FromJson<RunList>(wrapped);
            return list != null && list.runs != null ? list.runs : new RunSummary[0];
        }

        [Serializable]
        class CurrentSession { public bool active; public string session_id; public string state; }

        /// <summary>尽力暂停当前活动会话（后端单活动会话；残留 RUNNING 会阻塞新建，422）。</summary>
        static void PauseCurrentSessionBestEffort(string backend)
        {
            try
            {
                var current = JsonUtility.FromJson<CurrentSession>(TwinRest.Get(backend, "/api/sessions/current"));
                if (current != null && current.active && current.state == "RUNNING" && !string.IsNullOrEmpty(current.session_id))
                {
                    TwinRest.Post(backend, $"/api/sessions/{current.session_id}/pause");
                    Debug.Log("[Sango.TwinProbe] paused leftover session " + current.session_id);
                }
            }
            catch (Exception error)
            {
                Debug.LogWarning("[Sango.TwinProbe] pause current best-effort failed: " + error.Message);
            }
        }

        // ── psi=90° 冻结验收动作（数值级；无精确 90° 场景，spec #89 授权） ──────────

        static string ProbePsi90(List<string> failures)
        {
            float yaw = TwinPose.YawDegrees(Mathf.PI / 2f);
            Vector3 heading = TwinPose.HeadingVector(yaw);
            bool ok = Math.Abs(yaw - 90f) < 1e-3
                      && Math.Abs(heading.x - 1f) < 1e-4
                      && Math.Abs(heading.z) < 1e-4;
            if (!ok) failures.Add($"psi90: yaw={yaw:0.####} heading=({heading.x:0.####},{heading.z:0.####}) 期望 90°/+东");
            return ok ? "rotation.y=90 heading=+E PASS" : "FAIL";
        }

        static double VectorAngle(double psiRad) => psiRad * 180.0 / Math.PI;

        static void AssertClose(List<string> failures, string label, double actual, double expected, double tolerance)
        {
            if (Math.Abs(actual - expected) > tolerance)
                failures.Add($"{label}: expected {expected:0.####} ± {tolerance}, got {actual:0.####}");
        }
    }
}
