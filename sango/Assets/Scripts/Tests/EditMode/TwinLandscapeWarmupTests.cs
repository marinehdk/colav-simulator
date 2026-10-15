using NUnit.Framework;
using UnityEngine;
using System;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Collections.Concurrent;
namespace Sango.Tests
{
    public class TwinLandscapeWarmupTests
    {
        [Test] public void ReadinessRequiresStableLoadedViewsAndNeverHidesAgainOnPan()
        {
            var gate = new TwinLandscapeWarmup(); gate.Begin("a", 0);
            gate.Observe(5, 100, true, false); gate.Observe(7, 50, true, false);
            gate.Observe(10, 100, true, false); gate.Observe(13, 100, true, false);
            Assert.That(gate.Ready, Is.False);
            gate.Observe(14, 100, true, false); Assert.That(gate.Ready, Is.True);
            gate.Observe(15, 50, true, false); Assert.That(gate.Ready, Is.True);
            gate.Begin("b", 16); Assert.That(gate.Ready, Is.False);
        }
        [Test] public void MissingProviderUsesLocalTerrainButTimeoutNeverPretendsReady()
        {
            var gate = new TwinLandscapeWarmup(); gate.Begin("a", 0);
            gate.Observe(1, 0, false, false); Assert.That(gate.State, Is.EqualTo("offline-terrain"));
            gate.Begin("b", 2); gate.Observe(3, 95, true, false); gate.Observe(182, 95, true, false);
            Assert.That(gate.State, Is.EqualTo("failed")); Assert.That(gate.Ready, Is.False);
        }
        [Test] public void FailedWarmupReleasesTheStartupViewBeforeItRecovers()
        {
            var gate = new TwinLandscapeWarmup(); gate.Begin("stuck", 0);
            Assert.That(gate.StartupViewNeeded, Is.True, "Warming views still refine through the startup camera.");
            gate.Observe(10, 40, true, false); gate.Observe(101, 40, true, false);
            Assert.That(gate.State, Is.EqualTo("failed"));
            Assert.That(gate.StartupViewNeeded, Is.False,
                "A failed region must not pin the degraded extra-frustum selection set.");
            gate.Observe(700, 100, true, false); gate.Observe(704, 100, true, false);
            Assert.That(gate.Ready, Is.True);
            Assert.That(gate.StartupViewNeeded, Is.False);
        }
        [Test] public void HealthyLargeViewCanKeepLoadingButWaitIsBounded()
        {
            var gate = new TwinLandscapeWarmup(); gate.Begin("large",0);
            for (int i = 1; i <= 6; i++) gate.Observe(i*40,i*10,true,false);
            Assert.That(gate.State,Is.EqualTo("warming"),"Progress beyond 180 seconds is not a network failure.");
            for (int i = 7; i <= 15; i++) gate.Observe(i*40,60+i,true,false);
            Assert.That(gate.State,Is.EqualTo("failed"),"The absolute startup wait still has a bound.");
        }
        [Test] public void TimedOutDownloadsRecoverOnlyAfterStableLoadedViews()
        {
            var gate = new TwinLandscapeWarmup(); gate.Begin("slow",0);
            gate.Observe(10,25.5f,true,false); gate.Observe(101,25.5f,true,false);
            Assert.That(gate.State,Is.EqualTo("failed"));
            gate.Observe(700,100,true,false); gate.Observe(703,100,true,false);
            Assert.That(gate.Ready,Is.False);
            gate.Observe(704,100,true,false);
            Assert.That(gate.Ready,Is.True,"Completed downloads must recover within the same session.");
        }
        [Test] public void ProviderFailureAndIncompleteViewsStillBlockRecovery()
        {
            var gate = new TwinLandscapeWarmup(); gate.Begin("retry",0);
            gate.Observe(1,100,true,true); gate.Observe(10,100,true,true);
            Assert.That(gate.Ready,Is.False);
            gate.Observe(11,100,true,false); gate.Observe(14,98,true,false);
            gate.Observe(15,100,true,false); gate.Observe(18,100,true,false);
            Assert.That(gate.Ready,Is.False);
            gate.Observe(19,100,true,false); Assert.That(gate.Ready,Is.True);
        }
        [Test] public void PreloadFollowsRouteBendRatherThanExtrapolatingStraightIntoLand()
        {
            var route = new[] { Vector3.zero, new Vector3(0,0,1000), new Vector3(2000,0,1000) };
            var ahead = TwinLandscapeWarmup.Ahead(new Vector3(10,0,500), route, 1000, 0);
            Assert.That(ahead, Is.EqualTo(new Vector3(500,0,1000)));
            Assert.That(TwinLandscapeWarmup.Ahead(new Vector3(0,0,500), route, 10000, 0), Is.EqualTo(route[2]));
            Assert.That(TwinLandscapeWarmup.Ahead(Vector3.zero, null, 1000, 90).x, Is.EqualTo(1000).Within(.01));
        }
        [Test] public void DetachSuspendsSelectionAndReattachPreservesTheTileset()
        {
            var root = new GameObject("retained-landscape"); root.SetActive(false);
            var type = TestReflection.FindAssemblyCSharpType("Sango.TwinCesiumLandscape");
            var landscape = root.AddComponent(type);
            var tilesetType = AppDomain.CurrentDomain.GetAssemblies().Select(a => a.GetType("CesiumForUnity.Cesium3DTileset"))
                .First(t => t != null);
            var tileset = root.AddComponent(tilesetType);
            var flags = BindingFlags.Instance | BindingFlags.NonPublic;
            type.GetField("m_Terrain",flags).SetValue(landscape,tileset);
            try
            {
                type.GetMethod("ResetWarmup").Invoke(landscape,null);
                Assert.That(tilesetType.GetProperty("suspendUpdate").GetValue(tileset),Is.True,
                    "An idle retained renderer must not refine the restored demo or old route views.");
                type.GetMethod("PrepareViews").Invoke(landscape,new object[] {"new",Vector3.zero,0f,Array.Empty<Vector3>()});
                Assert.That(tilesetType.GetProperty("suspendUpdate").GetValue(tileset),Is.False);
                Assert.That(type.GetField("m_Terrain",flags).GetValue(landscape),Is.SameAs(tileset),
                    "Reattachment must keep the native tileset/cache owner.");
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }
        [Test] public void DistantSessionSwitchShrinksTheCacheThenRestoresIt()
        {
            var root = new GameObject("region-switch"); root.SetActive(false);
            var type = TestReflection.FindAssemblyCSharpType("Sango.TwinCesiumLandscape");
            var landscape = root.AddComponent(type);
            var tilesetType = AppDomain.CurrentDomain.GetAssemblies().Select(a => a.GetType("CesiumForUnity.Cesium3DTileset"))
                .First(t => t != null);
            var tileset = root.AddComponent(tilesetType);
            var flags = BindingFlags.Instance | BindingFlags.NonPublic;
            type.GetField("m_Terrain",flags).SetValue(landscape,tileset);
            tilesetType.GetProperty("maximumCachedBytes").SetValue(tileset,4L*1024*1024*1024);
            type.GetField("m_RegionAnchored",flags).SetValue(landscape,true);
            type.GetField("m_PreloadAnchor",flags).SetValue(landscape,Vector3.zero);
            try
            {
                type.GetMethod("PrepareViews").Invoke(landscape,
                    new object[] {"far",new Vector3(9000,0,0),0f,Array.Empty<Vector3>()});
                Assert.That((long)tilesetType.GetProperty("maximumCachedBytes").GetValue(tileset),
                    Is.EqualTo(256L*1024*1024),
                    "A distant session must hand the cache over instead of churning against the old region.");
                type.GetField("m_ShrinkRounds",flags).SetValue(landscape,1); // expire the window
                type.GetMethod("PrepareViews").Invoke(landscape,
                    new object[] {"far",new Vector3(9100,0,0),0f,Array.Empty<Vector3>()});
                Assert.That((long)tilesetType.GetProperty("maximumCachedBytes").GetValue(tileset),
                    Is.EqualTo(4L*1024*1024*1024),
                    "After the handover window the full ceiling returns for the new session.");
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }
        [Test] public void PausedAttachmentWarmsBeforeSuspendingGeography()
        {
            var root = new GameObject("paused-warmup"); root.SetActive(false);
            var own = new GameObject("paused-ownship");
            var flags = BindingFlags.Instance | BindingFlags.NonPublic;
            var landscapeType = TestReflection.FindAssemblyCSharpType("Sango.TwinCesiumLandscape");
            var driverType = TestReflection.FindAssemblyCSharpType("Sango.TwinSessionDriver");
            var bridgeType = TestReflection.FindAssemblyCSharpType("Sango.TwinBridgeService");
            var situationType = TestReflection.FindAssemblyCSharpType("Sango.TwinSituationDisplay");
            var tilesetType = AppDomain.CurrentDomain.GetAssemblies().Select(a => a.GetType("CesiumForUnity.Cesium3DTileset")).First(t => t != null);
            var landscape = root.AddComponent(landscapeType);
            var driver = root.AddComponent(driverType);
            var bridge = root.AddComponent(bridgeType);
            var situation = root.AddComponent(situationType);
            var tileset = root.AddComponent(tilesetType);
            var gate = (TwinLandscapeWarmup)landscapeType.GetField("m_Warmup",flags).GetValue(landscape);
            try
            {
                var slotType = driverType.GetNestedType("TwinSlot",BindingFlags.NonPublic);
                var slot = Activator.CreateInstance(slotType);
                slotType.GetField("Ship").SetValue(slot,own);
                var slots = (System.Collections.IDictionary)driverType.GetField("m_Slots",flags).GetValue(driver);
                slots.Add(0,slot);
                driverType.GetField("m_Latest",flags).SetValue(driver,new ColavTelemetry {
                    truth = new[] { new ColavTelemetry.ShipEntry { id = 0 } }
                });
                driverType.GetField("m_Anchor",flags).SetValue(driver,TwinAnchor.FromOrigin(0,0));
                bridgeType.GetField("m_RunId",flags).SetValue(bridge,"paused");
                bridgeType.GetField("m_Mode",flags).SetValue(bridge,"replay");
                bridgeType.GetField("m_PlayState",flags).SetValue(bridge,"PAUSED");
                bridgeType.GetField("m_Situation",flags).SetValue(bridge,situation);
                situationType.GetField("m_Shown",flags).SetValue(situation,new TwinSituationMessage { run_id = "paused" });
                landscapeType.GetField("m_Driver",flags).SetValue(landscape,driver);
                landscapeType.GetField("m_Bridge",flags).SetValue(landscape,bridge);
                landscapeType.GetField("m_Terrain",flags).SetValue(landscape,tileset);
                landscapeType.GetMethod("ResetWarmup").Invoke(landscape,null);
                landscapeType.GetMethod("UpdateWarmup",flags).Invoke(landscape,null);
                Assert.That(gate.RunId,Is.EqualTo("paused"),"Paused attach must leave waiting-session.");
                Assert.That(tilesetType.GetProperty("suspendUpdate").GetValue(tileset),Is.False);
                gate.Observe(10,100,true,false); gate.Observe(14,100,true,false);
                landscapeType.GetMethod("UpdateWarmup",flags).Invoke(landscape,null);
                Assert.That(tilesetType.GetProperty("suspendUpdate").GetValue(tileset),Is.True,
                    "Retain the steady-state pause optimization once geography is ready.");
            }
            finally { UnityEngine.Object.DestroyImmediate(root); UnityEngine.Object.DestroyImmediate(own); }
        }
        [Test] public void NearbySessionSwitchKeepsTheCacheCeiling()
        {
            var root = new GameObject("same-region"); root.SetActive(false);
            var type = TestReflection.FindAssemblyCSharpType("Sango.TwinCesiumLandscape");
            var landscape = root.AddComponent(type);
            var tilesetType = AppDomain.CurrentDomain.GetAssemblies().Select(a => a.GetType("CesiumForUnity.Cesium3DTileset"))
                .First(t => t != null);
            var tileset = root.AddComponent(tilesetType);
            var flags = BindingFlags.Instance | BindingFlags.NonPublic;
            type.GetField("m_Terrain",flags).SetValue(landscape,tileset);
            tilesetType.GetProperty("maximumCachedBytes").SetValue(tileset,4L*1024*1024*1024);
            type.GetField("m_RegionAnchored",flags).SetValue(landscape,true);
            type.GetField("m_PreloadAnchor",flags).SetValue(landscape,Vector3.zero);
            try
            {
                type.GetMethod("PrepareViews").Invoke(landscape,
                    new object[] {"near",new Vector3(100,0,0),0f,Array.Empty<Vector3>()});
                Assert.That((long)tilesetType.GetProperty("maximumCachedBytes").GetValue(tileset),
                    Is.EqualTo(4L*1024*1024*1024),
                    "Re-testing in the same neighbourhood is the reuse case; the cache stays.");
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }
        [Test] public void StaleReceiveThreadCannotTurnOffTheNewAttachment()
        {
            var root = new GameObject("rebound-driver");
            var type = TestReflection.FindAssemblyCSharpType("Sango.TwinSessionDriver");
            var driver = root.AddComponent(type);
            var flags = BindingFlags.Instance | BindingFlags.NonPublic;
            var cancel = new CancellationTokenSource();
            type.GetField("m_Cancel",flags).SetValue(driver,cancel);
            type.GetField("m_Inbox",flags).SetValue(driver,new ConcurrentQueue<ColavTelemetry>());
            type.GetField("m_Thread",flags).SetValue(driver,new Thread(() => {}));
            type.GetField("m_Running",flags).SetValue(driver,true);
            type.GetField("runtimeEnabled").SetValue(driver,true);
            type.GetField("sessionId").SetValue(driver,"new-session");
            type.GetField("backendBase").SetValue(driver,"http://127.0.0.1:1");
            try
            {
                var stale = new Thread(() => type.GetMethod("ReceiveLoop",flags).Invoke(driver,null));
                stale.Start(); Assert.That(stale.Join(2000),Is.True);
                Assert.That(type.GetField("runtimeEnabled").GetValue(driver),Is.True,
                    "A superseded receiver cannot mutate the new attachment's running flags.");
            }
            finally { UnityEngine.Object.DestroyImmediate(root); cancel.Dispose(); }
        }
    }
}
