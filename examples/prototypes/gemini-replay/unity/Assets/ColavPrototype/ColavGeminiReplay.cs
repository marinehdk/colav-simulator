// PROTOTYPE: actual Gemini pose service; scene and playback controls are disposable.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using Gemini.Core;
using Gemini.Networking.Services;
using GeminiOSPInterface;
using Grpc.Core;
using UnityEngine;
using UnityEngine.Networking;

[Serializable] public class RecordedPose { public int id; public float north, east, heading, speed; }
[Serializable] public class RecordedEnvironment { public float wind_speed_mps, wind_from_deg, current_speed_mps, current_to_deg, wave_hs_m, wave_tz_s; }
[Serializable] public class RecordedFrame { public float time; public RecordedPose[] poses; public string phase, mode, rule; public float roll_deg; public RecordedEnvironment environment; }
[Serializable] public class RecordedShip { public int id; public float length_m, width_m; }
[Serializable] public class RecordedChart { public float north, east, width_m, height_m; }
[Serializable] public class RecordedPoint { public float north, east; }
[Serializable] public class RecordedChapter { public float time; public string label; }
[Serializable] public class RecordedRun { public string run_id, algorithm, tracker, limits; public float duration; public RecordedShip[] ships; public RecordedChart chart; public RecordedPoint[] route; public RecordedChapter[] chapters; public RecordedFrame[] frames; }
[Serializable] public class PlaybackStatus { public bool playing, connected; public float time, rate, ack_time; public int capture, sent; public string error; }
[Serializable] public class AppliedPose { public float north, east, heading; }
[Serializable] public class PoseReadback { public string service; public float time, max_position_error_m, max_heading_error_deg; public int count; public AppliedPose[] poses; }

public class ColavGeminiReplay : MonoBehaviour
{
    public static ColavGeminiReplay Active;
    RecordedRun run;
    GameObject[] boats;
    GameObject[] hulls;
    Server server;
    Camera view;
    Material chartMaterial;
    PlaybackStatus playback = new PlaybackStatus();
    int frameIndex, captureSeen, readbackCount;
    float appliedTime, seekTime, lastCameraTime = -1;
    bool cameraReady;
    string cameraMode = "Follow";
    float displayScale = 3f, orbit = 210f, zoom = 1f;
    string outputPath;
    GUIStyle titleStyle, labelStyle, smallStyle;
    bool stylesReady, seeking;
    readonly Color ownColor = new Color(0.1f, 0.78f, 0.75f);
    readonly Color targetColor = new Color(1f, 0.64f, 0.21f);

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Boot()
    {
        if (FindObjectOfType<ColavGeminiReplay>() != null) return;
        new GameObject("COLAV_GEMINI_REPLAY_PROTOTYPE").AddComponent<ColavGeminiReplay>();
    }

    void Start()
    {
        Active = this;
        Application.runInBackground = true;
        Application.targetFrameRate = 60;
        run = JsonUtility.FromJson<RecordedRun>(File.ReadAllText(Path.Combine(Application.streamingAssetsPath, "replay.json")));
        outputPath = Environment.GetEnvironmentVariable("COLAV_GEMINI_OUTPUT");
        if (String.IsNullOrEmpty(outputPath)) outputPath = Application.isEditor
            ? Path.GetFullPath(Path.Combine(Application.dataPath, "../../outputs"))
            : Path.GetFullPath(Path.Combine(Application.dataPath, "../.."));
        Directory.CreateDirectory(outputPath);
        gameObject.AddComponent<ThreadManager>();
        Physics.autoSimulation = false;
        RenderSettings.ambientLight = new Color(0.57f, 0.66f, 0.72f);
        RenderSettings.fog = true;
        RenderSettings.fogColor = new Color(0.57f, 0.73f, 0.82f);
        RenderSettings.fogMode = FogMode.Linear;
        RenderSettings.fogStartDistance = 5000;
        RenderSettings.fogEndDistance = 14000;
        var sun = new GameObject("Sun").AddComponent<Light>();
        sun.type = LightType.Directional; sun.intensity = 1.2f;
        sun.transform.rotation = Quaternion.Euler(42, -35, 0);
        var cameraObject = new GameObject("Replay Camera");
        view = cameraObject.AddComponent<Camera>();
        view.clearFlags = CameraClearFlags.SolidColor;
        view.backgroundColor = RenderSettings.fogColor;
        view.nearClipPlane = .2f; view.farClipPlane = 18000; view.fieldOfView = 48;
        BuildChart();
        boats = new GameObject[run.ships.Length]; hulls = new GameObject[boats.Length];
        for (int i = 0; i < boats.Length; ++i)
        {
            boats[i] = new GameObject(i == 0 ? "FCB_Pose" : "Target_Pose");
            hulls[i] = BuildVessel(run.ships[i].length_m, run.ships[i].width_m, i == 0);
            hulls[i].transform.SetParent(boats[i].transform, false);
            hulls[i].transform.localScale = Vector3.one * displayScale;
            var trace = new Vector3[run.frames.Length];
            for (int f = 0; f < trace.Length; f++) trace[f] = new Vector3(run.frames[f].poses[i].east, 1, run.frames[f].poses[i].north);
            Line("Recorded trajectory " + i, trace, i == 0 ? ownColor : targetColor, 3f);
        }
        var route = new Vector3[run.route.Length];
        for (int i = 0; i < route.Length; ++i) route[i] = new Vector3(run.route[i].east, .8f, run.route[i].north);
        Line("Nominal route", route, new Color(.82f, .9f, .96f), 1.5f);
        server = new Server {
            Services = { Simulation.BindService(new ObservedGeminiService(boats, this)) },
            Ports = { new ServerPort("127.0.0.1", 12346, ServerCredentials.Insecure) }
        };
        server.Start();
        Debug.Log("COLAV_GEMINI_READY original SimulationServiceImpl on 127.0.0.1:12346");
        StartCoroutine(PollControls());
    }

