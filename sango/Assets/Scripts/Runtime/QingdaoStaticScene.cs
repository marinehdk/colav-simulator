using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.RegularExpressions;
using CesiumForUnity;
using Unity.Mathematics;
using UnityEngine;
using UnityEngine.Splines;
using UnityEngine.Profiling;
using UnityEngine.Networking;

namespace Sango
{
    /// <summary>Reusable Qingdao landscape. No vessel, tracker, planner or simulation clock.</summary>
    public sealed class QingdaoStaticScene : MonoBehaviour
    {
        [Serializable] public class TerrainManifest
        {
            public int resolution;
            public double origin_e, origin_n, longitude, latitude;
            public float size_m, base_y, range_y, cesium_scale, cesium_yaw;
            public double[] sea_correction;
            // P1-A cross-check ref: the bake-side feature counts in terrain.json.
            public ShoreworksRef shoreworks;
        }
        [Serializable] public class ShoreworksRef { public string file; public int lines, areas; }
        [Serializable] public class Frame { public double origin_e, origin_n; }
        [Serializable] class Mask { public Ring[] rings; public Ring[] wetRings; }
        [Serializable] class Ring { public Vector2[] points; }
        // P0-C shore-wave placement table (baked by tools/terrain/build_qingdao_static.py
        // from ENC COALNE; quiet harbour/bay water is intentionally unplaced).
        [Serializable] public class ShoreFoamTable
        {
            public string schema;
            public float anchor_x, anchor_z, region_size_m;
            public ShoreFoamEntry[] decals;
        }
        [Serializable] public class ShoreFoamEntry
        {
            public float x, z, yaw_deg, size_x, size_z;
        }
        // P1-A SLCONS shorework extrusion (plan §2 P1-A, D1=A 2026-10-19):
        // the upstream bake shoreworks.json carries buffered line footprints
        // plus digitised area footprints in UTM-window local metres; heights
        // and widths are type-based assumptions (视觉修整、非实测; display
        // only, never navigation).
        [Serializable] public class ShoreworkTable
        {
            public string schema;
            public double origin_e, origin_n;
            public string assumption, note;
            public ShoreworkFeature[] features;
        }
        [Serializable] public class ShoreworkFeature
        {
            public string id, kind, type, elevation_basis;
            public int catslc;
            public float width_m, height_m, length_m;
            // Local UTM metres (east, north) relative to origin. Filled by the
            // ring scanner in ParseShoreworks — JsonUtility cannot read [[e,n]]
            // plain arrays, so the header types below mirror the scalars only.
            public Vector2[] ring;
        }
        [Serializable] class ShoreworkHeader
        {
            public string schema;
            public double origin_e, origin_n;
            public string assumption, note;
            public ShoreworkFeatureHeader[] features;
        }
        [Serializable] class ShoreworkFeatureHeader
        {
            public string id, kind, type, elevation_basis;
            public int catslc;
            public float width_m, height_m, length_m;
        }
        public TerrainManifest Geography { get; private set; }
        public int ShipCount => 0;
        public Action<Frame> onReady;
        TwinSessionDriver m_Driver;
        CameraRig m_Camera;
        GameObject m_Root, m_Online;
        Terrain m_Terrain;
        TerrainData m_Data;
        bool m_NorwayWasActive, m_Opened, m_Failed;
        readonly TwinLandscapeWarmup m_Warmup = new TwinLandscapeWarmup();
        int m_Meshes;
        Cesium3DTileset m_Tiles;
        CesiumRasterOverlay m_Imagery;
        string m_IonToken, m_TiandituToken;
        ImagerySource m_ImagerySource; bool m_ImageryProbeInFlight;
        float m_NextImageryProbe;
        int m_ImageryProbeFailures;
        Camera m_Overview;
        RenderTexture m_OverviewViewport;
        CesiumCameraManager m_Cameras;
        float m_NextMemorySample;
        long m_MeshBytes, m_TextureBytes;
        int m_ResidentMeshes;
        readonly Queue<GameObject> m_Project = new();
        // P0-C shore foam (plan §2 P0-C): decal rig over the baked placement
        // table plus the water-surface decal region it needs to be visible.
        GameObject m_ShoreFoamRoot;
        Transform m_ShoreFoamAnchor;
        ShoreFoamTable m_ShoreFoamTable;
        bool m_ShoreFoamEnabled = true;
        UnityEngine.Rendering.HighDefinition.WaterSurface m_ShoreWater;
        Transform m_PreviousFoamAnchor;
        Vector2 m_PreviousFoamRegionSize;
        UnityEngine.Rendering.HighDefinition.WaterSurface.WaterDecalRegionResolution
            m_PreviousDeformationRes, m_PreviousFoamResolution;
        // P1-A shore volumes (plan §2 P1-A): the SLCONS extrusion rig built from
        // the baked table, parented to m_Root in the LocalPosition UTM frame.
        GameObject m_ShoreworkRoot;
        bool m_ShoreworksEnabled = false; // phase-1 satellite-first: opt-in via TWIN_QINGDAO_SHOREWORKS=1
        // Steady-state frame-budget guard (2026-10-19 P0-A), copied from the
        // Norwegian TwinCesiumLandscape precedent: cap per-frame tile
        // reprojection by time, not tile count, so load bursts during camera
        // swings cannot stall the projection main thread.
        const float k_ProjectionBudgetMs = 1.5f;
        // P1-B (2026-10-19): imagery source switch, env-driven and either/or —
        // never a second imagery overlay, the overlay budget stays
        // imagery+Clipping+WaterMask=3. Default flipped from ion to ArcGIS on
        // 2026-10-21 (see k_ArcgisWmts).
        const string k_TiandituWmts = "https://t0.tianditu.gov.cn/img_w/wmts";
        // Default imagery since 2026-10-21: ion asset 2's Bing tile CDN
        // (t*.virtualearth.net) is unreachable from the a4000 deployment network
        // (six-leg curl evidence: direct and clash both 000 while the REST
        // metadata host answers 200 — tiles only ever fail), so ion imagery
        // renders black. ArcGIS World_Imagery WMTS answers on both legs keyless.
        // Credit: Esri, Maxar, Earthstar Geographics, and the GIS User Community.
        const string k_ArcgisWmts = "https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/WMTS";
        // Health probe cadence: one z7 tile GET per 10 min (~144/day) is noise
        // against the daily quota yet bounds the quota-outage blind window —
        // cesium-unity 1.26 surfaces per-tile raster failures to no C# event.
        const float k_ImageryProbeInterval = 600f;
        const int k_ImageryProbeLevel = 7;
        // P1-A tooth-embed constants (视觉修整、非实测; registered in
        // asset-registry): deck faces lift this far above the assumed type
        // height so they never z-fight the DEM surface, and every skirt wall
        // reaches at least k_ShoreworkSkirtMinDepth below its top, or this far
        // below the sampled offline terrain height — whichever is lower — so
        // volumes stay buried where online World Terrain differs from the
        // offline grid (±50 m ZOC B registration band, plan §2 P1-A risks).
        const float k_ShoreworkTopLift = 0.3f;
        const float k_ShoreworkSkirtMinDepth = 12f;
        const float k_ShoreworkSkirtBelowTerrain = 6f;

