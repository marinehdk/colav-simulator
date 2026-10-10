using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;
using UnityEngine.UI;

namespace Sango
{
    // Run after ship interpolation and CameraRig. The marker is captured by the same camera
    // as the world geometry; the browser matches decoded marker pixels to these projections.
    [DefaultExecutionOrder(10000)]
    public sealed class TwinSituationDisplay : MonoBehaviour
    {
        public TwinBridgeService bridge;
        readonly List<TwinSituationMessage> m_Pending = new List<TwinSituationMessage>();
        readonly Dictionary<int, TwinSituationFrame> m_Frames = new Dictionary<int, TwinSituationFrame>();
        readonly Queue<int> m_FrameOrder = new Queue<int>();
        readonly Dictionary<string, Renderer[]> m_Renderers = new Dictionary<string, Renderer[]>();
        GameObject m_Geometry, m_MarkerRoot;
        Texture2D m_Marker, m_DiscTexture;
        readonly List<Material> m_Materials = new List<Material>();
        readonly List<Mesh> m_Meshes = new List<Mesh>();
        sealed class ScreenLine { public Mesh mesh; public TwinDisplayLine line; public TwinAnchor anchor; }
        readonly List<ScreenLine> m_ScreenLines = new List<ScreenLine>();
        readonly List<Vector3> m_LineVertices = new List<Vector3>();
        readonly List<int> m_LineTriangles = new List<int>();
        Vector3 m_LineEye;
        Quaternion m_LineRotation;
        TwinSituationMessage m_Shown;
        public TwinSituationMessage CurrentPresentation => m_Shown;
        string m_GeometrySignature;
        int m_FrameId;

        public void Offer(TwinSituationMessage value)
        {
            if (value == null || !TwinSituationMath.Finite(value.sim_time) || value.seq < 0) return;
            if (m_Pending.Count > 0 && value.seq < m_Pending[m_Pending.Count - 1].seq) Clear();
            if (m_Pending.Count > 0 && value.seq == m_Pending[m_Pending.Count - 1].seq)
                m_Pending[m_Pending.Count - 1] = value;
            else m_Pending.Add(value);
            if (m_Pending.Count > 120) m_Pending.RemoveAt(0);
        }

        public TwinDisplayTarget ResolveTarget(string key) =>
            Array.Find(m_Shown?.targets ?? Array.Empty<TwinDisplayTarget>(), target => target.key == key);

