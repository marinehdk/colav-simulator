using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;
using CesiumForUnity;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.UIElements;
using UnityEngine.Splines;
using Unity.Mathematics;

namespace Sango
{
    /// <summary>Online geographic appearance. Backend motion and ENC authority stay outside this component.</summary>
    public sealed class TwinCesiumLandscape : MonoBehaviour
    {
        [Serializable] class LandMask { public Ring[] rings; }
        [Serializable] class Ring { public Vector2[] points; }
        public NorwayTerrain geography;
        GameObject m_Root;
        Cesium3DTileset m_Terrain, m_Buildings;
        CesiumCreditSystem m_Credits;
        CesiumCameraManager m_Cameras;
        TwinBridgeService m_Bridge;
        TwinSessionDriver m_Driver;
        readonly TwinLandscapeWarmup m_Warmup = new TwinLandscapeWarmup();
        readonly List<Camera> m_PreloadCameras = new List<Camera>();
        RenderTexture m_PreloadViewport;
        Camera m_ViewCamera, m_StartupView;
        Vector3 m_PreloadAnchor;
        bool m_PreloadPositioned;
        public TwinBridgeLandscapeState Describe() => new TwinBridgeLandscapeState {
            ready = m_Warmup.Ready, state = m_Warmup.State, progress = m_Warmup.Progress,
            terrain_load = TerrainLoad, cache_bytes = m_Terrain != null ? m_Terrain.maximumCachedBytes : 0,
            meshes_created = m_TerrainMeshes, preload_views = m_PreloadCameras.Count + (m_StartupView != null ? 1 : 0),
        };
        Canvas m_CreditCanvas;
        RenderTexture m_CreditTexture;
        PanelSettings m_CreditPanel;
        float m_NextUpdate;
        bool m_ProjectionFailed;
        bool m_OnlineReady;
        bool m_Photoreal;
        float m_ProbeDistance = float.PositiveInfinity;
        int m_TerrainMeshes, m_BuildingMeshes;
        public string Status { get; private set; } = "offline-terrain";
        public int TerrainMeshes => m_TerrainMeshes;
        public int BuildingMeshes => m_BuildingMeshes;
        public float TerrainLoad => m_Terrain != null ? m_Terrain.ComputeLoadProgress() : 0;
        public float BuildingLoad => m_Buildings != null ? m_Buildings.ComputeLoadProgress() : 0;

        void Start()
        {
            m_Bridge = FindFirstObjectByType<TwinBridgeService>();
            m_Driver = FindFirstObjectByType<TwinSessionDriver>();
            string path = Environment.GetEnvironmentVariable("COLAV_CESIUM_TOKEN_FILE");
            if (string.IsNullOrWhiteSpace(path)) path = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "colav-twin-renderer", "cesium-ion-token");
            if (!File.Exists(path)) return;
            string token = File.ReadAllText(path).Trim();
            if (!Regex.IsMatch(token, @"^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$"))
            { Status = "invalid-token-file"; return; }
            m_Root = new GameObject("Cesium Norwegian landscape");
            m_Root.SetActive(false);
            m_Root.transform.SetParent(transform, false);
            m_Root.transform.localRotation = Quaternion.Euler(0,NorwayChartFrame.CesiumYaw,0);
            m_Root.transform.localScale = new Vector3(NorwayChartFrame.CesiumScale,1,NorwayChartFrame.CesiumScale);
            var georeference = m_Root.AddComponent<CesiumGeoreference>();
            georeference.Initialize(); // Inactive construction defers the SDK's OnEnable initialization.
            georeference.SetOriginLongitudeLatitudeHeight(NorwayChartFrame.Longitude,
                NorwayChartFrame.Latitude, NorwayChartFrame.EllipsoidHeight);
            var rig = FindFirstObjectByType<CameraRig>();
            var cameras = m_Root.AddComponent<CesiumCameraManager>();
            m_Cameras = cameras;
            cameras.useMainCamera = false;
            cameras.useSceneViewCameraInEditor = false;
            if (rig != null)
            {
                m_ViewCamera = rig.controlledCamera;
                cameras.additionalCameras.Add(rig.controlledCamera);
                rig.controlledCamera.farClipPlane = 20000;
            }
            m_Photoreal = Array.IndexOf(Environment.GetCommandLineArgs(), "--twin-cesium-world-terrain") < 0;
            m_Terrain = CreateTileset(m_Photoreal ? "Google Photorealistic 3D Tiles" : "Cesium World Terrain",
                m_Photoreal ? 2275207 : 1,token,6L*1024*1024*1024);
            if (!m_Photoreal)
            {
                var imagery = m_Terrain.gameObject.AddComponent<CesiumIonRasterOverlay>();
                imagery.ionAssetID = 2;
                imagery.ionAccessToken = token;
                imagery.showCreditsOnScreen = true;
                imagery.maximumScreenSpaceError = 1.5f;
                m_Buildings = CreateTileset("Cesium OSM Buildings",96188,token,512L*1024*1024);
                m_Buildings.OnTileGameObjectCreated += go => ProjectTile(go, true);
            }
            m_Terrain.OnTileGameObjectCreated += go => ProjectTile(go, false);
            Cesium3DTileset.OnCesium3DTilesetLoadFailure += LoadFailed;
            m_Root.SetActive(true);
            ClipToNorwegianLand(); // Polygon OnEnable must precede the overlay's native creation.
            m_Credits = CesiumCreditSystem.GetDefaultCreditSystem();
            CreateVideoCredits();
            Status = "loading";
        }