        public TwinBridgeLandscapeState Describe()
        {
            float progress = m_Tiles != null ? m_Tiles.ComputeLoadProgress() : 100;
            bool ready = m_Warmup.Ready;
            return new TwinBridgeLandscapeState { ready=ready, displayable=m_Opened && m_Terrain!=null,
                state=m_Warmup.State,
                progress=progress, terrain_load=progress, meshes_created=m_Meshes,
                cache_bytes=m_Tiles!=null ? m_Tiles.maximumCachedBytes : 0,
                cache_budget_bytes=m_Tiles?.maximumCachedBytes ?? 0,
                mesh_memory_bytes=m_MeshBytes, texture_memory_bytes=m_TextureBytes,
                meshes_resident=m_ResidentMeshes, process_rss_bytes=System.Diagnostics.Process.GetCurrentProcess().WorkingSet64,
                refining=ready && progress<99, extent_m=Geography!=null ? Geography.size_m : 0 };
        }

        public static Vector3 LocalPosition(double east, double north, TerrainManifest geography)
            => new Vector3((float)(east-geography.origin_e),0,(float)(north-geography.origin_n));

        public void Open(TwinSessionDriver driver, CameraRig camera)
        {
            m_Driver=driver; m_Camera=camera;
            if (!m_Opened)
            {
                m_Opened=true;
                m_NorwayWasActive=driver.geography!=null && driver.geography.gameObject.activeSelf;
                if(driver.geography!=null) driver.geography.gameObject.SetActive(false);
                if(m_Root==null) { BuildTerrain(); BuildShoreworks(); BuildOnline(); }
                else {
                    foreach(var renderer in m_Root.GetComponentsInChildren<Renderer>()) renderer.enabled=true;
                    if(m_Tiles!=null) m_Tiles.suspendUpdate=false;
                    // P1-B: a runtime Tianditu fallback is session-scoped, not one-way —
                    // every entry re-reads the environment and retries the configured source.
                    if(m_Tiles!=null) ApplyImagerySource();
                    // P0-C: re-entry re-shows the retained decal rig and re-claims the
                    // water region (Clear restored the pre-attach camera-follow state).
                    if(m_ShoreFoamRoot!=null)
                    {
                        if(m_ShoreFoamTable!=null) ClaimShoreFoamRegion(m_ShoreFoamTable);
                        m_ShoreFoamRoot.SetActive(m_ShoreFoamEnabled);
                    }
                    // P1-A: re-entry re-shows the retained shore volumes. Their
                    // renderers sit under a root that Clear deactivated, so the
                    // active-only loop above never reached them — restore them
                    // here or the reshown rig would stay invisible.
                    if(m_ShoreworkRoot!=null)
                    {
                        m_ShoreworkRoot.SetActive(m_ShoreworksEnabled);
                        foreach(var renderer in m_ShoreworkRoot.GetComponentsInChildren<Renderer>(true)) renderer.enabled=true;
                    }
                }
            }
            Camera("overlook");
            onReady?.Invoke(new Frame { origin_e=Geography.origin_e, origin_n=Geography.origin_n });
        }

        void BuildTerrain()
        {
            var manifest=Resources.Load<TextAsset>("Qingdao/terrain");
            var raw=Resources.Load<TextAsset>("Qingdao/heights");
            if(manifest==null || raw==null) throw new InvalidOperationException("Qingdao offline terrain missing");
            Geography=JsonUtility.FromJson<TerrainManifest>(manifest.text);
            var bytes=raw.bytes; int n=Geography.resolution;
            if(bytes.Length!=n*n*2) throw new InvalidOperationException("Qingdao heightmap size mismatch");
            var heights=new float[n,n];
            for(int y=0;y<n;y++) for(int x=0;x<n;x++)
            { int i=(y*n+x)*2; heights[y,x]=(bytes[i]|bytes[i+1]<<8)/65535f; }
            var references=m_Driver.geography?.tiles;
            var reference=references!=null && references.Length>0 ? references[0] : null;
            if(reference==null) throw new InvalidOperationException("Terrain material reference missing");
            m_Data=new TerrainData { heightmapResolution=n, size=new Vector3(Geography.size_m,Geography.range_y,Geography.size_m),
                alphamapResolution=512,baseMapResolution=1024 };
            m_Data.SetHeights(0,0,heights); m_Data.terrainLayers=reference.terrainData.terrainLayers;
            var weights=new float[512,512,m_Data.terrainLayers.Length];
            for(int y=0;y<512;y++) for(int x=0;x<512;x++) weights[y,x,0]=1;
            m_Data.SetAlphamaps(0,0,weights);
            m_Root=new GameObject("Qingdao geographic landscape EPSG32651");
            m_Warmup.Begin("qingdao",Time.unscaledTime);
            var go=Terrain.CreateTerrainGameObject(m_Data); go.transform.SetParent(m_Root.transform,false);
            go.transform.position=new Vector3(-Geography.size_m/2,Geography.base_y,-Geography.size_m/2);
            m_Terrain=go.GetComponent<Terrain>(); m_Terrain.materialTemplate=reference.materialTemplate;
            m_Terrain.heightmapPixelError=3; m_Terrain.drawInstanced=true; m_Terrain.basemapDistance=20000;
        }