    // Calls the upstream method unchanged; readback inspects Unity transforms AFTER it completed.
    class ObservedGeminiService : SimulationServiceImpl
    {
        readonly GameObject[] targets;
        readonly ColavGeminiReplay owner;
        public ObservedGeminiService(GameObject[] targets, ColavGeminiReplay owner) : base(null, targets)
        { this.targets = targets; this.owner = owner; }
        public override async Task<StepResponse> DoStep(StepRequest request, ServerCallContext context)
        {
            if (request.VesselPoses.Count != targets.Length) throw new RpcException(new Status(StatusCode.InvalidArgument, "Vessel count mismatch"));
            StepResponse response = await base.DoStep(request, context);
            var done = new TaskCompletionSource<bool>();
            ThreadManager.ExecuteOnMainThread(() => {
                var receipt = new PoseReadback { service = "Gemini original SimulationServiceImpl", time = request.Time,
                    count = ++owner.readbackCount, poses = new AppliedPose[targets.Length] };
                for (int i = 0; i < targets.Length; ++i)
                {
                    var p = targets[i].transform.position;
                    float heading = targets[i].transform.eulerAngles.y;
                    receipt.poses[i] = new AppliedPose { north = p.z, east = p.x, heading = heading };
                    receipt.max_position_error_m = Mathf.Max(receipt.max_position_error_m,
                        Vector2.Distance(new Vector2(p.x, p.z), new Vector2(request.VesselPoses[i].East, request.VesselPoses[i].North)));
                    receipt.max_heading_error_deg = Mathf.Max(receipt.max_heading_error_deg, Mathf.Abs(Mathf.DeltaAngle(heading, request.VesselPoses[i].Heading)));
                }
                owner.appliedTime = request.Time;
                while (owner.frameIndex > 0 && owner.run.frames[owner.frameIndex].time > request.Time) owner.frameIndex--;
                while (owner.frameIndex + 1 < owner.run.frames.Length && owner.run.frames[owner.frameIndex + 1].time <= request.Time) owner.frameIndex++;
                File.WriteAllText(Path.Combine(owner.outputPath, "pose-readback.json"), JsonUtility.ToJson(receipt, true));
                done.SetResult(receipt.max_position_error_m < .01f && receipt.max_heading_error_deg < .01f);
            });
            response.Success = response.Success && await done.Task;
            return response;
        }
    }

