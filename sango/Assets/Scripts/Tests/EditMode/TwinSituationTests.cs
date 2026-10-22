using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    public class TwinSituationTests
    {
        [TestCase(0, 0xD300005Au)]
        [TestCase(1, 0xD300015Bu)]
        [TestCase(65536, 0xD300005Au)]
        public void MarkerUsesSharedWireBits(int frame, uint expected)
        { Assert.AreEqual(expected, TwinSituationMath.MarkerBits(frame)); }

        [Test] public void PickUsesDisplayedFrameBoundsAndNearestVisibleTarget()
        {
            var far=new TwinScreenPoint { id="1",key="run:1:2",visible=true,depth=100,left=.4f,top=.4f,width=.1f,height=.1f };
            var near=new TwinScreenPoint { id="2",key="run:2:3",visible=true,depth=50,left=.4f,top=.4f,width=.1f,height=.1f };
            var frame=new TwinSituationFrame { width=1920,height=1080,targets=new[]{far,near} };
            Assert.AreSame(near,TwinSituationMath.Pick(frame,.45f,.45f));
            near.visible=false;
            Assert.AreSame(far,TwinSituationMath.Pick(frame,.45f,.45f));
            Assert.IsNull(TwinSituationMath.Pick(frame,.9f,.9f));
        }
        [Test] public void BlackBarsAndMalformedClicksCannotPick()
        {
            var frame=new TwinSituationFrame { width=1920,height=1080,targets=new[]{new TwinScreenPoint {
                id="1",visible=true,depth=10,left=0,top=0,width=1,height=1 }} };
            Assert.IsNull(TwinSituationMath.Pick(frame,-.01f,.5f));
            Assert.IsNull(TwinSituationMath.Pick(frame,.5f,float.NaN));
            Assert.IsNull(TwinSituationMath.Pick(frame,1.01f,.5f));
        }
        [Test] public void DisplayMessageRetainsGenerationAndGlobalCoordinatePrecision()
        {
            var command=TwinBridgeCommand.FromJson("{\"type\":\"presentation\",\"presentation\":{\"run_id\":\"run\",\"seq\":7,\"sim_time\":35,\"targets\":[{\"id\":\"2\",\"key\":\"run:2:8\",\"east\":42000.125,\"north\":6959450.25,\"truth\":false}]}}");
            Assert.AreEqual("run:2:8",command.presentation.targets[0].key);
            Assert.AreEqual(6959450.25,command.presentation.targets[0].north);
            Assert.IsFalse(command.presentation.targets[0].truth);
        }
        // dt-sensor-overlay 契约：B 段键名逐字对拍（length/width 非 length_m；track_key 空串=无关联）。
        [Test] public void PresentationParsesExistenceAndDetectionsWithContractKeyNames()
        {
            var command=TwinBridgeCommand.FromJson("{\"type\":\"presentation\",\"presentation\":{\"run_id\":\"run\",\"seq\":9,\"sim_time\":40,"+
                "\"targets\":[{\"id\":\"2\",\"key\":\"run:2:8\",\"east\":42000.125,\"north\":6959450.25,\"truth\":false,\"existence\":0.875}],"+
                "\"detections\":[{\"east\":42005.5,\"north\":6959455.25,\"length\":12,\"width\":5,\"confidence\":0.91,\"class_name\":\"boat\","+
                "\"sensor_id\":2,\"key\":\"2:104:0\",\"track_key\":\"run:2:8\"},"+
                "{\"east\":42100,\"north\":6959500,\"length\":9,\"width\":4,\"confidence\":0.4,\"class_name\":\"boat\","+
                "\"sensor_id\":3,\"key\":\"3:105:1\",\"track_key\":\"\"}]}}");
            Assert.AreEqual(0.875f,command.presentation.targets[0].existence,1e-5f);
            Assert.AreEqual(2,command.presentation.detections.Length);
            var detection=command.presentation.detections[0];
            Assert.AreEqual(42005.5,detection.east);
            Assert.AreEqual(12f,detection.length,1e-5f);
            Assert.AreEqual(5f,detection.width,1e-5f);
            Assert.AreEqual(0.91f,detection.confidence,1e-5f);
            Assert.AreEqual("boat",detection.class_name);
            Assert.AreEqual(2,detection.sensor_id);
            Assert.AreEqual("2:104:0",detection.key);
            Assert.AreEqual("run:2:8",detection.track_key);
            Assert.AreEqual("",command.presentation.detections[1].track_key);
        }
        [Test] public void OldPresentationWithoutNewFieldsParsesWithDefaults()
        {
            var command=TwinBridgeCommand.FromJson("{\"type\":\"presentation\",\"presentation\":{\"run_id\":\"run\",\"seq\":7,\"sim_time\":35,"+
                "\"targets\":[{\"id\":\"2\",\"key\":\"run:2:8\",\"east\":42000.125,\"north\":6959450.25,\"truth\":false}]}}");
            Assert.AreEqual(0f,command.presentation.targets[0].existence);
            Assert.IsNull(command.presentation.detections);
        }
        // DT 不安全水域红区(20261016):presentation.hazard_xy = 平铺绝对 [east,north]
        // ×0.1m 数组(6 数/三角形)+ hazard_count(对象数组会超数据通道消息上限);
        // 旧消息无该字段 = null + hazard_visible 默认 false,不画红。
        [Test] public void PresentationParsesHazardTrianglesAndOldMessagesDefaultToHidden()
        {
            var command=TwinBridgeCommand.FromJson("{\"type\":\"presentation\",\"presentation\":{\"run_id\":\"run\",\"seq\":10,\"sim_time\":41,"+
                "\"hazard_xy\":[42010.5,6959460.2,42030.5,6959480.2,42050.5,6959440.2,"+
                "42011.5,6959461.2,42031.5,6959481.2,42051.5,6959441.2],"+
                "\"hazard_count\":2,\"hazard_visible\":true}}");
            Assert.AreEqual(12,command.presentation.hazard_xy.Length);
            Assert.AreEqual(42010.5,command.presentation.hazard_xy[0]);
            Assert.AreEqual(6959480.2,command.presentation.hazard_xy[3]);
            Assert.AreEqual(2,command.presentation.hazard_count);
            Assert.IsTrue(command.presentation.hazard_visible);
            var legacy=TwinBridgeCommand.FromJson("{\"type\":\"presentation\",\"presentation\":{\"run_id\":\"run\",\"seq\":7,\"sim_time\":35}}");
            Assert.IsNull(legacy.presentation.hazard_xy);
            Assert.AreEqual(0,legacy.presentation.hazard_count);
            Assert.IsFalse(legacy.presentation.hazard_visible);
        }
        // presentation_shard 契约(20261016):大 presentation 拆片字段逐字解析;
        // 服务侧组包 = "{\"type\":\"presentation\",\"presentation\":" + 各片顺序拼接。
        [Test] public void PresentationShardFieldsParseAndAssembleRoundTrip()
        {
            var shard=TwinBridgeCommand.FromJson("{\"type\":\"presentation_shard\",\"run_id\":\"run\",\"seq\":910,\"index\":1,\"total\":3,\"part\":\"efgh\"}");
            Assert.AreEqual("presentation_shard",shard.type);
            Assert.AreEqual("run",shard.run_id);
            Assert.AreEqual(910,shard.seq);
            Assert.AreEqual(1,shard.index);
            Assert.AreEqual(3,shard.total);
            Assert.AreEqual("efgh",shard.part);
            var assembled=TwinBridgeCommand.FromJson(
                "{\"type\":\"presentation\",\"presentation\":"+"{\"run_id\":\"run\","+"\"seq\":910,"+"\"sim_time\":41.5}"+"}");
            Assert.AreEqual("run",assembled.presentation.run_id);
            Assert.AreEqual(910,assembled.presentation.seq);
            Assert.AreEqual(41.5,assembled.presentation.sim_time,1e-5);
        }

        [Test] public void FrameJsonRoundTripsDetectionsAndTargetExistence()
        {
            var frame=new TwinSituationFrame { width=1920,height=1080,
                targets=new[]{new TwinScreenPoint { id="1",key="run:1:none",visible=true,depth=42,left=.3f,top=.3f,width=.2f,height=.2f,existence=.875f }},
                detections=new[]{new TwinScreenDetection { key="2:104:0",track_key="run:1:none",visible=true,depth=41,left=.31f,top=.31f,
                    width=.22f,height=.22f,confidence=.91f,class_name="boat",sensor_id=2 }} };
            var json=frame.ToJson();
            StringAssert.Contains("\"detections\":[{",json);
            StringAssert.Contains("\"existence\":0.875",json);
            StringAssert.Contains("\"class_name\":\"boat\"",json);
            StringAssert.Contains("\"track_key\":\"run:1:none\"",json);
            var back=JsonUtility.FromJson<TwinSituationFrame>(json);
            Assert.AreEqual(.875f,back.targets[0].existence,1e-5f);
            Assert.AreEqual(1,back.detections.Length);
            Assert.AreEqual(.91f,back.detections[0].confidence,1e-5f);
            Assert.AreEqual(back.detections[0].key,"2:104:0");
            Assert.AreEqual(41f,back.detections[0].depth,1e-4f);
        }

        // ── P1 本船水线多边形（dt-ownship-mask，20261019）─────────────────────
        // 契约：4 角点 [艏左,艏右,艉右,艉左] 归一化视口坐标（左上原点、y 向下、
        // 可越界）；相机前方角点<3 或无相机 → 空数组=无掩膜（消费端优雅跳过）。
        // 三例：无相机场景 / 追随居中（四角全入画）/ 部分出画（出画角点保留+标记）。
        [Test] public void OwnshipPolygonWithoutCameraIsEmpty()
        {
            var polygon=TwinSituationMath.OwnshipPolygon(null,Vector3.zero,Vector3.forward,Vector3.back,Vector3.left);
            Assert.IsNotNull(polygon);
            Assert.AreEqual(0,polygon.Length,"无相机场景 → 空数组（无掩膜），不抛");
        }
        [Test] public void OwnshipPolygonChaseViewCentersAllFourCorners()
        {
            var go=new GameObject("ownship-camera");
            try
            {
                var camera=go.AddComponent<Camera>();
                camera.aspect=16f/9f; camera.fieldOfView=60;
                // 船：原点朝 +Z，LOA 40（艏 z=+20 艉 z=-20）、beam 4（±2），水线 y=0；
                // 相机艉后上方 (0,12,-45)，俯角 atan(12/45) 恰对船中 → 四角全入画居中。
                float pitch=Mathf.Atan(12f/45f)*Mathf.Rad2Deg;
                go.transform.SetPositionAndRotation(new Vector3(0,12,-45),Quaternion.Euler(pitch,0,0));
                var polygon=TwinSituationMath.OwnshipPolygon(camera,
                    new Vector3(-2,0,20),new Vector3(2,0,20),new Vector3(2,0,-20),new Vector3(-2,0,-20));
                Assert.AreEqual(4,polygon.Length,"追随居中：四角全保留");
                foreach(var corner in polygon) Assert.IsTrue(corner.in_frame,$"角点应在画面内 ({corner.x:0.00},{corner.y:0.00})");
                Assert.Less(polygon[0].x,polygon[1].x,"顺序[艏左,艏右]：左舷 x<右舷");
                Assert.Greater(polygon[0].depth,polygon[2].depth,"艏比艉离相机远");
                float cx=(polygon[0].x+polygon[1].x+polygon[2].x+polygon[3].x)/4f;
                float cy=(polygon[0].y+polygon[1].y+polygon[2].y+polygon[3].y)/4f;
                Assert.AreEqual(.5f,cx,.02f,"水线中心 ≈ 画面水平中心");
                Assert.AreEqual(.5f,cy,.15f,"水线中心 ≈ 画面垂直中心（俯角对准船中）");
            }
            finally { Object.DestroyImmediate(go); }
        }
        [Test] public void OwnshipPolygonPartialOutOfFrameKeepsUnclampedCornersWithFlags()
        {
            var go=new GameObject("ownship-camera");
            try
            {
                var camera=go.AddComponent<Camera>();
                camera.aspect=16f/9f; camera.fieldOfView=30; // 窄视场+贴近艏前看船：艏两角甩出画面
                go.transform.SetPositionAndRotation(new Vector3(0,2,22),Quaternion.Euler(0,180,0));
                var polygon=TwinSituationMath.OwnshipPolygon(camera,
                    new Vector3(-2,0,20),new Vector3(2,0,20),new Vector3(2,0,-20),new Vector3(-2,0,-20));
                Assert.AreEqual(4,polygon.Length,"部分出画仍给全 4 角点（相机前方全保留）");
                Assert.IsFalse(polygon[0].in_frame,"艏左舷角出画");
                Assert.IsFalse(polygon[1].in_frame,"艏右舷角出画");
                Assert.IsTrue(polygon[2].in_frame&&polygon[3].in_frame,"艉两角仍在画面内");
                Assert.IsTrue(polygon[0].x>1f||polygon[0].x<0f||polygon[0].y>1f||polygon[0].y<0f,
                    "出画角点坐标不钳位（保留越界值供消费端裁剪）");
                // 相机移到船中看艏向：艉两角在相机身后（z≤近轴）被弃 → 剩 2 角 <3 → 空数组。
                go.transform.SetPositionAndRotation(new Vector3(0,3,0),Quaternion.identity);
                var behind=TwinSituationMath.OwnshipPolygon(camera,
                    new Vector3(-2,0,20),new Vector3(2,0,20),new Vector3(2,0,-20),new Vector3(-2,0,-20));
                Assert.AreEqual(0,behind.Length,"桥眼位语义：身后角点丢弃后 <3 → 空数组=无掩膜");
            }
            finally { Object.DestroyImmediate(go); }
        }
        [Test] public void FrameJsonRoundTripsOwnshipPolygonAndRelayEnvelope()
        {
            var corner=new TwinOwnshipCorner { x=.25f,y=.75f,depth=48.5f,in_frame=true };
            var frame=new TwinSituationFrame { width=1280,height=720,
                ownship_polygon=new[]{corner,
                    new TwinOwnshipCorner { x=.55f,y=.75f,depth=50f,in_frame=true },
                    new TwinOwnshipCorner { x=.55f,y=.9f,depth=52f,in_frame=false },
                    new TwinOwnshipCorner { x=.25f,y=.9f,depth=51f,in_frame=true }} };
            var json=frame.ToJson();
            StringAssert.Contains("\"ownship_polygon\":[{",json);
            StringAssert.Contains("\"in_frame\":false",json);
            var back=JsonUtility.FromJson<TwinSituationFrame>(json);
            Assert.AreEqual(4,back.ownship_polygon.Length);
            Assert.AreEqual(.25f,back.ownship_polygon[0].x,1e-5f);
            Assert.IsFalse(back.ownship_polygon[2].in_frame);
            // 中继信封（viewport_ownship_polygon@1）字段名逐字对拍（后端 pydantic 冻结契约）。
            var report=new TwinOwnshipPolygonReport { run_id="run",sim_time=12.5,
                camera_pose=new TwinBridgeCameraPose { east=1,north=2,height_m=3,yaw_deg=4,pitch_deg=-5,fov_deg=60 },
                frames=new[]{new TwinOwnshipPolygonFrameEntry { frame_id=4171,polygon=new[]{corner} }} };
            var reportJson=report.ToJson();
            StringAssert.Contains("\"schema\":\"viewport_ownship_polygon@1\"",reportJson);
            StringAssert.Contains("\"frame_id\":4171",reportJson);
            var reportBack=JsonUtility.FromJson<TwinOwnshipPolygonReport>(reportJson);
            Assert.AreEqual(4171,reportBack.frames[0].frame_id);
            Assert.AreEqual(1,reportBack.frames[0].polygon.Length);
            Assert.AreEqual(60f,reportBack.camera_pose.fov_deg,1e-4f);
        }

        [Test] public void DetectionProjectionMirrorsNonTruthTargetBoundsWithoutShipsGate()
        {
            // TwinSituationDisplay lives in Assembly-CSharp (no asmdef at Runtime root) — reflect.
            var display=TestReflection.FindAssemblyCSharpType("Sango.TwinSituationDisplay");
            var project=display.GetMethod("ProjectDetection",BindingFlags.NonPublic|BindingFlags.Static);
            Assert.That(project,Is.Not.Null);
            var go=new GameObject("detection-camera");
            try
            {
                var camera=go.AddComponent<Camera>();
                camera.aspect=1; camera.fieldOfView=60;
                go.transform.SetPositionAndRotation(new Vector3(0,3,0),Quaternion.identity);
                var anchor=new TwinAnchor { EastM=500000,NorthM=6959000,LandingM=Vector2.zero };
                var detection=new TwinDisplayDetection { east=500000,north=6959100,length=12,width=5,
                    confidence=.91f,class_name="boat",sensor_id=2,key="2:104:0",track_key="run:2:8" };
                TwinScreenDetection Project() => (TwinScreenDetection)project.Invoke(null,new object[]{ camera,detection,anchor });
                var screen=Project();
                Assert.AreEqual(.5f,screen.x,1e-3f);
                Assert.AreEqual(.5f,screen.y,1e-3f);
                Assert.AreEqual(100f,screen.depth,.01f);
                Assert.IsTrue(screen.visible);
                Assert.AreEqual(.91f,screen.confidence,1e-5f);
                Assert.AreEqual("boat",screen.class_name);
                Assert.AreEqual(2,screen.sensor_id);
                Assert.AreEqual("2:104:0",screen.key);
                Assert.AreEqual("run:2:8",screen.track_key);
                // Axis-aligned oracle: half-extents (Max(8,w)/2, 2.5, Max(12,l)/2), nearest face z=94.
                float unit=1f/(2f*94f*Mathf.Tan(30f*Mathf.Deg2Rad));
                Assert.AreEqual(8f*unit,screen.width,1e-3f,"width uses Max(8,width_m) bounds");
                Assert.AreEqual(5f*unit,screen.height,1e-3f,"height uses fixed 5 m bounds");
                Assert.LessOrEqual(Mathf.Abs(screen.left+screen.width*.5f-.5f),1e-3f);
                Assert.LessOrEqual(Mathf.Abs(screen.top+screen.height*.5f-.5f),1e-3f);
                detection.width=8; var clamped=Project();
                Assert.AreEqual(screen.width,clamped.width,1e-5f,"width<=8 collapses to min-clamped box");
                detection.width=20; var wide=Project();
                Assert.Greater(wide.width,clamped.width);
                detection.width=5; detection.north=6958900;
                var behind=Project();
                Assert.IsFalse(behind.visible);
                Assert.AreEqual(-100f,behind.depth,.01f);
            }
            finally { Object.DestroyImmediate(go); }
        }
    }
}