        void LateUpdate()
        {
            var driver = bridge?.driver;
            var camera = bridge?.cameraRig?.controlledCamera;
            if (bridge == null || !bridge.runtimeEnabled || driver?.Anchor == null ||
                camera == null || bridge.channel == null || !bridge.channel.IsConnected)
            { if (m_MarkerRoot != null) m_MarkerRoot.SetActive(false); return; }
            double sim = driver.RenderSimTime;
            if (!TwinSituationMath.Finite(sim)) return;
            TwinSituationMessage data = null;
            foreach (var item in m_Pending)
                if (item.run_id == bridge.AttachedRunId && item.sim_time <= sim + 0.02) data = item;
            if (data == null) return;
            m_Shown = data;
            // Geometry is rebuilt only when its actual shape/appearance changes.
            string signature = JsonUtility.ToJson(new GeometryKey(data));
            if (m_GeometrySignature != signature)
            { RebuildGeometry(data, driver.Anchor.Value); m_GeometrySignature = signature; }
            UpdateScreenLines(camera);
            EnsureMarker(camera);
            m_MarkerRoot.SetActive(true);
            m_FrameId = (m_FrameId + 1) & 65535;
            uint bits = TwinSituationMath.MarkerBits(m_FrameId);
            var pixels = new Color32[32];
            for (int i = 0; i < 32; i++) pixels[i] = (bits & (1u << (31 - i))) != 0 ? new Color32(255,255,255,255) : new Color32(0,0,0,255);
            m_Marker.SetPixels32(pixels); m_Marker.Apply(false);
            var targets = new List<TwinScreenPoint>();
            foreach (var target in data.targets ?? Array.Empty<TwinDisplayTarget>())
            {
                Vector3 world = Local(target, driver.Anchor.Value, 3);
                GameObject ship = int.TryParse(target.id, out int id) ? driver.ShipObject(id) : null;
                if (target.truth && ship != null) world = ship.transform.position + Vector3.up * 3;
                var screen = Project(camera, world);
                screen.id = target.id; screen.key = target.key;
                screen.visible &= data.ships_visible && (ship == null || ship.activeInHierarchy);
                if (ship != null && target.truth)
                {
                    if (!m_Renderers.TryGetValue(target.key, out var renderers) || renderers.Length == 0 || renderers[0] == null)
                    { renderers = Array.FindAll(ship.GetComponentsInChildren<Renderer>(),
                        renderer => renderer is MeshRenderer || renderer is SkinnedMeshRenderer); m_Renderers[target.key] = renderers; }
                    var bounds = new Bounds(ship.transform.position, Vector3.one);
                    foreach (var renderer in renderers) if (renderer != null) bounds.Encapsulate(renderer.bounds);
                    ProjectBounds(camera, bounds, screen);
                }
                else
                {
                    var bounds = new Bounds(world, new Vector3(Mathf.Max(8,target.width), 5, Mathf.Max(12,target.length)));
                    ProjectBounds(camera, bounds, screen);
                }
                targets.Add(screen);
            }
            var frame = new TwinSituationFrame {
                run_id = data.run_id, frame_id = m_FrameId, source_seq = data.seq, telemetry_seq = driver.LastSeq,
                sim_time = sim, width = camera.pixelWidth, height = camera.pixelHeight,
                landscape = bridge.Landscape,
                camera = bridge.CurrentPreset, camera_yaw = camera.transform.eulerAngles.y,
                camera_pose = new TwinBridgeCameraPose {
                    east = driver.Anchor.Value.EastM + camera.transform.position.x - driver.Anchor.Value.LandingM.x,
                    north = driver.Anchor.Value.NorthM + camera.transform.position.z - driver.Anchor.Value.LandingM.y,
                    height_m = camera.transform.position.y, yaw_deg = camera.transform.eulerAngles.y,
                    pitch_deg = -Mathf.DeltaAngle(0, camera.transform.eulerAngles.x), fov_deg = camera.fieldOfView,
                },
                targets = targets.ToArray(), waypoints = ProjectPoints(camera, data.waypoints, driver.Anchor.Value, data.waypoints_visible),
                time_markers = ProjectPoints(camera, data.time_markers, driver.Anchor.Value, true),
            };
            m_Frames[m_FrameId] = frame; m_FrameOrder.Enqueue(m_FrameId);
            while (m_FrameOrder.Count > 120) m_Frames.Remove(m_FrameOrder.Dequeue());
            bridge.channel.SendJson(frame.ToJson());
        }

        public void Pick(int frameId, float x, float y)
        {
            if (!m_Frames.TryGetValue(frameId, out var frame) || frame.run_id != bridge?.AttachedRunId) return;
            var point = TwinSituationMath.Pick(frame, x, y);
            // Reject a retired target generation even when its old video frame is still buffered.
            if (point != null && !Array.Exists(m_Shown?.targets ?? Array.Empty<TwinDisplayTarget>(), target => target.key == point.key)) return;
            bridge.channel.SendJson(new TwinSituationPick { run_id = frame.run_id, frame_id = frameId,
                id = point?.id, key = point?.key }.ToJson());
        }