    void BuildChart()
    {
        var texture = new Texture2D(2, 2);
        texture.LoadImage(File.ReadAllBytes(Path.Combine(Application.streamingAssetsPath, "enc.png")));
        chartMaterial = new Material(Resources.Load<Shader>("ChartWater"));
        chartMaterial.mainTexture = texture;
        var chart = new GameObject("Recorded ENC chart");
        chart.transform.position = new Vector3(run.chart.east, -.1f, run.chart.north);
        var mesh = new Mesh(); float w = run.chart.width_m, h = run.chart.height_m;
        mesh.vertices = new [] { Vector3.zero, new Vector3(w,0,0), new Vector3(w,0,h), new Vector3(0,0,h) };
        mesh.uv = new [] { new Vector2(0,0), new Vector2(1,0), new Vector2(1,1), new Vector2(0,1) };
        mesh.triangles = new [] {0,2,1,0,3,2}; mesh.RecalculateNormals();
        chart.AddComponent<MeshFilter>().mesh = mesh;
        chart.AddComponent<MeshRenderer>().material = chartMaterial;
        var sea = GameObject.CreatePrimitive(PrimitiveType.Plane);
        sea.name = "Backdrop only"; sea.transform.position = new Vector3(2500,-.3f,2500);
        sea.transform.localScale = new Vector3(4000,1,4000);
        sea.GetComponent<Renderer>().material = Mat(new Color(.09f,.28f,.39f));
        Destroy(sea.GetComponent<Collider>());
    }

    Material Mat(Color color) { var m = new Material(Shader.Find("Standard")); m.color = color; m.SetFloat("_Glossiness", .25f); m.SetColor("_EmissionColor", color*.12f); m.EnableKeyword("_EMISSION"); return m; }
    GameObject Box(Transform parent, string name, Vector3 size, Vector3 pos, Color color)
    {
        var g = GameObject.CreatePrimitive(PrimitiveType.Cube); g.name = name;
        g.transform.SetParent(parent, false); g.transform.localScale = size; g.transform.localPosition = pos;
        g.GetComponent<Renderer>().material = Mat(color); Destroy(g.GetComponent<Collider>()); return g;
    }

    GameObject BuildVessel(float length, float width, bool own)
    {
        var g = new GameObject(own ? "Procedural FCB display hull" : "Procedural target display hull");
        float l = length, w = width, h = Mathf.Max(1, length*.045f);
        Vector2[] outline = { new Vector2(-w*.4f,-l*.5f), new Vector2(w*.4f,-l*.5f), new Vector2(w*.5f,l*.2f),
            new Vector2(w*.35f,l*.38f), new Vector2(0,l*.5f), new Vector2(-w*.35f,l*.38f), new Vector2(-w*.5f,l*.2f) };
        var v = new List<Vector3>(); var triangles = new List<int>();
        foreach(var p in outline) v.Add(new Vector3(p.x,-h*.3f,p.y));
        foreach(var p in outline) v.Add(new Vector3(p.x,h,p.y));
        int n=outline.Length;
        for(int i=0;i<n;i++) { int j=(i+1)%n; triangles.AddRange(new[]{i,n+j,j,i,n+i,n+j}); }
        for(int i=1;i<n-1;i++) { triangles.AddRange(new[]{n,n+i+1,n+i}); triangles.AddRange(new[]{0,i,i+1}); }
        var mesh=new Mesh(); mesh.vertices=v.ToArray(); mesh.triangles=triangles.ToArray(); mesh.RecalculateNormals();
        var hull=new GameObject("Hull"); hull.transform.SetParent(g.transform,false);
        hull.AddComponent<MeshFilter>().mesh=mesh;
        hull.AddComponent<MeshRenderer>().material=Mat(own ? new Color(.1f,.2f,.27f) : targetColor);
        Box(g.transform,"Deck",new Vector3(w*.8f,.25f,l*.65f),new Vector3(0,h,-l*.04f),new Color(.88f,.88f,.8f));
        Box(g.transform,"Cabin",new Vector3(w*.76f,h*1.6f,l*.3f),new Vector3(0,h*1.8f,l*.12f),Color.white);
        Box(g.transform,"Bridge windows",new Vector3(w*.79f,h*.55f,l*.24f),new Vector3(0,h*2.15f,l*.17f),new Color(.1f,.35f,.48f));
        Box(g.transform,"Roof",new Vector3(w*.84f,.25f,l*.32f),new Vector3(0,h*2.65f,l*.12f),Color.white);
        Box(g.transform,"Mast",new Vector3(.3f,h*1.6f,.3f),new Vector3(0,h*3.35f,l*.05f),Color.white);
        Box(g.transform,"Radar",new Vector3(w*.55f,.22f,.35f),new Vector3(0,h*4.1f,l*.05f),Color.white);
        Box(g.transform,"Port light",new Vector3(.2f,.25f,.25f),new Vector3(-w*.42f,h*2.8f,l*.15f),Color.red);
        Box(g.transform,"Starboard light",new Vector3(.2f,.25f,.25f),new Vector3(w*.42f,h*2.8f,l*.15f),Color.green);
        return g;
    }

