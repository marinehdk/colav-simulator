using System;
using System.Net.Http;
using System.Text;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// Twin REST helper（P2-S1 spec #89）：会话创建/启动 + 只读 GET（window/context）。
    /// 后端零改动红线（00-REPORT.md §8）：只消费既有端点——
    /// POST /api/sessions、POST /api/sessions/{id}/start、GET /api/runs/{id}/replay/...。
    /// 仅后台线程/编辑器批处理使用（同步阻塞）；超时 15s 与 p2s0_capture.py 同量级。
    /// </summary>
    public static class TwinRest
    {
        /// <summary>会话创建响应的 twin 消费子集（capture 脚本兼容 session_id/id 双键）。</summary>
        [Serializable]
        public class SessionCreated
        {
            public string session_id;
            public string id;
        }

        /// <summary>创建会话并返回 session id（evidence/p2s0_capture.py 同参数面）。</summary>
        public static string CreateSession(string backendBase, string validationRuleId, string scenarioId,
            string algorithmId, string trackerId)
        {
            string body = "{\"validation_rule_id\":\"" + validationRuleId + "\",\"scenario_id\":\"" + scenarioId +
                          "\",\"algorithm_id\":\"" + algorithmId + "\",\"tracker_id\":\"" + trackerId +
                          "\",\"record_replay_trace\":true}";
            string json = SendJson(backendBase, "/api/sessions", body);
            var created = JsonUtility.FromJson<SessionCreated>(json);
            string sessionId = created != null ? (created.session_id ?? created.id) : null;
            if (string.IsNullOrEmpty(sessionId))
                throw new InvalidOperationException("session create response lacks session_id/id: " + Truncate(json));
            return sessionId;
        }

        /// <summary>启动会话（幂等语义由后端负责；409 已运行亦视为就绪）。</summary>
        public static void StartSession(string backendBase, string sessionId)
        {
            SendJson(backendBase, $"/api/sessions/{sessionId}/start", null);
        }

        /// <summary>GET 相对路径，返回响应正文（探针拉 replay window/context 用）。</summary>
        public static string Get(string backendBase, string relativePath)
        {
            using (var client = MakeClient())
            using (var response = client.GetAsync(backendBase.TrimEnd('/') + relativePath).GetAwaiter().GetResult())
                return ReadBody(response);
        }

        /// <summary>无体 POST（探针收尾 pause 会话等既有控制端点用）。</summary>
        public static void Post(string backendBase, string relativePath)
        {
            SendJson(backendBase, relativePath, null);
        }

        static string SendJson(string backendBase, string path, string jsonBody)
        {
            using (var client = MakeClient())
            {
                using (var content = jsonBody == null ? null
                    : new StringContent(jsonBody, Encoding.UTF8, "application/json"))
                using (var response = content == null
                    ? client.PostAsync(backendBase.TrimEnd('/') + path, null).GetAwaiter().GetResult()
                    : client.PostAsync(backendBase.TrimEnd('/') + path, content).GetAwaiter().GetResult())
                    return ReadBody(response);
            }
        }

        static HttpClient MakeClient()
        {
            var client = new HttpClient();
            client.Timeout = TimeSpan.FromSeconds(15);
            // 关 keep-alive 复用：低频管理调用，Mono 连接池对 uvicorn 空闲连接有
            // 复用竞态（服务端半关后读头部 Operation aborted），禁复用一劳永逸。
            client.DefaultRequestHeaders.ConnectionClose = true;
            return client;
        }

        static string ReadBody(HttpResponseMessage response)
        {
            string body = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
            if (!response.IsSuccessStatusCode)
                throw new InvalidOperationException($"HTTP {(int)response.StatusCode} {Truncate(body)}");
            return body;
        }

        static string Truncate(string value)
        {
            if (string.IsNullOrEmpty(value)) return "";
            return value.Length <= 300 ? value : value.Substring(0, 300) + "…";
        }
    }
}