        void BuildOnline()
        {
            string path=Environment.GetEnvironmentVariable("COLAV_CESIUM_TOKEN_FILE");
            if(string.IsNullOrWhiteSpace(path)) path=Path.Combine(Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData),"colav-twin-renderer","cesium-ion-token");
            if(!File.Exists(path)) return;
            string token=File.ReadAllText(path).Trim();
            if(!Regex.IsMatch(token,@"^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$"))
                throw new InvalidOperationException("Invalid Cesium token file");
            m_Online=new GameObject("Qingdao satellite terrain");
            m_Online.SetActive(false); m_Online.transform.SetParent(m_Root.transform,false);
            m_Online.transform.localRotation=Quaternion.Euler(0,Geography.cesium_yaw,0);
            m_Online.transform.localScale=new Vector3(Geography.cesium_scale,1,Geography.cesium_scale);
            var geo=m_Online.AddComponent<CesiumGeoreference>(); geo.Initialize();
            geo.SetOriginLongitudeLatitudeHeight(Geography.longitude,Geography.latitude,0);
            var cameras=m_Online.AddComponent<CesiumCameraManager>();
            m_Cameras=cameras;
            cameras.useMainCamera=false; cameras.useSceneViewCameraInEditor=false;
            cameras.additionalCameras.Add(m_Camera.controlledCamera);
            var overviewGo=new GameObject("Qingdao coarse overview preload");
            overviewGo.transform.SetParent(m_Root.transform,false);
            m_Overview=overviewGo.AddComponent<Camera>();m_Overview.enabled=false;
            m_Overview.fieldOfView=80;m_Overview.aspect=1;m_Overview.farClipPlane=25000;
            m_Overview.transform.SetPositionAndRotation(new Vector3(0,12000,0),Quaternion.Euler(90,0,0));
            m_OverviewViewport=new RenderTexture(1024,1024,0);m_Overview.targetTexture=m_OverviewViewport;
            cameras.additionalCameras.Add(m_Overview);
            m_Camera.controlledCamera.farClipPlane=25000;
            // 2 GiB cache (2026-10-19 P0-A): the Norwegian link holds its whole
            // scenario family in 4 GiB with VRAM headroom (TwinCesiumLandscape
            // k_FullCacheBytes rationale); a static no-vessel scene needs half
            // that, keeping refined detail tiles resident across camera swings.
            // Verify on the a4000 via Describe()'s cache/rss fields.
            m_Tiles=Tiles("Qingdao World Terrain",1,token,2L*1024*1024*1024);
            // P1-B: imagery source is env-driven (either/or). Without
            // TWIN_QINGDAO_IMAGERY=tianditu this builds the same ion asset 2
            // overlay as before, with identical fields and ordering.
            m_IonToken=token;
            ApplyImagerySource();
            m_Tiles.OnTileGameObjectCreated+=go=>m_Project.Enqueue(go);
            Cesium3DTileset.OnCesium3DTilesetLoadFailure+=LoadFailed;
            m_Online.SetActive(true);
            var mask=JsonUtility.FromJson<Mask>(Resources.Load<TextAsset>("Qingdao/land-mask").text);
            var clipPolygons=BuildPolygons(mask.rings,"ENC land clip");
            var clip=m_Tiles.gameObject.AddComponent<CesiumPolygonRasterOverlay>();
            clip.materialKey="Clipping";clip.polygons=clipPolygons;clip.invertSelection=true;clip.excludeSelectedTiles=false;
            // Binary water/land mask (plan P0-B): the wet rings erode the landline by the
            // baked band, so this overlay selects water plus a land-side intertidal band;
            // the cloned Qingdao material darkens/desaturates imagery there. Overlay
            // budget stays exactly three: imagery + Clipping + WaterMask.
            // 2026-10-21 A/B hatch: TWIN_QINGDAO_WATER_MASK=0 skips the overlay
            // (imagery then paints untinted through the clone's unbound mask slot).
            bool waterMaskOn=Environment.GetEnvironmentVariable("TWIN_QINGDAO_WATER_MASK")!="0";
            var waterPolygons=waterMaskOn?BuildPolygons(mask.wetRings??new Ring[0],"ENC wet band"):new List<CesiumCartographicPolygon>();
            if(waterPolygons.Count>0)
            {
                var water=m_Tiles.gameObject.AddComponent<CesiumPolygonRasterOverlay>();
                water.materialKey="WaterMask";water.polygons=waterPolygons;water.invertSelection=true;water.excludeSelectedTiles=false;
            }
            else if(!waterMaskOn) Debug.Log("[Sango.Qingdao] water mask overlay disabled by env");
            Debug.Log("[Sango.Qingdao] satellite terrain loading; EPSG32651; no buildings or vessels");
            BuildShoreFoam();
        }

        /// <summary>Parse the baked shore-foam placement table; null when the
        /// document is absent or fails the schema sanity checks.</summary>
        public static ShoreFoamTable ParseShoreFoam(string json)
        {
            if(string.IsNullOrWhiteSpace(json)) return null;
            ShoreFoamTable table;
            try { table=JsonUtility.FromJson<ShoreFoamTable>(json); } catch(ArgumentException) { return null; }
            if(table==null || table.schema!="qingdao-shorefoam.v1") return null;
            if(table.decals==null || table.decals.Length==0 || table.region_size_m<=0) return null;
            foreach(var entry in table.decals)
                if(entry.size_x<=0 || entry.size_z<=0) return null;
            return table;
        }

        /// <summary>Instantiate one WaterDecal per baked entry under parent.
        /// Decal local +X is landward (waves run up toward the shore), local Z
        /// runs along the coast; ScaleInvariant keeps regionSize metric.</summary>
        public static UnityEngine.Rendering.HighDefinition.WaterDecal[] BuildShoreFoamDecals(
            Transform parent,ShoreFoamTable table,Material material)
        {
            var decals=new UnityEngine.Rendering.HighDefinition.WaterDecal[table.decals.Length];
            for(int i=0;i<table.decals.Length;i++)
            {
                var entry=table.decals[i];
                var go=new GameObject($"Qingdao shore wave {i}");
                go.transform.SetParent(parent,false);
                go.transform.localPosition=new Vector3(entry.x,0,entry.z);
                go.transform.localRotation=Quaternion.Euler(0,entry.yaw_deg,0);
                var decal=go.AddComponent<UnityEngine.Rendering.HighDefinition.WaterDecal>();
                decal.material=material;
                decal.scaleMode=UnityEngine.Rendering.HighDefinition.DecalScaleMode.ScaleInvariant;
                decal.regionSize=new Vector2(entry.size_x,entry.size_z);
                // First-guess visual constants (视觉修整、非实测): the shore-wave
                // branch is Time-driven noise, so the atlas must refresh per frame.
                decal.amplitude=0.25f;
                decal.surfaceFoamDimmer=0.8f;
                decal.deepFoamDimmer=0.6f;
                decal.resolution=new Vector2Int(256,256);
                decal.updateMode=CustomRenderTextureUpdateMode.Realtime;
                decals[i]=decal;
            }
            return decals;
        }

        /// <summary>Parse the baked SLCONS shorework table. Rings are [[e,n]]
        /// plain arrays, which JsonUtility cannot read, so scalar fields go
        /// through JsonUtility and rings through a targeted depth-scanning
        /// parser; JSON nulls (width_m/length_m/catslc on area features) are
        /// stripped first and read as zero. Null when absent or malformed —
        /// strict parse, one bad feature rejects the document so the rig is
        /// never half-built.</summary>
        public static ShoreworkTable ParseShoreworks(string json)
        {
            if(string.IsNullOrWhiteSpace(json)) return null;
            json=Regex.Replace(json,@",?""[A-Za-z_0-9]+"":null",string.Empty);
            ShoreworkHeader header;
            try { header=JsonUtility.FromJson<ShoreworkHeader>(json); } catch(ArgumentException) { return null; }
            if(header?.features==null || header.features.Length==0) return null;
            var table=new ShoreworkTable { schema=header.schema, origin_e=header.origin_e, origin_n=header.origin_n,
                assumption=header.assumption, note=header.note, features=new ShoreworkFeature[header.features.Length] };
            for(int i=0;i<header.features.Length;i++)
            {
                var f=header.features[i];
                table.features[i]=new ShoreworkFeature { id=f.id, kind=f.kind, type=f.type,
                    elevation_basis=f.elevation_basis, catslc=f.catslc, width_m=f.width_m, height_m=f.height_m, length_m=f.length_m };
            }
            if(table.schema!="qingdao-shoreworks.v1") return null;
            if(!TryScanShoreworkRings(json,table.features)) return null;
            foreach(var f in table.features)
            {
                if(f==null || string.IsNullOrEmpty(f.id)) return null;
                if(f.kind!="line" && f.kind!="area") return null;
                if(f.height_m<=0 || f.ring==null) return null;
                if(f.kind=="line" && (f.width_m<=0 || f.ring.Length<2)) return null;
                if(f.kind=="area" && f.ring.Length<3) return null;
            }
            return table;
        }

        /// <summary>Fill features[i].ring by scanning each {…} member of the
        /// "features":[…] array for its "ring":[[e,n],…] value.</summary>
        static bool TryScanShoreworkRings(string json,ShoreworkFeature[] features)
        {
            int featuresAt=json.IndexOf("\"features\":[",StringComparison.Ordinal);
            if(featuresAt<0) return false;
            int i=json.IndexOf('[',featuresAt+11)+1; // step past the array bracket
            for(int f=0;f<features.Length;f++)
            {
                while(i<json.Length && char.IsWhiteSpace(json[i]) || i<json.Length && json[i]==',') i++;
                if(i>=json.Length || json[i]!='{') return false;
                int end=ScanBalanced(json,i,'{','}');
                if(end<0) return false;
                var ring=ScanShoreworkRing(json,i,end);
                if(ring==null) return false;
                features[f].ring=ring;
                i=end+1;
            }
            return true;
        }