    void Line(string name, Vector3[] points, Color color, float width)
    {
        var line = new GameObject(name).AddComponent<LineRenderer>();
        line.positionCount=points.Length; line.SetPositions(points); line.widthMultiplier=width;
        line.material=new Material(Shader.Find("Sprites/Default")); line.startColor=color; line.endColor=color;
    }

    IEnumerator PollControls()
    {
        while(true)
        {
            using(var request=UnityWebRequest.Get("http://127.0.0.1:8127/status"))
            {
                yield return request.SendWebRequest();
                if(!request.isNetworkError && !request.isHttpError)
                {
                    playback=JsonUtility.FromJson<PlaybackStatus>(request.downloadHandler.text);
                    if(playback.capture>captureSeen) { captureSeen=playback.capture; StartCoroutine(Capture()); }
                }
            }
            yield return new WaitForSecondsRealtime(.2f);
        }
    }
    IEnumerator Capture() { yield return new WaitForEndOfFrame(); ScreenCapture.CaptureScreenshot(Path.Combine(outputPath,"unity-replay.png")); }
    IEnumerator Command(string action, float value=0)
    {
        string url="http://127.0.0.1:8127/control?action="+action+"&value="+value.ToString(System.Globalization.CultureInfo.InvariantCulture);
        using(var request=UnityWebRequest.Get(url)) { yield return request.SendWebRequest(); }
    }

    void LateUpdate()
    {
        if(boats==null) return;
        if(Input.GetMouseButton(1)) orbit+=Input.GetAxis("Mouse X")*3;
        zoom=Mathf.Clamp(zoom-Input.mouseScrollDelta.y*.07f,.25f,3f);
        Vector3 own=boats[0].transform.position, other=boats[1].transform.position;
        Vector3 focus=own, desired;
        float distance=Mathf.Clamp(Vector3.Distance(own,other),350,1600)*zoom;
        if(cameraMode=="Encounter") { focus=(own+other)*.5f; desired=focus+Quaternion.Euler(0,orbit,0)*new Vector3(0,distance*.55f,-distance*1.15f); }
        else if(cameraMode=="Top") { focus=(own+other)*.5f; desired=focus+new Vector3(0,distance*1.5f,-1); }
        else { focus=own+boats[0].transform.forward*55; desired=own+Quaternion.Euler(0,boats[0].transform.eulerAngles.y+orbit-210,0)*new Vector3(120*zoom,100*zoom,-220*zoom); }
        if (!cameraReady || Mathf.Abs(appliedTime-lastCameraTime)>2) view.transform.position=desired;
        else view.transform.position=Vector3.Lerp(view.transform.position,desired,.18f);
        cameraReady=true; lastCameraTime=appliedTime;
        view.transform.LookAt(focus+Vector3.up*4);
        chartMaterial.SetFloat("_ReplayTime",appliedTime);
    }