        static TwinScreenPoint Project(Camera camera, Vector3 world)
        {
            var p = camera.WorldToViewportPoint(world);
            return new TwinScreenPoint { x=p.x, y=1-p.y, depth=p.z,
                visible=p.z>camera.nearClipPlane && p.z<camera.farClipPlane && p.x>=0 && p.x<=1 && p.y>=0 && p.y<=1 };
        }
        static void ProjectBounds(Camera camera, Bounds bounds, TwinScreenPoint point)
        {
            float left=1, right=0, top=1, bottom=0;
            for (int i=0;i<8;i++)
            {
                var corner=bounds.center + Vector3.Scale(bounds.extents, new Vector3((i&1)==0?-1:1,(i&2)==0?-1:1,(i&4)==0?-1:1));
                var p=camera.WorldToViewportPoint(corner);
                if (p.z <= camera.nearClipPlane) continue;
                left=Mathf.Min(left,p.x); right=Mathf.Max(right,p.x); top=Mathf.Min(top,1-p.y); bottom=Mathf.Max(bottom,1-p.y);
            }
            point.left=left; point.top=top; point.width=Mathf.Max(0,right-left); point.height=Mathf.Max(0,bottom-top);
        }
        static TwinScreenPoint[] ProjectPoints(Camera camera, TwinDisplayPoint[] points, TwinAnchor anchor, bool visible)
        {
            return Array.ConvertAll(points ?? Array.Empty<TwinDisplayPoint>(), p => {
                var result=Project(camera,Local(p,anchor,1.4f)); result.label=p.label; result.visible &= visible; return result;
            });
        }
        static Vector3 Local(TwinDisplayPoint p, TwinAnchor anchor, float height)
        { var local=anchor.ToLocal(p.east,p.north); return new Vector3(local.x,height,local.y); }

        void EnsureMarker(Camera camera)
        {
            if (m_MarkerRoot != null) { m_MarkerRoot.GetComponent<Canvas>().worldCamera=camera; return; }
            m_MarkerRoot = new GameObject("DT frame identity",typeof(Canvas));
            m_MarkerRoot.transform.SetParent(transform,false);
            var canvas=m_MarkerRoot.GetComponent<Canvas>(); canvas.renderMode=RenderMode.ScreenSpaceCamera;
            canvas.worldCamera=camera; canvas.planeDistance=camera.nearClipPlane+0.02f; canvas.sortingOrder=32000;
            var image=new GameObject("frame-marker@1",typeof(RectTransform),typeof(RawImage));
            image.transform.SetParent(m_MarkerRoot.transform,false);
            var rect=image.GetComponent<RectTransform>(); rect.anchorMin=rect.anchorMax=rect.pivot=new Vector2(0,1);
            rect.anchoredPosition=Vector2.zero; rect.sizeDelta=new Vector2(TwinSituationMath.MarkerWidth,TwinSituationMath.MarkerHeight);
            m_Marker=new Texture2D(32,1,TextureFormat.RGBA32,false) { filterMode=FilterMode.Point, wrapMode=TextureWrapMode.Clamp };
            image.GetComponent<RawImage>().texture=m_Marker; image.GetComponent<RawImage>().raycastTarget=false;
        }