        /// <summary>Index of the bracket/brace closing the one at open, or -1;
        /// string literals are skipped so braces inside them cannot confuse it.</summary>
        static int ScanBalanced(string json,int open,char openChar,char closeChar)
        {
            int depth=0; bool quoted=false;
            for(int i=open;i<json.Length;i++)
            {
                char c=json[i];
                if(quoted) { if(c=='\\') i++; else if(c=='"') quoted=false; continue; }
                if(c=='"') quoted=true;
                else if(c==openChar) depth++;
                else if(c==closeChar && --depth==0) return i;
            }
            return -1;
        }

        /// <summary>Parse the [e,n] pairs of the "ring" array between json
        /// positions [start,end). Null when absent, empty or non-numeric.</summary>
        static Vector2[] ScanShoreworkRing(string json,int start,int end)
        {
            int at=json.IndexOf("\"ring\"",start,Math.Max(0,end-start),StringComparison.Ordinal);
            if(at<0) return null;
            int open=json.IndexOf('[',at+6);
            if(open<0 || open>end) return null;
            int close=ScanBalanced(json,open,'[',']');
            if(close<0) return null;
            var points=new List<Vector2>();
            int i=open+1;
            while(i<close)
            {
                while(i<close && json[i]!='[') i++;
                if(i>=close) break;
                int comma=json.IndexOf(',',i,close-i);
                int shut=json.IndexOf(']',i,close-i);
                if(comma<0 || shut<0 || comma>shut) return null;
                if(!float.TryParse(json.Substring(i+1,comma-i-1).Trim(),NumberStyles.Float,CultureInfo.InvariantCulture,out float east) ||
                   !float.TryParse(json.Substring(comma+1,shut-comma-1).Trim(),NumberStyles.Float,CultureInfo.InvariantCulture,out float north))
                    return null;
                points.Add(new Vector2(east,north));
                i=shut+1;
            }
            return points.Count>=2 ? points.ToArray() : null;
        }

        /// <summary>Dedupe consecutive repeated points (S-57 digitisation) and
        /// drop the repeated closer of already-closed rings.</summary>
        static Vector2[] ShoreworkDedupe(Vector2[] points)
        {
            var clean=new List<Vector2>(points.Length);
            foreach(var p in points)
                if(clean.Count==0 || (p-clean[clean.Count-1]).sqrMagnitude>1e-4f) clean.Add(p);
            if(clean.Count>1 && (clean[0]-clean[clean.Count-1]).sqrMagnitude<=1e-4f) clean.RemoveAt(clean.Count-1);
            return clean.ToArray();
        }

        /// <summary>Twice the signed area of a ring in the XZ plane; positive
        /// means counter-clockwise seen from above (+y).</summary>
        public static float ShoreworkRingArea(Vector2[] ring)
        {
            float area=0;
            for(int i=0;i<ring.Length;i++)
            {
                int j=(i+1)%ring.Length;
                area+=ring[i].x*ring[j].y-ring[j].x*ring[i].y;
            }
            return area;
        }

        /// <summary>Buffer a line spine by its assumed width into a closed
        /// outline ring — miter joins clamped so sharp digitised reversals
        /// cannot spike (offset at most ~2.9x the half-width).</summary>
        public static Vector2[] ShoreworkLineRing(Vector2[] spine,float width)
        {
            int n=spine.Length;
            if(n<2) return null;
            var outline=new Vector2[2*n];
            for(int i=0;i<n;i++)
            {
                var inbound=i>0 ? spine[i]-spine[i-1] : Vector2.zero;
                var outbound=i<n-1 ? spine[i+1]-spine[i] : Vector2.zero;
                var tangent=inbound+outbound;
                if(tangent.sqrMagnitude<1e-8f) tangent=outbound.sqrMagnitude>0 ? outbound : inbound;
                tangent.Normalize();
                var miter=new Vector2(-tangent.y,tangent.x);
                float cos=1f;
                if(inbound.sqrMagnitude>0)
                    cos=Mathf.Min(cos,Mathf.Abs(Vector2.Dot(miter,new Vector2(-inbound.y,inbound.x).normalized)));
                if(outbound.sqrMagnitude>0)
                    cos=Mathf.Min(cos,Mathf.Abs(Vector2.Dot(miter,new Vector2(-outbound.y,outbound.x).normalized)));
                var offset=miter*(width*0.5f/Mathf.Max(0.35f,cos));
                outline[i]=spine[i]+offset;
                outline[n+i]=spine[n-1-i]-offset;
            }
            return outline;
        }

        /// <summary>Ear-clipping triangulation of a simple polygon in the XZ
        /// plane (counter-clockwise seen from above). If no ear is found —
        /// slightly self-touching digitised rings — it degrades to a fan from
        /// vertex 0; display-grade geometry, not a computational-geometry
        /// contract.</summary>
        public static int[] ShoreworkTriangles(Vector2[] ring)
        {
            int m=ring.Length;
            var tris=new List<int>((m-2)*3);
            var live=new List<int>(m);
            for(int i=0;i<m;i++) live.Add(i);
            int guard=0;
            while(live.Count>3 && guard++<m*m)
            {
                bool clipped=false;
                for(int a=0;a<live.Count && !clipped;a++)
                {
                    int b=(a+1)%live.Count, c=(a+2)%live.Count;
                    var pa=ring[live[a]]; var pb=ring[live[b]]; var pc=ring[live[c]];
                    if((pb.x-pa.x)*(pc.y-pa.y)-(pb.y-pa.y)*(pc.x-pa.x)<=1e-6f) continue; // reflex or collinear
                    bool contains=false;
                    for(int t=0;t<live.Count;t++)
                    {
                        if(t==a||t==b||t==c) continue;
                        if(ShoreworkPointInTriangle(ring[live[t]],pa,pb,pc)) { contains=true; break; }
                    }
                    if(contains) continue;
                    tris.Add(live[a]); tris.Add(live[b]); tris.Add(live[c]);
                    live.RemoveAt(b);
                    clipped=true;
                }
                if(!clipped) break;
            }
            if(live.Count==3) { tris.Add(live[0]); tris.Add(live[1]); tris.Add(live[2]); }
            if(tris.Count/3!=m-2)
            {
                tris.Clear();
                for(int i=1;i<m-1;i++) { tris.Add(0); tris.Add(i); tris.Add(i+1); }
            }
            return tris.ToArray();
        }

        static bool ShoreworkPointInTriangle(Vector2 p,Vector2 a,Vector2 b,Vector2 c)
        {
            float d1=ShoreworkCross(p,a,b), d2=ShoreworkCross(p,b,c), d3=ShoreworkCross(p,c,a);
            bool negative=d1<0||d2<0||d3<0, positive=d1>0||d2>0||d3>0;
            return !(negative&&positive);
        }

        static float ShoreworkCross(Vector2 a,Vector2 b,Vector2 c)
            =>(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);

