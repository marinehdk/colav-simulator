using System;
using NetMQ;
using NetMQ.Sockets;
using UnityEngine;
using UnityEngine.Rendering;

namespace Sango
{
    /// <summary>
    /// 路线A 本船逐像素掩膜通道（ownship-mask-v1.md）:每渲染帧把本船全部 Renderer
    /// 以白 unlit 画进 R8 掩膜 RT（视口相机同帧同参 SetViewProjectionMatrices）,
    /// 读回后逐行 1bit RLE 按 topic sango.ownship_mask 直发检测端（:5558）。
    /// 帧对齐 = FRAME_MARKER frame_id（LateUpdate 采 TwinSituationDisplay.CurrentFrameId,
    /// 与 blit 进视频的 marker 同帧）;检测端环形缓存精确匹配,替代 P1 多边形 HTTP 中继。
    /// 门控与 TwinSituationDisplay 同源（桥断/无 driver/无相机即停发,socket 随关随开）;
    /// 渲染/发布只在 marker 或相机/本船位姿实际变化时发生（典型 ~10-20Hz）。
    /// </summary>
    [DefaultExecutionOrder(10001)] // 紧随 TwinSituationDisplay(10000):marker 已更新、相机位姿为终值
    public sealed class TwinOwnshipMaskPublisher : MonoBehaviour
    {
        public TwinBridgeService bridge;

        [Tooltip("掩膜 RT 宽（16:9,与 sender detect tap 同宽高比;检测端 NEAREST 缩放）")]
        [Range(64, 1280)] public int maskWidth = 640;
        [Range(64, 720)] public int maskHeight = 360;

        PublisherSocket m_Pub;
        RenderTexture m_MaskRT;
        Material m_MaskMaterial;
        GameObject m_Ship;
        Renderer[] m_Renderers;
        int m_LastFrameId = -1;
        Vector3 m_LastCamPos = new Vector3(float.PositiveInfinity, 0, 0);
        Quaternion m_LastCamRot = Quaternion.identity;
        Vector3 m_LastShipPos = new Vector3(float.PositiveInfinity, 0, 0);
        int m_Sent, m_Dropped;
        float m_LastLog = -60f;

        void LateUpdate()
        {
            var driver = bridge?.driver;
            var camera = bridge?.cameraRig?.controlledCamera;
            var display = bridge?.Situation;
            bool gate = bridge != null && bridge.runtimeEnabled && driver?.Anchor != null &&
                camera != null && display != null && bridge.ActiveBridgeChannel != null &&
                bridge.ActiveBridgeChannel.IsConnected;
            if (!gate) { StopPublishing(); return; }
            var ship = driver.OwnShipObject;
            int frameId = display.CurrentFrameId;
            bool changed = frameId != m_LastFrameId ||
                Vector3.SqrMagnitude(camera.transform.position - m_LastCamPos) > 0.0001f ||
                Quaternion.Angle(camera.transform.rotation, m_LastCamRot) > 0.05f ||
                (ship != null && ship.activeInHierarchy &&
                 Vector3.SqrMagnitude(ship.transform.position - m_LastShipPos) > 0.0001f);
            if (!changed) return;
            m_LastFrameId = frameId;
            m_LastCamPos = camera.transform.position;
            m_LastCamRot = camera.transform.rotation;
            if (ship != null) m_LastShipPos = ship.transform.position;
            if (!EnsurePublishing() || !RefreshShip(ship)) return;
            int frame = frameId, width = maskWidth, height = maskHeight;
            var cmd = new CommandBuffer { name = "Sango ownship mask" };
            cmd.SetRenderTarget(m_MaskRT);
            cmd.ClearRenderTarget(false, true, Color.clear);
            cmd.SetViewProjectionMatrices(camera.worldToCameraMatrix, camera.projectionMatrix);
            foreach (var renderer in m_Renderers)
            {
                if (renderer == null) continue;
                int submeshes = Math.Max(1, renderer.sharedMaterials.Length);
                for (int submesh = 0; submesh < submeshes; submesh++)
                    cmd.DrawRenderer(renderer, m_MaskMaterial, submesh);
            }
            cmd.RequestAsyncReadback(m_MaskRT, 0, TextureFormat.R8, request =>
            {
                if (request.hasError) { m_Dropped++; return; }
                Publish(frame, OwnshipMaskRle.Encode(request.GetData<byte>(), width, height), width, height);
            });
            Graphics.ExecuteCommandBuffer(cmd);
            cmd.Dispose();
        }

