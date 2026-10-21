using System;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// live 地理探测的纯解析面（2026-10-21 青岛会话）：后端 /api/enc_info →
    /// 是否 UTM51 青岛域。TwinBridgeService 据此在 live attach 时把
    /// QingdaoStaticScene 当地理提供方（锚/高程覆盖注入 TwinSessionDriver）。
    /// 放 Sango.Vessels（与 TwinBridgeMessage/TwinAnchor 同族）供 EditMode 直引测试。
    /// </summary>
    public static class TwinLiveGeographyProbe
    {
        [Serializable]
        public class EncInfoDocument { public bool ready; public int utm_zone; }

        public static bool IsQingdao(string json)
        {
            if (string.IsNullOrEmpty(json)) return false;
            var info = JsonUtility.FromJson<EncInfoDocument>(json);
            return info != null && info.ready && info.utm_zone == 51;
        }
    }
}