        /// <summary>Snapshot of the offline height grid (normalised 0..1) for
        /// shorework skirt sampling — one allocation for the whole build, since
        /// per-vertex GetHeights calls would each copy the whole grid.</summary>
        public static float[,] ReadShoreworkHeightGrid(TerrainData data)
            => data!=null ? data.GetHeights(0,0,data.heightmapResolution,data.heightmapResolution) : null;

        /// <summary>Offline DEM height at a local (east, north) in the
        /// LocalPosition frame, bilinear over the height grid snapshot. Axis
        /// note: BuildTerrain passes the bake grid straight to SetHeights and
        /// the bake (build_qingdao_static.py meshgrid+flipud) writes south→north
        /// rows into the first index, west→east into the second; GetHeights
        /// round-trips that layout (GetInterpolatedHeight proved unreadable
        /// here — see QingdaoStaticSceneTests probe history).</summary>
        public static float ShoreworkTerrainHeight(TerrainManifest geography,float[,] heights,Vector2 local)
        {
            if(geography==null || heights==null) return 0f;
            int n=heights.GetLength(0);
            float half=geography.size_m*0.5f;
            float u=Mathf.Clamp01((local.x+half)/geography.size_m)*(n-1); // east → second index
            float v=Mathf.Clamp01((local.y+half)/geography.size_m)*(n-1); // north → first index
            int x0=Mathf.Min((int)u,n-2), y0=Mathf.Min((int)v,n-2);
            float tx=u-x0, ty=v-y0;
            float south=heights[y0,  x0  ]*(1-tx)+heights[y0,  x0+1]*tx;
            float north=heights[y0+1,x0  ]*(1-tx)+heights[y0+1,x0+1]*tx;
            return (float)geography.base_y+(south*(1-ty)+north*ty)*geography.range_y;
        }

        /// <summary>Extrude one footprint into a display-grade low-poly volume
        /// in UTM-window local metres: line features buffered by width_m,
        /// area features extruded as digitised. The deck sits at the assumed
        /// type height plus k_ShoreworkTopLift, the skirt walls run down to
        /// the tooth-embed floor — below both a fixed minimum depth and the
        /// sampled offline terrain — and the bottom face is omitted because it
        /// is buried below water and terrain by construction.</summary>
        public static Mesh BuildShoreworkMesh(ShoreworkFeature feature,Func<Vector2,float> terrainHeight)
        {
            var spine=ShoreworkDedupe(feature.ring);
            var ring=feature.kind=="line" ? ShoreworkLineRing(spine,feature.width_m) : spine;
            if(ring==null || ring.Length<3) return null;
            if(ShoreworkRingArea(ring)<0) System.Array.Reverse(ring); // CCW seen from above
            float top=feature.height_m+k_ShoreworkTopLift;
            float floor=top-k_ShoreworkSkirtMinDepth;
            int m=ring.Length;
            var vertices=new Vector3[3*m]; // m deck + m wall-top + m wall-bottom
            for(int i=0;i<m;i++)
            {
                float bottom=Mathf.Min(floor,(terrainHeight!=null ? terrainHeight(ring[i]) : 0f)-k_ShoreworkSkirtBelowTerrain);
                vertices[i]=new Vector3(ring[i].x,top,ring[i].y);
                vertices[m+i]=new Vector3(ring[i].x,top,ring[i].y);
                vertices[2*m+i]=new Vector3(ring[i].x,bottom,ring[i].y);
            }
            var tris=new List<int>((m-2)*3+m*6);
            var ears=ShoreworkTriangles(ring);
            for(int t=0;t<ears.Length;t+=3)
            { // reversed: a CCW-from-above ring is back-face seen from above
                tris.Add(ears[t]); tris.Add(ears[t+2]); tris.Add(ears[t+1]);
            }
            for(int i=0;i<m;i++)
            { // exterior walls: CCW-from-above keeps the outside on the right
                int j=(i+1)%m;
                tris.Add(m+i); tris.Add(m+j); tris.Add(2*m+j);
                tris.Add(m+i); tris.Add(2*m+j); tris.Add(2*m+i);
            }
            var mesh=new Mesh { name="Qingdao shorework "+feature.id };
            mesh.SetVertices(vertices);
            mesh.SetTriangles(tris,0);
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            return mesh;
        }

        /// <summary>Instantiate one volume per table feature under parent, in
        /// the LocalPosition UTM frame — no Cesium curvature correction
        /// applies to these planar assets. Wharfs and revetments get the
        /// dressed-stone material, everything else concrete. Returns the
        /// number of volumes created; degenerate footprints are skipped.</summary>
        public static int BuildShoreworkInstances(ShoreworkTable table,Transform parent,
            Material concrete,Material stone,Func<Vector2,float> terrainHeight)
        {
            int created=0;
            foreach(var f in table.features)
            {
                var mesh=BuildShoreworkMesh(f,terrainHeight);
                if(mesh==null) continue;
                var go=new GameObject($"Qingdao shorework {f.id} {f.type}");
                go.transform.SetParent(parent,false);
                go.AddComponent<MeshFilter>().sharedMesh=mesh;
                go.AddComponent<MeshRenderer>().sharedMaterial=
                    (f.type=="wharf"||f.type=="revetment") && stone!=null ? stone : concrete;
                created++;
            }
            return created;
        }

        /// <summary>Shore-foam master switch (default on; TWIN_QINGDAO_SHORE_FOAM=0
        /// disables at build). Off hides the decal rig without touching the water.</summary>
        public bool shoreFoamEnabled
        {
            get { return m_ShoreFoamEnabled; }
            set
            {
                m_ShoreFoamEnabled=value;
                if(m_ShoreFoamRoot!=null) m_ShoreFoamRoot.SetActive(value);
            }
        }

        void BuildShoreFoam()
        {
            var table=ParseShoreFoam(Resources.Load<TextAsset>("Qingdao/shorefoam")?.text);
            var material=Resources.Load<Material>("Qingdao/QingdaoShoreWave");
            if(table==null || material==null)
            {
                Debug.Log("[Sango.Qingdao] shore foam table or material missing; shore waves off");
                return;
            }
            m_ShoreFoamRoot=new GameObject("Qingdao shore foam");
            m_ShoreFoamRoot.transform.SetParent(m_Root.transform,false);
            var anchorGo=new GameObject("Qingdao shore foam region");
            anchorGo.transform.SetParent(m_ShoreFoamRoot.transform,false);
            anchorGo.transform.localPosition=new Vector3(table.anchor_x,0,table.anchor_z);
            m_ShoreFoamAnchor=anchorGo.transform;
            m_ShoreFoamTable=table;
            BuildShoreFoamDecals(m_ShoreFoamRoot.transform,table,material);
            // The serialized water surface keeps a 108 m camera-following region
            // (SangoTwin.unity decalRegionSize/decalRegionAnchor), which shows none
            // of the baked segments kilometres from the origin. A stationary anchor
            // on the baked cluster centroid wins over following the camera: HDRP
            // 17.3 does not rebind the graphics foam target when the region moves
            // (TwinSessionDriver precedent), and visibility of a region-covered
            // decal does not depend on the camera in the first place.
            ClaimShoreFoamRegion(table);
            m_ShoreFoamEnabled=Environment.GetEnvironmentVariable("TWIN_QINGDAO_SHORE_FOAM")!="0";
            m_ShoreFoamRoot.SetActive(m_ShoreFoamEnabled);
            Debug.Log($"[Sango.Qingdao] shore foam wired: {table.decals.Length} segments, region {table.region_size_m:F0} m");
        }