        Cesium3DTileset CreateTileset(string name, long id, string token, long cache)
        {
            var go = new GameObject(name);
            go.transform.SetParent(m_Root.transform, false);
            var tileset = go.AddComponent<Cesium3DTileset>();
            var material = Resources.Load<Material>("TwinCesiumLandscapeMaterial");
            if (material != null) tileset.opaqueMaterial = material;
            tileset.ionAssetID = id;
            tileset.ionAccessToken = token;
            tileset.maximumScreenSpaceError = 8;
            tileset.maximumSimultaneousTileLoads = 24;
            tileset.preloadAncestors = true;
            tileset.preloadSiblings = true;
            tileset.forbidHoles = true;
            tileset.maximumCachedBytes = cache;
            tileset.createPhysicsMeshes = false;
            tileset.showCreditsOnScreen = true;
            return tileset;
        }

        void ClipToNorwegianLand()
        {
            var source = Resources.Load<TextAsset>("NorwayLandMask");
            if (source == null) throw new InvalidDataException("Norwegian N50 land mask missing");
            var mask = JsonUtility.FromJson<LandMask>(source.text);
            var polygons = new List<CesiumCartographicPolygon>();
            foreach (var ring in mask.rings)
            {
                var go = new GameObject("N50 coastline");
                go.transform.SetParent(m_Root.transform,false);
                var polygon = go.AddComponent<CesiumCartographicPolygon>();
                var spline = new Spline();
                foreach (var point in ring.points)
                {
                    var local = go.transform.InverseTransformPoint(new Vector3(point.x,0,point.y));
                    spline.Add(new BezierKnot(new float3(local.x,local.y,local.z)),TangentMode.Linear);
                }
                spline.Closed = true;
                go.GetComponent<SplineContainer>().Spline = spline;
                go.GetComponent<CesiumGlobeAnchor>().detectTransformChanges = false;
                polygons.Add(polygon);
            }
            foreach (var tileset in new[] { m_Terrain, m_Buildings })
            {
                if (tileset == null) continue;
                var clipping = tileset.gameObject.AddComponent<CesiumPolygonRasterOverlay>();
                clipping.materialKey = "Clipping";
                clipping.polygons = polygons;
                clipping.invertSelection = true;
                // Google tiles reproduce the false-outside pruning described in
                // cesium-native #803. Keep the visible mask, without tile-tree pruning.
                clipping.excludeSelectedTiles = false;
            }
            var getPoints = typeof(CesiumCartographicPolygon).GetMethod("GetCartographicPoints",
                System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            int count = 0;
            double minLon = 180, maxLon = -180, minLat = 90, maxLat = -90;
            foreach (var polygon in polygons)
                if (getPoints?.Invoke(polygon,new object[] { m_Terrain.transform.worldToLocalMatrix }) is List<double2> points)
                    foreach (var p in points)
                    { count++; minLon = Math.Min(minLon,p.x); maxLon = Math.Max(maxLon,p.x); minLat = Math.Min(minLat,p.y); maxLat = Math.Max(maxLat,p.y); }
            Debug.Log($"[Sango.Cesium] N50 polygons={polygons.Count} points={count} longitude={minLon:F6}..{maxLon:F6} latitude={minLat:F6}..{maxLat:F6}");
        }

        void ProjectTile(GameObject tile, bool building)
        {
            foreach (var filter in tile.GetComponentsInChildren<MeshFilter>(true))
            {
                var material = filter.GetComponent<MeshRenderer>()?.sharedMaterial;
                if (material != null && material.HasProperty("_AlphaCutoffEnable"))
                {
                    // The SDK unlit template serializes HDRP alpha cutoff as zero.
                    // HDRP 17 therefore disables the polygon mask unless enabled here.
                    material.SetFloat("_AlphaCutoffEnable",1);
                    material.EnableKeyword("_ALPHATEST_ON");
                }
                var source = filter.sharedMesh;
                if (source == null) continue;
                if (!source.isReadable)
                {
                    m_ProjectionFailed = true;
                    Debug.LogWarning("[Sango.Cesium] unreadable mesh; keeping the projected offline terrain");
                    return;
                }
                // The SDK allocates one pooled mesh per primitive and returns the
                // MeshFilter's mesh to that pool when unloading. Modify that mesh in
                // place: replacing/destroying it corrupts the SDK's next pool checkout.
                var mesh = source;
                var vertices = mesh.vertices;
                float nearest = m_ProbeDistance;
                Vector3 probeBefore = Vector3.zero, probeAfter = Vector3.zero;
                bool localTerrain = false;
                for (int i = 0; i < vertices.Length; i++)
                {
                    var world = filter.transform.TransformPoint(vertices[i]);
                    if (Mathf.Abs(world.x) > 25000 || Mathf.Abs(world.z) > 25000) continue;
                    var before = world;
                    world.y += NorwayChartFrame.SeaLevelCorrection(world);
                    if (!building && Mathf.Abs(world.x) < 6000 && Mathf.Abs(world.z) < 6000
                        && world.y > 1 && world.y < 1500) localTerrain = true;
                    float distance = new Vector2(world.x+3000,world.z+2450).magnitude;
                    if (!building && distance < nearest)
                    { nearest = distance; probeBefore = before; probeAfter = world; }
                    vertices[i] = filter.transform.InverseTransformPoint(world);
                }
                if (nearest < m_ProbeDistance && nearest < 100)
                {
                    m_ProbeDistance = nearest;
                    Debug.Log($"[Sango.Cesium] sea-control distance={nearest:F1} before={probeBefore} projected={probeAfter}");
                }
                mesh.vertices = vertices;
                // Preserve provider topology, including triangles crossing the coast.
                // The N50 raster mask clips sea pixels; centroid tests against the coarse
                // fallback DEM remove complete coastal faces and create sawtooth holes.
                mesh.RecalculateBounds();
                // Loading is continuous as the camera moves. Do not draw two different
                // elevation surfaces until a global progress counter happens to hit 100%.
                if (localTerrain) m_OnlineReady = true;
                if (building) m_BuildingMeshes++; else m_TerrainMeshes++;
            }
        }

        void LoadFailed(Cesium3DTilesetLoadFailureDetails details)
        {
            if (details.tileset != m_Terrain && details.tileset != m_Buildings) return;
            Status = "imagery-load-failed";
            // The SDK's full error can contain an authenticated URL. Keep our diagnostics credential-free.
            Debug.LogWarning($"[Sango.Cesium] load failure type={details.type} http={details.httpStatusCode}");
        }

        public void ResetWarmup()
        {
            m_Warmup.Reset(); m_PreloadPositioned = false;
        }

        void UpdateWarmup()
        {
            var own = m_Driver?.OwnShipObject;
            var presentation = m_Bridge?.Presentation;
            if (own == null || presentation == null || m_Driver?.Anchor == null ||
                presentation.run_id != m_Bridge.AttachedRunId) return;
            var route = Array.ConvertAll(presentation.waypoints ?? Array.Empty<TwinDisplayPoint>(), p => {
                var local = m_Driver.Anchor.Value.ToLocal(p.east,p.north);
                return new Vector3(local.x,0,local.y);
            });
            PrepareViews(presentation.run_id, own.transform.position, own.transform.eulerAngles.y, route);
        }

        // Same view-preparation path is exercised by the opt-in renderer evidence fixture.
        public void PrepareViews(string runId, Vector3 position, float heading, Vector3[] route)
        {
            bool changed = m_Warmup.RunId != runId;
            m_Warmup.Begin(runId, Time.unscaledTime);
            if (m_Cameras != null && m_PreloadCameras.Count == 0)
            {
                // Disabled cameras participate in Cesium selection but never render.
                // The uncreated RT supplies a fixed LOD viewport without allocating a hidden frame.
                m_PreloadViewport = new RenderTexture(1024,1024,0);
                for (int i = 0; i < 3; i++)
                {
                    var go = new GameObject("Landscape preload " + i);
                    go.transform.SetParent(transform, false);
                    var camera = go.AddComponent<Camera>(); camera.enabled = false;
                    camera.fieldOfView = 90; camera.aspect = 1; camera.farClipPlane = 3000;
                    camera.targetTexture = m_PreloadViewport;
                    m_PreloadCameras.Add(camera); m_Cameras.additionalCameras.Add(camera);
                }
            }
            if (m_Cameras != null && (changed || !m_PreloadPositioned || (m_Warmup.Ready && Vector3.Distance(position,m_PreloadAnchor) > 200)) && m_ViewCamera != null)
            {
                if (m_StartupView == null)
                {
                    var go = new GameObject("Landscape startup view"); go.transform.SetParent(transform, false);
                    m_StartupView = go.AddComponent<Camera>(); m_StartupView.enabled = false;
                }
                // Match the visible camera exactly; a larger virtual viewport would
                // request detail the actual image cannot show and prolong startup.
                m_StartupView.CopyFrom(m_ViewCamera); m_StartupView.enabled = false;
                m_StartupView.transform.SetPositionAndRotation(m_ViewCamera.transform.position,m_ViewCamera.transform.rotation);
                if (!m_Warmup.Ready) m_Cameras.additionalCameras.Remove(m_ViewCamera);
                if (!m_Cameras.additionalCameras.Contains(m_StartupView)) m_Cameras.additionalCameras.Add(m_StartupView);
            }
            if (changed || !m_PreloadPositioned || (m_Warmup.Ready && Vector3.Distance(position,m_PreloadAnchor) > 200))
            {
                for (int i = 0; i < m_PreloadCameras.Count; i++)
                {
                    var focus = i == 0 ? position : TwinLandscapeWarmup.Ahead(position, route, i * 1000, heading);
                    focus.y = 600;
                    m_PreloadCameras[i].transform.SetPositionAndRotation(focus, Quaternion.Euler(90,0,0));
                }
                m_PreloadPositioned = true; m_PreloadAnchor = position;
            }
            float progress = m_Buildings == null ? TerrainLoad : Mathf.Min(TerrainLoad,BuildingLoad);
            m_Warmup.Observe(Time.unscaledTime, progress, m_Terrain != null,
                m_ProjectionFailed || Status == "imagery-load-failed");
            if (m_Warmup.Ready && m_Cameras != null && m_ViewCamera != null)
            {
                // Keep the startup view hot while the ship remains in this neighbourhood.
                // Camera orbit alone must not evict its already refined shoreline.
                if (!m_Cameras.additionalCameras.Contains(m_ViewCamera)) m_Cameras.additionalCameras.Add(m_ViewCamera);
            }
        }

        void Update()
        {
            UpdateWarmup();
            if (m_Root == null || Time.unscaledTime < m_NextUpdate) return;
            m_NextUpdate = Time.unscaledTime + 2;
            if (m_ProjectionFailed)
            {
                m_Root.SetActive(false);
                Status = "projection-unavailable";
            }
            if (!m_ProjectionFailed && m_TerrainMeshes > 0 && TerrainLoad > 99) m_OnlineReady = true;
            bool ready = m_OnlineReady && !m_ProjectionFailed;
            if (ready) Status = "streaming";
            if (geography != null && geography.tiles != null)
                foreach (var tile in geography.tiles) if (tile != null) tile.drawHeightmap = !ready;
            if (m_CreditCanvas != null)
            {
                m_CreditCanvas.gameObject.SetActive(true); // Attribution survives visual HUD hiding.
                m_CreditCanvas.planeDistance = m_CreditCanvas.worldCamera.nearClipPlane + 0.05f;
            }
            Debug.Log($"[Sango.Cesium] state={Status} terrain={TerrainLoad:F1}% buildings={BuildingLoad:F1}% meshes={m_TerrainMeshes}/{m_BuildingMeshes} warmup={m_Warmup.State} preload={m_PreloadCameras.Count} cacheMiB={(m_Terrain != null ? m_Terrain.maximumCachedBytes / 1048576 : 0)}");
        }

        void CreateVideoCredits()
        {
            var rig = FindFirstObjectByType<CameraRig>();
            var document = m_Credits != null ? m_Credits.GetComponent<UIDocument>() : null;
            if (rig == null || rig.controlledCamera == null || document == null) return;
            // Keep the SDK's provider text, logos and attribution rules intact. Its
            // ordinary screen overlay is not included in camera-based WebRTC capture.
            m_CreditTexture = new RenderTexture(2560,1440,0,RenderTextureFormat.ARGB32)
                { name = "Map attribution for streamed camera" };
            m_CreditTexture.Create();
            m_CreditPanel = Instantiate(document.panelSettings);
            m_CreditPanel.targetTexture = m_CreditTexture;
            m_CreditPanel.clearColor = true;
            m_CreditPanel.colorClearValue = Color.clear;
            document.panelSettings = m_CreditPanel;
            var go = new GameObject("Map attribution",typeof(Canvas));
            go.transform.SetParent(transform,false);
            m_CreditCanvas = go.GetComponent<Canvas>();
            m_CreditCanvas.renderMode = RenderMode.ScreenSpaceCamera;
            m_CreditCanvas.worldCamera = rig.controlledCamera;
            m_CreditCanvas.planeDistance = rig.controlledCamera.nearClipPlane + 0.05f;
            m_CreditCanvas.sortingOrder = 32000;
            var image = new GameObject("Provider credits",typeof(RectTransform),typeof(RawImage));
            image.transform.SetParent(go.transform,false);
            var rect = image.GetComponent<RectTransform>();
            rect.anchorMin = Vector2.zero; rect.anchorMax = Vector2.one;
            rect.offsetMin = rect.offsetMax = Vector2.zero;
            var raw = image.GetComponent<RawImage>();
            raw.texture = m_CreditTexture; raw.raycastTarget = false;
        }

        void OnDestroy()
        {
            Cesium3DTileset.OnCesium3DTilesetLoadFailure -= LoadFailed;
            if (geography != null && geography.tiles != null)
                foreach (var tile in geography.tiles) if (tile != null) tile.drawHeightmap = true;
            if (m_StartupView != null) Destroy(m_StartupView.gameObject);
            foreach (var camera in m_PreloadCameras) if (camera != null) Destroy(camera.gameObject);
            if (m_PreloadViewport != null) Destroy(m_PreloadViewport);
            if (m_Root != null) Destroy(m_Root);
            if (m_CreditCanvas != null) Destroy(m_CreditCanvas.gameObject);
            if (m_CreditTexture != null) { m_CreditTexture.Release(); Destroy(m_CreditTexture); }
            if (m_CreditPanel != null) Destroy(m_CreditPanel);
        }
    }

}