        [Serializable] sealed class GeometryKey
        {
            public TwinDisplayPoint[] ribbon,waypoints;
            public TwinDisplayLine[] lines;
            public TwinDisplayDisc vo;
            public bool waypoints_visible;
            public GeometryKey(TwinSituationMessage data) { ribbon=data.ribbon; waypoints=data.waypoints; lines=data.lines; vo=data.vo; waypoints_visible=data.waypoints_visible; }
        }
        void RebuildGeometry(TwinSituationMessage data, TwinAnchor anchor)
        {
            ReleaseGeometry();
            m_Geometry=new GameObject("DT situation geometry"); m_Geometry.transform.SetParent(transform,false);
            var vertices=new List<Vector3>(); var triangles=new List<int>();
            var ribbon=data.ribbon ?? Array.Empty<TwinDisplayPoint>();
            Debug.Log($"[Sango.DT] geometry seq={data.seq} ribbon_quads={ribbon.Length/4} lines={data.lines?.Length ?? 0} waypoints={data.waypoints?.Length ?? 0}");
            for (int i=0;i+3<ribbon.Length;i+=4)
                Quad(vertices,triangles,Local(ribbon[i],anchor,1.2f),Local(ribbon[i+1],anchor,1.2f),Local(ribbon[i+2],anchor,1.2f),Local(ribbon[i+3],anchor,1.2f));
            MeshObject("Mission route ribbon",vertices,triangles,new Color(0.467f,0.741f,1,0.3f));
            foreach(var line in data.lines ?? Array.Empty<TwinDisplayLine>())
            {
                vertices.Clear(); triangles.Clear();
                var points=line.points ?? Array.Empty<TwinDisplayPoint>();
                for(int i=1;i<points.Length;i++) Segment(vertices,triangles,Local(points[i-1],anchor,1.4f),Local(points[i],anchor,1.4f),line.width,line.dashed);
                ColorUtility.TryParseHtmlString(line.color,out var color);
                var mesh=MeshObject(line.id,vertices,triangles,color);
                if(mesh!=null) m_ScreenLines.Add(new ScreenLine { mesh=mesh,line=line,anchor=anchor });
            }
            if(data.waypoints_visible) foreach(var waypoint in data.waypoints ?? Array.Empty<TwinDisplayPoint>())
            {
                vertices.Clear(); triangles.Clear();
                var center=Local(waypoint,anchor,1.4f);
                for(int i=0;i<48;i++) Segment(vertices,triangles,center+Circle(i,48,12),center+Circle(i+1,48,12),1.2f,false);
                MeshObject(waypoint.label,vertices,triangles,new Color(0,0.42f,0.84f,0.65f));
            }
            if(data.vo != null && data.vo.radius>0 && !string.IsNullOrEmpty(data.vo.png))
            {
                m_DiscTexture=new Texture2D(2,2);
                if(ImageConversion.LoadImage(m_DiscTexture,Convert.FromBase64String(data.vo.png)))
                {
                    vertices.Clear(); triangles.Clear();
                    var c=Local(data.vo,anchor,1.6f); float r=data.vo.radius;
                    Quad(vertices,triangles,c+new Vector3(-r,0,-r),c+new Vector3(r,0,-r),c+new Vector3(r,0,r),c+new Vector3(-r,0,r));
                    var mesh=MeshObject("VO decision disc",vertices,triangles,new Color(1,1,1,0.42f));
                    mesh.uv=new[]{new Vector2(0,0),new Vector2(1,0),new Vector2(1,1),new Vector2(0,1)};
                    m_Materials[m_Materials.Count-1].SetTexture("_UnlitColorMap",m_DiscTexture);
                    m_Materials[m_Materials.Count-1].EnableKeyword("_UNLIT_COLOR_MAP");
                }
            }
        }
        static Vector3 Local(TwinDisplayDisc p,TwinAnchor anchor,float height)
        { var q=anchor.ToLocal(p.east,p.north); return new Vector3(q.x,height,q.y); }
        static Vector3 Circle(int i,int count,float radius)
        { float angle=i*2*Mathf.PI/count; return new Vector3(Mathf.Cos(angle)*radius,0,Mathf.Sin(angle)*radius); }
        static void Quad(List<Vector3> v,List<int> t,Vector3 a,Vector3 b,Vector3 c,Vector3 d)
        { int i=v.Count; v.AddRange(new[]{a,b,c,d}); t.AddRange(new[]{i,i+2,i+1,i,i+3,i+2}); }
        static void Segment(List<Vector3> v,List<int> t,Vector3 a,Vector3 b,float width,bool dashed,Camera camera=null)
        {
            var delta=b-a; float length=delta.magnitude;
            if(length<0.001f)return;
            var normal=new Vector3(-delta.z,0,delta.x).normalized;
            float step=dashed?40:length;
            for(float d=0;d<length;d+=step)
            {
                var start=a+delta*(d/length); var end=a+delta*(Mathf.Min(length,d+(dashed?20:length))/length);
                float meters=width;
                if(camera!=null)
                {
                    float depth=Mathf.Max(camera.nearClipPlane,camera.WorldToViewportPoint((start+end)*0.5f).z);
                    float span=camera.orthographic?2*camera.orthographicSize:2*depth*Mathf.Tan(camera.fieldOfView*Mathf.Deg2Rad*0.5f);
                    meters=Mathf.Clamp(span*width/Mathf.Max(1,camera.pixelHeight),0.05f,50);
                }
                var side=normal*meters*0.5f; Quad(v,t,start-side,end-side,end+side,start+side);
            }
        }
        void UpdateScreenLines(Camera camera)
        {
            if(Vector3.Distance(m_LineEye,camera.transform.position)<0.5f &&
                Quaternion.Angle(m_LineRotation,camera.transform.rotation)<0.25f) return;
            m_LineEye=camera.transform.position; m_LineRotation=camera.transform.rotation;
            foreach(var record in m_ScreenLines)
            {
                m_LineVertices.Clear(); m_LineTriangles.Clear();
                var points=record.line.points ?? Array.Empty<TwinDisplayPoint>();
                for(int i=1;i<points.Length;i++) Segment(m_LineVertices,m_LineTriangles,
                    Local(points[i-1],record.anchor,1.4f),Local(points[i],record.anchor,1.4f),
                    record.line.width,record.line.dashed,camera);
                record.mesh.Clear(); record.mesh.SetVertices(m_LineVertices);
                record.mesh.SetTriangles(m_LineTriangles,0); record.mesh.RecalculateBounds();
            }
        }
        Mesh MeshObject(string name,List<Vector3> vertices,List<int> triangles,Color color)
        {
            if(vertices.Count==0)return null;
            var mesh=new Mesh { name=name,indexFormat=IndexFormat.UInt32 };
            mesh.SetVertices(vertices); mesh.SetTriangles(triangles,0); mesh.RecalculateBounds(); m_Meshes.Add(mesh);
            var material=new Material(Shader.Find("HDRP/Unlit")); material.SetColor("_UnlitColor",color);
            material.SetFloat("_BlendMode",0); material.SetFloat("_TransparentZWrite",0);
            material.SetFloat("_DoubleSidedEnable",1); material.SetFloat("_EnableFogOnTransparent",0);
            HDMaterial.SetSurfaceType(material,true);
            material.renderQueue=3000; HDMaterial.ValidateMaterial(material); m_Materials.Add(material);
            var go=new GameObject(name,typeof(MeshFilter),typeof(MeshRenderer)); go.transform.SetParent(m_Geometry.transform,false);
            go.GetComponent<MeshFilter>().sharedMesh=mesh; var renderer=go.GetComponent<MeshRenderer>();
            renderer.sharedMaterial=material; renderer.shadowCastingMode=ShadowCastingMode.Off; renderer.receiveShadows=false;
            return mesh;
        }
        void ReleaseGeometry()
        {
            if(m_Geometry!=null) Destroy(m_Geometry);
            foreach(var mesh in m_Meshes) Destroy(mesh); m_Meshes.Clear();
            m_ScreenLines.Clear(); m_LineEye=new Vector3(float.PositiveInfinity,0,0);
            foreach(var material in m_Materials) Destroy(material); m_Materials.Clear();
            if(m_DiscTexture!=null) Destroy(m_DiscTexture); m_DiscTexture=null;
        }
        public void Clear()
        {
            m_Pending.Clear(); m_Frames.Clear(); m_FrameOrder.Clear(); m_Renderers.Clear();
            m_Shown=null; m_GeometrySignature=null; ReleaseGeometry();
            if(m_MarkerRoot!=null) m_MarkerRoot.SetActive(false);
        }
        void OnDestroy() { Clear(); if(m_MarkerRoot!=null)Destroy(m_MarkerRoot); if(m_Marker!=null)Destroy(m_Marker); }
    }
}