        void BuildShoreworks()
        {
            var table=ParseShoreworks(Resources.Load<TextAsset>("Qingdao/shoreworks")?.text);
            var concrete=Resources.Load<Material>("Qingdao/QingdaoShoreworkConcrete");
            var stone=Resources.Load<Material>("Qingdao/QingdaoShoreworkStone");
            if(table==null || concrete==null || stone==null)
            {
                Debug.Log("[Sango.Qingdao] shorework table or materials missing; shore volumes off");
                return;
            }
            if(table.origin_e!=Geography.origin_e || table.origin_n!=Geography.origin_n)
                Debug.LogWarning("[Sango.Qingdao] shorework table origin disagrees with the terrain manifest; rings still placed in terrain-local metres");
            m_ShoreworkRoot=new GameObject("Qingdao shoreworks");
            m_ShoreworkRoot.transform.SetParent(m_Root.transform,false);
            int lines=0, areas=0;
            foreach(var f in table.features) { if(f.kind=="line") lines++; else areas++; }
            var expected=Geography.shoreworks;
            if(expected!=null && (expected.lines!=lines || expected.areas!=areas))
                Debug.LogWarning($"[Sango.Qingdao] shorework table {lines}/{areas} disagrees with manifest {expected.lines}/{expected.areas}; table wins");
            var heightGrid=ReadShoreworkHeightGrid(m_Data);
            int created=BuildShoreworkInstances(table,m_ShoreworkRoot.transform,concrete,stone,
                local=>ShoreworkTerrainHeight(Geography,heightGrid,local));
            m_ShoreworksEnabled=Environment.GetEnvironmentVariable("TWIN_QINGDAO_SHOREWORKS")=="1";
            m_ShoreworkRoot.SetActive(m_ShoreworksEnabled);
            Debug.Log($"[Sango.Qingdao] shoreworks wired: {created} volumes ({lines} buffered lines + {areas} areas), default OFF (phase-1 satellite-first 2026-10-21; TWIN_QINGDAO_SHOREWORKS=1 opts in), UTM local under m_Root; heights/widths assumed (视觉修整、非实测)");
        }

        /// <summary>Shorework master switch (default OFF since 2026-10-21,
        /// phase-1 satellite-first: raw imagery + Unity water, volumes only with
        /// TWIN_QINGDAO_SHOREWORKS=1). Off hides the volume rig without touching
        /// the terrain or water.</summary>
        public bool shoreworksEnabled
        {
            get { return m_ShoreworksEnabled; }
            set { m_ShoreworksEnabled=value; if(m_ShoreworkRoot!=null) m_ShoreworkRoot.SetActive(value); }
        }

        void ClaimShoreFoamRegion(ShoreFoamTable table)
        {
            var water=m_Driver!=null ? m_Driver.water : null;
            if(water==null) water=FindFirstObjectByType<UnityEngine.Rendering.HighDefinition.WaterSurface>();
            if(water==null) return;
            if(m_ShoreWater==water && water.decalRegionAnchor==m_ShoreFoamAnchor) return; // already claimed
            m_ShoreWater=water;
            m_PreviousFoamAnchor=water.decalRegionAnchor;
            m_PreviousFoamRegionSize=water.decalRegionSize;
            m_PreviousDeformationRes=water.deformationRes;
            m_PreviousFoamResolution=water.foamResolution;
            water.deformation=water.foam=true; // decal passes invisible with either off
            water.decalRegionAnchor=m_ShoreFoamAnchor;
            water.decalRegionSize=new Vector2(table.region_size_m,table.region_size_m);
            water.deformationRes=UnityEngine.Rendering.HighDefinition.WaterSurface.WaterDecalRegionResolution.Resolution512;
            water.foamResolution=UnityEngine.Rendering.HighDefinition.WaterSurface.WaterDecalRegionResolution.Resolution1024;
        }

        void ReleaseShoreFoamRegion()
        {
            if(m_ShoreWater==null) return;
            if(m_ShoreWater.decalRegionAnchor==m_ShoreFoamAnchor)
            {
                m_ShoreWater.decalRegionAnchor=m_PreviousFoamAnchor;
                m_ShoreWater.decalRegionSize=m_PreviousFoamRegionSize;
                m_ShoreWater.deformationRes=m_PreviousDeformationRes;
                m_ShoreWater.foamResolution=m_PreviousFoamResolution;
            }
            m_ShoreWater=null;
        }

        public enum ImagerySource { Ion, Tianditu, Arcgis }

        /// <summary>TWIN_QINGDAO_IMAGERY selects the imagery source: unset,
        /// "arcgis" and unrecognized values resolve to ArcGIS World_Imagery
        /// (default since 2026-10-21 — the Bing tile CDN behind ion asset 2 is
        /// unreachable from the deployment network and rendered the terrain
        /// black); "tianditu" selects Tianditu img_w only when
        /// TWIN_QINGDAO_TIANDITU_TOKEN is non-empty; "ion" restores asset 2.</summary>
        public static ImagerySource ResolveImagerySource(string imageryEnv,string tokenEnv)
        {
            if(string.Equals(imageryEnv,"ion",StringComparison.OrdinalIgnoreCase)) return ImagerySource.Ion;
            if(string.Equals(imageryEnv,"tianditu",StringComparison.OrdinalIgnoreCase)
               && !string.IsNullOrWhiteSpace(tokenEnv)) return ImagerySource.Tianditu;
            return ImagerySource.Arcgis;
        }

        /// <summary>The overlay's key channel: the Unity WMTS component exposes no
        /// headers/query fields, so the token rides the baseUrl query. cesium-native
        /// (pin 1bca8021) keeps existing query params and switches '?'→'&' when
        /// building KVP GetTile requests (WebMapTileServiceRasterOverlay.cpp:111-160).</summary>
        public static string TiandituBaseUrl(string token)
            => k_TiandituWmts+"?tk="+Uri.EscapeDataString(token);

        /// <summary>Health-probe URL mirroring the KVP GetTile request the overlay
        /// itself issues (same lowercase parameters, pinned cesium-native), for a
        /// Web Mercator tile containing the given position.</summary>
        public static string TiandituTileUrl(string token,double longitude,double latitude,int level)
        {
            WebMercatorTile(longitude,latitude,level,out int row,out int col);
            return TiandituBaseUrl(token)+"&request=GetTile&version=1.0.0&service=WMTS"
                +"&format=tiles&layer=img&style=default&tilematrixset=w"
                +"&tilematrix="+level+"&tilerow="+row+"&tilecol="+col;
        }

        /// <summary>ArcGIS probe URL: the same WMTS KVP GetTile the overlay issues
        /// (GoogleMapsCompatible matrix set = Web Mercator, north-origin rows,
        /// same tile math as the Tianditu probe).</summary>
        public static string ArcgisTileUrl(double longitude,double latitude,int level)
        {
            WebMercatorTile(longitude,latitude,level,out int row,out int col);
            return k_ArcgisWmts+"?service=WMTS&request=GetTile&version=1.0.0"
                +"&layer=World_Imagery&style=default&tilematrixset=GoogleMapsCompatible&format=image/jpeg"
                +"&tilematrix="+level+"&tilerow="+row+"&tilecol="+col;
        }