    void OnGUI()
    {
        if(run==null) return;
        if(!stylesReady)
        {
            GUI.skin.font=Font.CreateDynamicFontFromOSFont(new[]{"PingFang SC","Heiti SC","Arial"},18);
            titleStyle=new GUIStyle(GUI.skin.label){fontSize=25,fontStyle=FontStyle.Bold}; titleStyle.normal.textColor=Color.white;
            labelStyle=new GUIStyle(GUI.skin.label){fontSize=17}; labelStyle.normal.textColor=new Color(.88f,.95f,1f);
            smallStyle=new GUIStyle(labelStyle){fontSize=13};
            GUI.skin.button.fontSize=16; stylesReady=true;
        }
        float scale=Mathf.Min(Screen.width/1360f,Screen.height/800f);
        GUI.matrix=Matrix4x4.Scale(Vector3.one*scale);
        float screenW=Screen.width/scale, screenH=Screen.height/scale;
        GUI.Box(new Rect(18,16,screenW-36,84),"");
        GUI.Label(new Rect(34,22,900,38),"Gemini / Unity × Colav-Simulator",titleStyle);
        GUI.Label(new Rect(34,62,1000,27),"PROTOTYPE  ·  VO 追越记录  ·  原版 Gemini gRPC 位姿服务  ·  L1：理想态势",labelStyle);
        GUI.Box(new Rect(18,114,322,282),"");
        var frame=run.frames[frameIndex];
        GUI.Label(new Rect(34,126,300,28),"已应用时间  "+appliedTime.ToString("F1")+" / "+run.duration.ToString("F1")+" s",labelStyle);
        GUI.Label(new Rect(34,163,300,26),"本船航速  "+(frame.poses[0].speed*1.943844f).ToString("F1")+" kn",labelStyle);
        GUI.Label(new Rect(34,197,300,26),"艏向  "+frame.poses[0].heading.ToString("F1")+"°",labelStyle);
        GUI.Label(new Rect(34,231,300,26),"追越状态  "+frame.phase,labelStyle);
        GUI.Label(new Rect(34,265,300,26),"执行模式  "+frame.mode,labelStyle);
        float separation=Vector3.Distance(boats[0].transform.position,boats[1].transform.position);
        GUI.Label(new Rect(34,299,300,26),"船位距离  "+separation.ToString("F1")+" m",labelStyle);
        GUI.Label(new Rect(34,336,300,46),"回读确认  "+readbackCount+" 帧\n"+(playback.connected?"Python ↔ Gemini 已连接":"等待 Python 回放连接"),smallStyle);
        GUI.Box(new Rect(screenW-284,114,266,210),"");
        GUI.Label(new Rect(screenW-268,126,245,26),"记录环境 / 显示边界",labelStyle);
        GUI.Label(new Rect(screenW-268,166,245,25),"风速 "+frame.environment.wind_speed_mps.ToString("F1")+" m/s",labelStyle);
        GUI.Label(new Rect(screenW-268,200,245,25),"流速 "+frame.environment.current_speed_mps.ToString("F2")+" m/s",labelStyle);
        GUI.Label(new Rect(screenW-268,234,245,25),"波高 Hs "+frame.environment.wave_hs_m.ToString("F1")+" m",labelStyle);
        GUI.Label(new Rect(screenW-268,272,245,42),"船模显示 ×"+displayScale+"；船位按记录\n波纹仅示意，不参与动力学",smallStyle);
        float y=screenH-168;
        GUI.Box(new Rect(18,y,screenW-36,150),"");
        if(GUI.Button(new Rect(32,y+12,90,34),playback.playing?"暂停":"播放")) StartCoroutine(Command(playback.playing?"pause":"play"));
        if(GUI.Button(new Rect(130,y+12,90,34),"回到起点")) StartCoroutine(Command("reset"));
        float[] rates={1,8,16,32};
        for(int i=0;i<rates.Length;i++) if(GUI.Button(new Rect(232+i*58,y+12,52,34),rates[i]+"×")) StartCoroutine(Command("rate",rates[i]));
        if(GUI.Button(new Rect(490,y+12,88,34),"会遇全景")) cameraMode="Encounter";
        if(GUI.Button(new Rect(586,y+12,88,34),"跟随本船")) cameraMode="Follow";
        if(GUI.Button(new Rect(682,y+12,88,34),"俯视")) cameraMode="Top";
        if(GUI.Button(new Rect(778,y+12,96,34),"真实尺寸")) { displayScale=displayScale==1?3:1; foreach(var h in hulls) h.transform.localScale=Vector3.one*displayScale; }
        if(GUI.Button(new Rect(884,y+12,88,34),"截图")) StartCoroutine(Capture());
        float before=seeking?seekTime:appliedTime;
        float slider=GUI.HorizontalSlider(new Rect(34,y+61,screenW-68,20),before,0,run.duration);
        if(Mathf.Abs(slider-before)>.01f) {seekTime=slider;seeking=true;}
        if(seeking && Event.current.type==EventType.MouseUp) { StartCoroutine(Command("seek",seekTime)); seeking=false; }
        float x=34;
        foreach(var c in run.chapters) { if(GUI.Button(new Rect(x,y+89,178,27),c.label+" "+c.time.ToString("F0")+"s")) StartCoroutine(Command("seek",c.time)); x+=185; }
        GUI.Label(new Rect(34,y+122,screenW-68,24),"右键拖动旋转 · 滚轮缩放 · 全程轨迹为历史参考 · 外形/波纹为示意 · 未运行新算法或实船验证",smallStyle);
        for(int i=0;i<boats.Length;i++)
        {
            Vector3 p=view.WorldToScreenPoint(boats[i].transform.position+Vector3.up*30);
            if(p.z>0) GUI.Label(new Rect(p.x/scale-65,(Screen.height-p.y)/scale,220,26),i==0?"● FCB / Ship0":"● Target / Ship1",labelStyle);
        }
    }

    void OnDestroy() { if(server!=null) server.ShutdownAsync(); }
}
