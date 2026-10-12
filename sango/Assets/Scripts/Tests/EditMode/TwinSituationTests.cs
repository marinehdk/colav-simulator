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
            Assert.AreEqual("2:104:0",back.detections[0].key);
            Assert.AreEqual(41f,back.detections[0].depth,1e-4f);
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