        static void WebMercatorTile(double longitude,double latitude,int level,out int row,out int col)
        {
            int n=1<<level;
            col=Math.Clamp((int)Math.Floor((longitude+180.0)/360.0*n),0,n-1);
            double rad=Math.Clamp(latitude,-85.05112878,85.05112878)*Math.PI/180.0;
            row=Math.Clamp((int)Math.Floor((1.0-Math.Log(Math.Tan(rad)+1.0/Math.Cos(rad))/Math.PI)/2.0*n),0,n-1);
        }

        void ApplyImagerySource()
        {
            string imagery=Environment.GetEnvironmentVariable("TWIN_QINGDAO_IMAGERY");
            string token=Environment.GetEnvironmentVariable("TWIN_QINGDAO_TIANDITU_TOKEN");
            var source=ResolveImagerySource(imagery,token);
            if(source!=ImagerySource.Tianditu)
            {
                if(string.Equals(imagery,"tianditu",StringComparison.OrdinalIgnoreCase))
                    Debug.LogWarning("[Sango.Qingdao] TWIN_QINGDAO_IMAGERY=tianditu but TWIN_QINGDAO_TIANDITU_TOKEN is empty; staying on ArcGIS World_Imagery");
                else if(!string.IsNullOrWhiteSpace(imagery) && source==ImagerySource.Arcgis
                        && !string.Equals(imagery,"arcgis",StringComparison.OrdinalIgnoreCase))
                    Debug.LogWarning($"[Sango.Qingdao] unrecognized TWIN_QINGDAO_IMAGERY='{imagery}' (expected arcgis|tianditu|ion); staying on ArcGIS World_Imagery");
            }
            SwitchImagery(source,token);
        }

        void SwitchImagery(ImagerySource source,string tiandituToken,string reason=null)
        {
            if(m_ImagerySource==source && m_Imagery!=null) return;
            if(source==ImagerySource.Ion && m_ImagerySource!=ImagerySource.Ion && reason!=null)
                Debug.LogWarning($"[Sango.Qingdao] {m_ImagerySource} imagery {reason}; falling back to ion asset 2");
            if(m_Imagery!=null) { m_Imagery.RemoveFromTileset(); Destroy(m_Imagery); m_Imagery=null; }
            m_ImagerySource=source;
            if(source!=ImagerySource.Ion)
            {
                m_ImageryProbeFailures=0; m_NextImageryProbe=Time.unscaledTime+5f;
                var wmts=m_Tiles.gameObject.AddComponent<CesiumWebMapTileServiceRasterOverlay>();
                wmts.specifyZoomLevels=true; wmts.minimumLevel=0;
                wmts.maximumScreenSpaceError=1;
                if(source==ImagerySource.Tianditu)
                {
                    m_TiandituToken=tiandituToken;
                    wmts.baseUrl=TiandituBaseUrl(tiandituToken);
                    wmts.layer="img"; wmts.style="default"; wmts.tileMatrixSetID="w"; wmts.format="tiles";
                    // Community-documented img_w range is z0–18; the cap avoids futile
                    // z19+ requests. Re-check against the console once the key is injected.
                    wmts.maximumLevel=18;
                }
                else
                {
                    wmts.baseUrl=k_ArcgisWmts;
                    wmts.layer="World_Imagery"; wmts.style="default";
                    wmts.tileMatrixSetID="GoogleMapsCompatible"; wmts.format="image/jpeg";
                    // World_Imagery carries Qingdao coastal imagery through z19
                    // (~0.3 m/px); deeper levels are sparse inland and skipped.
                    wmts.maximumLevel=19;
                }
                m_Imagery=wmts;
                CesiumRasterOverlay.OnCesiumRasterOverlayLoadFailure+=ImageryLoadFailed;
                Debug.Log($"[Sango.Qingdao] imagery source: {source} WMTS (either/or switch, fallback=ion asset 2)");
                return;
            }
            CesiumRasterOverlay.OnCesiumRasterOverlayLoadFailure-=ImageryLoadFailed;
            m_Imagery=BuildIonImagery();
        }

        CesiumIonRasterOverlay BuildIonImagery()
        {
            var imagery=m_Tiles.gameObject.AddComponent<CesiumIonRasterOverlay>();
            imagery.ionAssetID=2; imagery.ionAccessToken=m_IonToken;
            imagery.maximumScreenSpaceError=1;
            return imagery;
        }

        void ImageryLoadFailed(CesiumRasterOverlayLoadFailureDetails failure)
        {
            if(failure.overlay!=m_Imagery || m_ImagerySource==ImagerySource.Ion) return;
            SwitchImagery(ImagerySource.Ion,null,$"overlay load failed (HTTP {failure.httpStatusCode}: {failure.message})");
        }

        System.Collections.IEnumerator ProbeImagery()
        {
            m_ImageryProbeInFlight=true;
            string url=m_ImagerySource==ImagerySource.Tianditu
                ? TiandituTileUrl(m_TiandituToken,Geography.longitude,Geography.latitude,k_ImageryProbeLevel)
                : ArcgisTileUrl(Geography.longitude,Geography.latitude,k_ImageryProbeLevel);
            var request=UnityWebRequest.Get(url);
            yield return request.SendWebRequest();
            long code=request.responseCode;
            bool healthy=code==200 && request.downloadHandler!=null && request.downloadHandler.data.Length>0;
            request.Dispose();
            m_ImageryProbeInFlight=false;
            if(m_Opened && m_ImagerySource!=ImagerySource.Ion)
            {
                if(healthy) m_ImageryProbeFailures=0;
                else if(++m_ImageryProbeFailures>=2)
                {
                    SwitchImagery(ImagerySource.Ion,null,$"health probe failed twice (last HTTP {code})");
                    yield break;
                }
                m_NextImageryProbe=Time.unscaledTime+k_ImageryProbeInterval;
            }
        }

        List<CesiumCartographicPolygon> BuildPolygons(Ring[] rings,string name)
        {
            var polygons=new List<CesiumCartographicPolygon>();
            foreach(var ring in rings)
            {
                var go=new GameObject(name); go.transform.SetParent(m_Online.transform,false);
                var polygon=go.AddComponent<CesiumCartographicPolygon>(); var spline=new Spline();
                foreach(var point in ring.points)
                {
                    var local=go.transform.InverseTransformPoint(new Vector3(point.x,0,point.y));
                    spline.Add(new BezierKnot(new float3(local.x,local.y,local.z)),TangentMode.Linear);
                }
                spline.Closed=true; go.GetComponent<SplineContainer>().Spline=spline;
                go.GetComponent<CesiumGlobeAnchor>().detectTransformChanges=false; polygons.Add(polygon);
            }
            return polygons;
        }