        bool RefreshShip(GameObject ship)
        {
            if (m_Ship != ship)
            {
                m_Ship = ship;
                m_Renderers = ship != null
                    ? Array.FindAll(ship.GetComponentsInChildren<Renderer>(false),
                        renderer => renderer is MeshRenderer || renderer is SkinnedMeshRenderer)
                    : Array.Empty<Renderer>();
                if (m_Renderers.Length == 0 && ship != null)
                {
                    // 扫描落在本船层级装配/激活窗口内(GetComponentsInChildren(false)
                    // 不含 inactive)会拿到空表,而空表在此永不重扫 → 掩膜永久全零、
                    // 本船裸奔检出(20261020 追尾视角误检根因)。置空下帧重扫。
                    m_Ship = null;
                    return false;
                }
            }
            else if (m_Renderers != null && m_Renderers.Length > 0 && m_Renderers[0] == null)
            {
                m_Ship = null; // 本船销毁重建（会话代际）:置空下帧重扫
                return false;
            }
            return true;
        }

        bool EnsurePublishing()
        {
            if (m_MaskRT != null && (m_MaskRT.width != maskWidth || m_MaskRT.height != maskHeight))
            { m_MaskRT.Release(); Destroy(m_MaskRT); m_MaskRT = null; }
            if (m_MaskRT == null)
            {
                m_MaskRT = new RenderTexture(maskWidth, maskHeight, 0, RenderTextureFormat.R8) { name = "Sango ownship mask" };
                m_MaskRT.Create();
            }
            if (m_MaskMaterial == null)
            {
                var shader = Shader.Find("Sango/OwnshipMaskUnlit");
                if (shader == null) { enabled = false; Debug.LogError("[Sango.DT] OwnshipMaskUnlit shader missing — mask publisher disabled"); return false; }
                m_MaskMaterial = new Material(shader);
            }
            if (m_Pub != null) return true;
            try
            {
                m_Pub = new PublisherSocket();
                m_Pub.Options.SendHighWatermark = 60; // 掩膜小帧:订阅端慢=丢旧不积压
                m_Pub.Bind(SangoSeamConfig.OwnshipMaskEndpoint);
                Debug.Log($"[Sango.DT] ownship mask publisher bound {SangoSeamConfig.OwnshipMaskEndpoint} (topic {SangoSeamConfig.OwnshipMaskTopic}, {maskWidth}x{maskHeight} R8)");
                return true;
            }
            catch (Exception error)
            {
                Debug.LogError($"[Sango.DT] ownship mask bind {SangoSeamConfig.OwnshipMaskEndpoint} failed: {error.GetType().Name} {error.Message} (mask publisher disabled)");
                m_Pub?.Dispose(); m_Pub = null;
                enabled = false; // 不再重试,直至组件重新使能
                return false;
            }
        }

        void Publish(int frameId, byte[] rle, int width, int height)
        {
            if (m_Pub == null) return;
            var meta = $"{{\"schema\":\"ownship_mask@1\",\"frame_id\":{frameId},\"width\":{width},\"height\":{height},\"rle_bytes\":{rle.Length}}}";
            var message = new NetMQMessage();
            message.Append(SangoSeamConfig.OwnshipMaskTopic);
            message.Append(meta);
            message.Append(rle);
            if (m_Pub.TrySendMultipartMessage(TimeSpan.FromMilliseconds(50), message)) m_Sent++;
            else m_Dropped++;
            if (Time.unscaledTime - m_LastLog > 30f)
            {
                m_LastLog = Time.unscaledTime;
                Debug.Log($"[Sango.DT] ownship mask sent={m_Sent} dropped={m_Dropped} renderers={(m_Renderers != null ? m_Renderers.Length : 0)} last_frame_id={frameId}");
            }
        }

        void StopPublishing()
        {
            // 迟到读回安全:m_Pub 已 null → Publish 早退;RT 释放后的在途请求走 hasError 分支
            if (m_Pub == null) return;
            m_Pub.Dispose(); m_Pub = null;
            m_LastFrameId = -1;
            Debug.Log("[Sango.DT] ownship mask publisher socket closed");
        }

        void OnDisable() => StopPublishing();
        void OnDestroy()
        {
            StopPublishing();
            if (m_MaskRT != null) { m_MaskRT.Release(); Destroy(m_MaskRT); m_MaskRT = null; }
            if (m_MaskMaterial != null) { Destroy(m_MaskMaterial); m_MaskMaterial = null; }
        }
    }
}