        Cesium3DTileset Tiles(string name,long asset,string token,long cache)
        {
            var go=new GameObject(name); go.transform.SetParent(m_Online.transform,false);
            var tiles=go.AddComponent<Cesium3DTileset>();
            // Qingdao-specific clone (plan P0-B): WaterMask channel, wet-band smoothness
            // and a metric detail normal on top of the shared Cesium tileset graph; the
            // Norwegian link keeps TwinCesiumLandscapeMaterial untouched.
            // 2026-10-21: the Qingdao clone (QingdaoTilesetShader) compiles but never
            // paints the imagery overlay on the Linux Vulkan player — A/B on the
            // deployed player: clone land luminance 25 (mask on) / 39 (mask off)
            // vs standard material 142 with the same ArcGIS tiles. The standard
            // Cesium material is therefore the default; TWIN_QINGDAO_MATERIAL=clone
            // opts back in for the graph-fix iteration (follow-up: overlay/baseColor
            // protocol broken under Vulkan in the clone graph).
            if(Environment.GetEnvironmentVariable("TWIN_QINGDAO_MATERIAL")=="clone")
                tiles.opaqueMaterial=Resources.Load<Material>("Qingdao/QingdaoCesiumLandscapeMaterial");
            tiles.ionAssetID=asset;tiles.ionAccessToken=token;tiles.maximumCachedBytes=cache;
            // SSE 3 unchanged (P0-A). 16 concurrent loads, Norwegian precedent:
            // more in-flight requests bring detail tiles in earlier during
            // camera swings, and the arrival bursts are bounded by the
            // projection time budget in Update() instead of a tile count.
            tiles.maximumScreenSpaceError=3;tiles.maximumSimultaneousTileLoads=16;
            tiles.createPhysicsMeshes=false;tiles.forbidHoles=true;tiles.showCreditsOnScreen=true;
            return tiles;
        }

        void LoadFailed(Cesium3DTilesetLoadFailureDetails failure)
        {
            if(failure.tileset!=m_Tiles) return;
            m_Failed=true; Debug.LogWarning("[Sango.Qingdao] online landscape HTTP "+failure.httpStatusCode);
        }

        void Update()
        {
            if(!m_Opened) return;
            // Budgeted reprojection by time rather than count, copied from the
            // Norwegian TwinCesiumLandscape Update(): one large tile can cost
            // several small ones, and a fixed two-per-frame budget still ate
            // the frame during load bursts. ~1.5 ms keeps the queue draining
            // while bounding the worst-case main-thread hit.
            long budget=(long)(k_ProjectionBudgetMs*System.Diagnostics.Stopwatch.Frequency/1000.0);
            long started=System.Diagnostics.Stopwatch.GetTimestamp();
            for(int count=0;count<8 && m_Project.Count>0;count++)
            {
                var tile=m_Project.Dequeue();if(tile==null) continue;
                foreach(var filter in tile.GetComponentsInChildren<MeshFilter>(true))
                {
                    var mesh=filter.sharedMesh;if(mesh==null || !mesh.isReadable) continue;
                    var vertices=mesh.vertices;var c=Geography.sea_correction;
                    for(int i=0;i<vertices.Length;i++)
                    {
                        var world=filter.transform.TransformPoint(vertices[i]);
                        double x=world.x,z=world.z;
                        world.y+=(float)(c[0]*x+c[1]*z+c[2]*x*x+c[3]*x*z+c[4]*z*z);
                        vertices[i]=filter.transform.InverseTransformPoint(world);
                    }
                    mesh.vertices=vertices;mesh.RecalculateBounds();m_Meshes++;
                }
                if(System.Diagnostics.Stopwatch.GetTimestamp()-started>=budget) break;
            }
            float progress=m_Tiles!=null ? m_Tiles.ComputeLoadProgress() : 100;
            m_Warmup.Observe(Time.unscaledTime,m_Tiles!=null && m_Meshes==0 ? Mathf.Min(progress,98) : progress,
                m_Tiles!=null,m_Failed);
            if(m_Warmup.Ready && m_Overview!=null && m_Cameras!=null) m_Cameras.additionalCameras.Remove(m_Overview);
            if(Time.unscaledTime>=m_NextMemorySample)
            { SampleResourceMemory();m_NextMemorySample=Time.unscaledTime+5; }
            if(m_ImagerySource!=ImagerySource.Ion && !m_ImageryProbeInFlight && Time.unscaledTime>=m_NextImageryProbe)
                StartCoroutine(ProbeImagery());
            if(m_Terrain!=null) m_Terrain.drawHeightmap=m_Tiles==null || m_Failed || m_Meshes==0;
        }

        void SampleResourceMemory()
        {
            if(m_Root==null) return;
            var meshes=new HashSet<Mesh>();var textures=new HashSet<Texture>();
            foreach(var filter in m_Root.GetComponentsInChildren<MeshFilter>(true))
                if(filter.sharedMesh!=null) meshes.Add(filter.sharedMesh);
            foreach(var renderer in m_Root.GetComponentsInChildren<Renderer>(true))
                foreach(var material in renderer.sharedMaterials)
                    if(material!=null) foreach(var property in material.GetTexturePropertyNames())
                    { var texture=material.GetTexture(property);if(texture!=null) textures.Add(texture); }
            m_MeshBytes=m_TextureBytes=0;m_ResidentMeshes=meshes.Count;
            foreach(var mesh in meshes) m_MeshBytes+=Profiler.GetRuntimeMemorySizeLong(mesh);
            foreach(var texture in textures) m_TextureBytes+=Profiler.GetRuntimeMemorySizeLong(texture);
        }

        public void Camera(string preset)
        {
            if(m_Camera==null) return;
            if(preset=="top") m_Camera.SetFreePose(new Vector3(0,9000,0),0,-90,65);
            else if(preset=="bridge") m_Camera.SetFreePose(new Vector3(-2000,15,-1800),55,-2,65);
            else m_Camera.SetFreePose(new Vector3(-2300,900,-4100),55,-45,65);
        }

        public void FreePose(TwinBridgeFreePose pos,double yaw,double pitch,double fov)
        { m_Camera.SetFreePose(LocalPosition(pos.east,pos.north,Geography)+Vector3.up*(float)pos.height_m,(float)yaw,(float)pitch,(float)fov); }

        public void Clear()
        {
            if(!m_Opened) return;
            // Attachment release retains geographic resources; the next Qingdao entry reuses them.
            m_Opened=false;m_Camera?.ClearFreePose();
            if(m_Tiles!=null) m_Tiles.suspendUpdate=true;
            if(m_Root!=null) foreach(var renderer in m_Root.GetComponentsInChildren<Renderer>()) renderer.enabled=false;
            if(m_Terrain!=null) m_Terrain.drawHeightmap=false;
            // P0-C: release the water decal region back to the pre-attach state and
            // hide the rig; the retained objects are reused by the next entry.
            ReleaseShoreFoamRegion();
            if(m_ShoreFoamRoot!=null) m_ShoreFoamRoot.SetActive(false);
            // P1-A: shore volumes hide with the rest of the retained rig.
            if(m_ShoreworkRoot!=null) m_ShoreworkRoot.SetActive(false);
            if(m_Driver?.geography!=null) m_Driver.geography.gameObject.SetActive(m_NorwayWasActive);
        }
        void OnDestroy()
        {
            Cesium3DTileset.OnCesium3DTilesetLoadFailure-=LoadFailed;
            CesiumRasterOverlay.OnCesiumRasterOverlayLoadFailure-=ImageryLoadFailed;
            ReleaseShoreFoamRegion();
            // P1-A: runtime-built shorework meshes outlive their GameObjects
            // unless destroyed explicitly.
            if(m_ShoreworkRoot!=null)
                foreach(var filter in m_ShoreworkRoot.GetComponentsInChildren<MeshFilter>())
                    if(filter.sharedMesh!=null) Destroy(filter.sharedMesh);
            if(m_Root!=null) Destroy(m_Root);
            if(m_Data!=null) Destroy(m_Data);
            if(m_OverviewViewport!=null) Destroy(m_OverviewViewport);
        }
    }
}
