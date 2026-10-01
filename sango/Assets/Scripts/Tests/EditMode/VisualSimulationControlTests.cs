using NUnit.Framework;
using System.Linq;
using UnityEngine;

namespace Sango.Tests
{
    public class VisualSimulationControlTests
    {
        [Test]
        public void EgoSelectionRebindsCameraRadarAndForeignTargetOverlay()
        {
            var sessionType = TestReflection.FindLoadedType("Sango.VisualSimulationSession");
            var rigType = TestReflection.FindLoadedType("Sango.CameraRig");
            var radarType = TestReflection.FindLoadedType("Sango.RadarOverlay");
            var overlayType = TestReflection.FindLoadedType("Sango.DetectionOverlay");
            var model = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var catalog = ScriptableObject.CreateInstance<VesselCatalog>();
            catalog.entries = new[] { new VesselCatalog.Entry { vesselClass = VesselClass.Small, prefab = model, loaMeters = 12f } };
            var go = new GameObject("Ego binding test");
            var cameraGo = new GameObject("Binding camera", typeof(Camera));
            try
            {
                var rig = cameraGo.AddComponent(rigType);
                rigType.GetField("controlledCamera").SetValue(rig, cameraGo.GetComponent<Camera>());
                var radar = go.AddComponent(radarType);
                var overlay = go.AddComponent(overlayType);
                var session = go.AddComponent(sessionType);
                sessionType.GetField("catalog").SetValue(session, catalog);
                sessionType.GetField("cameraRig").SetValue(session, rig);
                sessionType.GetField("radar").SetValue(session, radar);
                sessionType.GetField("overlay").SetValue(session, overlay);
                var draft = new VisualSimulationSettings { sceneMode = VisualSceneMode.Procedural, vesselClass = VesselClass.Small };
                Assert.That(sessionType.GetMethod("Apply").Invoke(session, new object[] { draft }), Is.True);
                Assert.That(sessionType.GetMethod("SetEgo").Invoke(session, new object[] { 1 }), Is.True);
                var ego = (WaypointFollower)sessionType.GetProperty("Ego").GetValue(session);
                Assert.That(rigType.GetField("followShip").GetValue(rig), Is.SameAs(ego.transform));
                Assert.That(radarType.GetField("ownShip").GetValue(radar), Is.SameAs(ego.transform));
                var ships = (Transform[])overlayType.GetField("ships").GetValue(overlay);
                Assert.That(ships.Length, Is.EqualTo(1));
                Assert.That(ships[0], Is.Not.SameAs(ego.transform), "Onboard truth must describe other vessels, not the ego itself.");
                Assert.That(((Transform)rigType.GetField("bridgeMount").GetValue(rig)).parent, Is.SameAs(ego.transform));
            }
            finally { Object.DestroyImmediate(go); Object.DestroyImmediate(cameraGo); Object.DestroyImmediate(model); Object.DestroyImmediate(catalog); }
        }

        [Test]
        public void HeadOnPresetActuallyChangesTargetHeadingAndRoute()
        {
            var sessionType = TestReflection.FindLoadedType("Sango.VisualSimulationSession");
            var model = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var catalog = ScriptableObject.CreateInstance<VesselCatalog>();
            catalog.entries = new[] { new VesselCatalog.Entry { vesselClass = VesselClass.Small, prefab = model, loaMeters = 12f } };
            var go = new GameObject("Route preset test");
            try
            {
                var session = go.AddComponent(sessionType);
                sessionType.GetField("catalog").SetValue(session, catalog);
                var draft = new VisualSimulationSettings { sceneMode = VisualSceneMode.Procedural, vesselClass = VesselClass.Small, waypointPattern = VisualWaypointPattern.HeadOn };
                Assert.That(sessionType.GetMethod("Apply").Invoke(session, new object[] { draft }), Is.True);
                var actors = (System.Collections.Generic.IReadOnlyList<WaypointFollower>)sessionType.GetProperty("Actors").GetValue(session);
                Assert.That(actors[1].transform.eulerAngles.y, Is.EqualTo(180f).Within(0.1f));
                sessionType.GetMethod("StartRun").Invoke(session, null);
                var initial = actors[1].transform.position;
                sessionType.GetMethod("Step").Invoke(session, new object[] { 1f });
                Assert.That(actors[1].transform.position.z, Is.LessThan(initial.z));
            }
            finally { Object.DestroyImmediate(go); Object.DestroyImmediate(model); Object.DestroyImmediate(catalog); }
        }

        [Test]
        public void ProceduralIslandControlsChangeGeometryAndReplayTheSeed()
        {
            var sessionType = TestReflection.FindLoadedType("Sango.VisualSimulationSession");
            var model = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var catalog = ScriptableObject.CreateInstance<VesselCatalog>();
            catalog.entries = new[] { new VesselCatalog.Entry { vesselClass = VesselClass.Small, prefab = model, loaMeters = 12f } };
            var go = new GameObject("Island control test");
            try
            {
                var session = go.AddComponent(sessionType);
                sessionType.GetField("catalog").SetValue(session, catalog);
                var draft = new VisualSimulationSettings { sceneMode = VisualSceneMode.Procedural, vesselClass = VesselClass.Small, generateIslands = true, islandHeightM = 10f, seed = 731 };
                Assert.That(sessionType.GetMethod("Apply").Invoke(session, new object[] { draft }), Is.True);
                var islands = (System.Collections.Generic.IReadOnlyList<Transform>)sessionType.GetProperty("Islands").GetValue(session);
                Assert.That(islands.Count, Is.EqualTo(1));
                var mesh = islands[0].GetComponent<MeshFilter>().sharedMesh;
                var initial = mesh.vertices;
                var height = mesh.bounds.size.y;
                Assert.That(sessionType.GetMethod("Apply").Invoke(session, new object[] { draft }), Is.True);
                islands = (System.Collections.Generic.IReadOnlyList<Transform>)sessionType.GetProperty("Islands").GetValue(session);
                CollectionAssert.AreEqual(initial, islands[0].GetComponent<MeshFilter>().sharedMesh.vertices);
                draft.islandHeightM = 30f;
                Assert.That(sessionType.GetMethod("Apply").Invoke(session, new object[] { draft }), Is.True);
                islands = (System.Collections.Generic.IReadOnlyList<Transform>)sessionType.GetProperty("Islands").GetValue(session);
                Assert.That(islands[0].GetComponent<MeshFilter>().sharedMesh.bounds.size.y, Is.GreaterThan(height));
            }
            finally { Object.DestroyImmediate(go); Object.DestroyImmediate(model); Object.DestroyImmediate(catalog); }
        }

        [Test]
        public void CurrentAndManualTakeoverUseTheExistingMotionOwner()
        {
            var sessionType = TestReflection.FindLoadedType("Sango.VisualSimulationSession");
            var model = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var catalog = ScriptableObject.CreateInstance<VesselCatalog>();
            catalog.entries = new[] { new VesselCatalog.Entry { vesselClass = VesselClass.Small, prefab = model, loaMeters = 12f } };
            var go = new GameObject("Motion ownership test");
            try
            {
                var session = go.AddComponent(sessionType);
                sessionType.GetField("catalog").SetValue(session, catalog);
                var draft = new VisualSimulationSettings { sceneMode = VisualSceneMode.Procedural, vesselClass = VesselClass.Small, currentSpeedMps = 1f, currentDirectionDeg = 90f };
                Assert.That(sessionType.GetMethod("Apply").Invoke(session, new object[] { draft }), Is.True);
                var ego = (WaypointFollower)sessionType.GetProperty("Ego").GetValue(session);
                Assert.That(ego.enabled, Is.False, "Session dispatch and legacy Update must not both integrate the same actor.");
                sessionType.GetMethod("StartRun").Invoke(session, null);
                sessionType.GetMethod("Step").Invoke(session, new object[] { 1f });
                Assert.That(ego.transform.position.x, Is.EqualTo(1f).Within(0.05f), "One second of 1m/s east current must yield 1m of east drift.");
                sessionType.GetMethod("SetManualControl").Invoke(session, new object[] { true });
                sessionType.GetMethod("SetManualInput").Invoke(session, new object[] { 1f, 1f });
                sessionType.GetMethod("Step").Invoke(session, new object[] { 1f });
                Assert.That(ego.transform.eulerAngles.y, Is.GreaterThan(5f), "Manual starboard input must turn the actual vessel.");
                Assert.That(ego.SpeedMps, Is.GreaterThan(0f));
                sessionType.GetMethod("SetManualControl").Invoke(session, new object[] { false });
                Assert.That(sessionType.GetProperty("ManualControl").GetValue(session), Is.False);
            }
            finally { Object.DestroyImmediate(go); Object.DestroyImmediate(model); Object.DestroyImmediate(catalog); }
        }

        [Test]
        public void RemovingTargetKeepsOtherVesselIdsStableAndAddReusesVacantSlot()
        {
            var sessionType = TestReflection.FindLoadedType("Sango.VisualSimulationSession");
            var model = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var catalog = ScriptableObject.CreateInstance<VesselCatalog>();
            catalog.entries = new[] { new VesselCatalog.Entry { vesselClass = VesselClass.Small, prefab = model, loaMeters = 12f } };
            var go = new GameObject("Target editing test");
            try
            {
                var session = go.AddComponent(sessionType);
                sessionType.GetField("catalog").SetValue(session, catalog);
                var draft = new VisualSimulationSettings { sceneMode = VisualSceneMode.Procedural, vesselClass = VesselClass.Small, agentsPerEnvironment = 3 };
                Assert.That(sessionType.GetMethod("Apply").Invoke(session, new object[] { draft }), Is.True);
                Assert.That(sessionType.GetMethod("RemoveTarget").Invoke(session, new object[] { 1 }), Is.True);
                Assert.That(sessionType.GetProperty("ActorCount").GetValue(session), Is.EqualTo(2));
                var actors = (System.Collections.Generic.IReadOnlyList<WaypointFollower>)sessionType.GetProperty("Actors").GetValue(session);
                Assert.That(actors[1], Is.Null);
                Assert.That(actors[2], Is.Not.Null, "Removing target 1 must not rename target 2.");
                Assert.That(sessionType.GetMethod("AddTarget").Invoke(session, new object[] {
                    new VisualTargetVessel { vesselClass = VesselClass.Small, offsetMeters = new Vector2(40f, 60f), motion = VisualTargetMotion.Straight }
                }), Is.True);
                actors = (System.Collections.Generic.IReadOnlyList<WaypointFollower>)sessionType.GetProperty("Actors").GetValue(session);
                Assert.That(actors[1].transform.position.x, Is.EqualTo(40f));
                Assert.That(actors[2], Is.Not.Null);
                Assert.That(sessionType.GetMethod("RemoveTarget").Invoke(session, new object[] { 0 }), Is.False, "Select another ego before removing the current one.");
            }
            finally { Object.DestroyImmediate(go); Object.DestroyImmediate(model); Object.DestroyImmediate(catalog); }
        }

        [Test]
        public void SceneDefinitionRoundTripRestoresAuthoredTargetConfiguration()
        {
            var sessionType = TestReflection.FindLoadedType("Sango.VisualSimulationSession");
            var model = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var catalog = ScriptableObject.CreateInstance<VesselCatalog>();
            catalog.entries = new[] { new VesselCatalog.Entry { vesselClass = VesselClass.Small, prefab = model, loaMeters = 12f } };
            var go = new GameObject("Scene definition test");
            try
            {
                var session = go.AddComponent(sessionType);
                sessionType.GetField("catalog").SetValue(session, catalog);
                var draft = new VisualSimulationSettings { sceneMode = VisualSceneMode.Procedural, vesselClass = VesselClass.Small, seed = 912 };
                Assert.That(sessionType.GetMethod("Apply").Invoke(session, new object[] { draft }), Is.True);
                var json = (string)sessionType.GetMethod("ExportSceneJson").Invoke(session, null);
                StringAssert.Contains("sango.visual-scene@1", json);
                draft.agentsPerEnvironment = 3;
                Assert.That(sessionType.GetMethod("Apply").Invoke(session, new object[] { draft }), Is.True);
                Assert.That(sessionType.GetMethod("ImportSceneJson").Invoke(session, new object[] { json }), Is.True);
                Assert.That(sessionType.GetProperty("ActorCount").GetValue(session), Is.EqualTo(2));
                var restored = (VisualSimulationSettings)sessionType.GetProperty("AppliedSettings").GetValue(session);
                Assert.That(restored.seed, Is.EqualTo(912));
                var ego = sessionType.GetProperty("Ego").GetValue(session);
                Assert.That(sessionType.GetMethod("ImportSceneJson").Invoke(session, new object[] { "{\"schema_version\":\"invalid\"}" }), Is.False);
                Assert.That(sessionType.GetProperty("Ego").GetValue(session), Is.SameAs(ego), "Invalid files must preserve the applied world.");
            }
            finally { Object.DestroyImmediate(go); Object.DestroyImmediate(model); Object.DestroyImmediate(catalog); }
        }

        [Test]
        public void StartPauseAndRunningApplyKeepOneCoherentRun()
        {
            var sessionType = TestReflection.FindLoadedType("Sango.VisualSimulationSession");
            var draft = new VisualSimulationSettings { sceneMode = VisualSceneMode.Procedural, vesselClass = VesselClass.Small };
            var catalog = ScriptableObject.CreateInstance<VesselCatalog>();
            var model = GameObject.CreatePrimitive(PrimitiveType.Cube);
            catalog.entries = new[] { new VesselCatalog.Entry { vesselClass = VesselClass.Small, prefab = model, loaMeters = 12f } };
            var go = new GameObject("Run lifecycle test");
            try
            {
                var session = go.AddComponent(sessionType);
                sessionType.GetField("catalog").SetValue(session, catalog);
                Assert.That(sessionType.GetMethod("Apply").Invoke(session, new object[] { draft }), Is.True);
                var ego = (WaypointFollower)sessionType.GetProperty("Ego").GetValue(session);
                sessionType.GetMethod("StartRun").Invoke(session, null);
                sessionType.GetMethod("Step").Invoke(session, new object[] { 1f });
                Assert.That(ego.transform.position.z, Is.GreaterThan(-100f));
                Assert.That(sessionType.GetMethod("Apply").Invoke(session, new object[] { draft }), Is.False,
                    "Running scene must not be silently replaced by applying the draft.");
                Assert.That(sessionType.GetProperty("Ego").GetValue(session), Is.SameAs(ego));
                sessionType.GetMethod("PauseRun").Invoke(session, null);
                var paused = ego.transform.position;
                sessionType.GetMethod("Step").Invoke(session, new object[] { 1f });
                Assert.That(ego.transform.position, Is.EqualTo(paused));
            }
            finally { Object.DestroyImmediate(go); Object.DestroyImmediate(model); Object.DestroyImmediate(catalog); }
        }

        [Test]
        public void IndividualTargetControlsRenderedTypePoseAndMotion()
        {
            var settingsType = TestReflection.FindLoadedType("Sango.VisualSimulationSettings");
            var targetType = TestReflection.FindLoadedType("Sango.VisualTargetVessel");
            var sessionType = TestReflection.FindLoadedType("Sango.VisualSimulationSession");
            var draft = System.Activator.CreateInstance(settingsType);
            settingsType.GetField("sceneMode").SetValue(draft, System.Enum.ToObject(settingsType.GetField("sceneMode").FieldType, 1));
            settingsType.GetField("vesselClass").SetValue(draft, VesselClass.Small);
            var target = System.Activator.CreateInstance(targetType);
            targetType.GetField("id").SetValue(target, 1);
            targetType.GetField("vesselClass").SetValue(target, VesselClass.Large);
            targetType.GetField("offsetMeters").SetValue(target, new Vector2(100f, 80f));
            targetType.GetField("headingDeg").SetValue(target, 90f);
            targetType.GetField("speedMps").SetValue(target, 3f);
            targetType.GetField("motion").SetValue(target, System.Enum.ToObject(targetType.GetField("motion").FieldType, 1));
            var targets = System.Array.CreateInstance(targetType, 1);
            targets.SetValue(target, 0);
            settingsType.GetField("targets").SetValue(draft, targets);
            var small = GameObject.CreatePrimitive(PrimitiveType.Cube);
            small.transform.localScale = new Vector3(12f, 2f, 4f);
            var large = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            large.transform.localScale = new Vector3(60f, 5f, 15f);
            var catalog = ScriptableObject.CreateInstance<VesselCatalog>();
            catalog.entries = new[] {
                new VesselCatalog.Entry { vesselClass = VesselClass.Small, prefab = small, loaMeters = 12f },
                new VesselCatalog.Entry { vesselClass = VesselClass.Large, prefab = large, loaMeters = 60f }
            };
            var go = new GameObject("Individual target test");
            try
            {
                var session = go.AddComponent(sessionType);
                sessionType.GetField("catalog").SetValue(session, catalog);
                Assert.That(sessionType.GetMethod("Apply").Invoke(session, new[] { draft }), Is.True);
                var actors = ((System.Collections.Generic.IReadOnlyList<WaypointFollower>)sessionType.GetProperty("Actors").GetValue(session)).ToArray();
                Assert.That(actors[1].transform.position, Is.EqualTo(new Vector3(100f, 0f, 80f)));
                Assert.That(actors[1].GetComponentInChildren<Renderer>().bounds.size.x, Is.GreaterThan(10f), "Selected large model must change actual rendered geometry.");
                Assert.That(actors[1].cruiseSpeedMps, Is.EqualTo(3f));
                actors[1].StepOnce(1f);
                Assert.That(actors[1].transform.position.x, Is.GreaterThan(100f));
                Assert.That(actors[1].transform.position.z, Is.EqualTo(80f).Within(0.1f));
            }
            finally { Object.DestroyImmediate(go); Object.DestroyImmediate(small); Object.DestroyImmediate(large); Object.DestroyImmediate(catalog); }
        }

        [Test]
        public void ValidDraftCreatesConfiguredVesselsAndBindsChosenEgo()
        {
            var settingsType = TestReflection.FindLoadedType("Sango.VisualSimulationSettings");
            var sessionType = TestReflection.FindLoadedType("Sango.VisualSimulationSession");
            var draft = System.Activator.CreateInstance(settingsType);
            settingsType.GetField("sceneMode").SetValue(draft, System.Enum.ToObject(settingsType.GetField("sceneMode").FieldType, 1));
            settingsType.GetField("environmentCount").SetValue(draft, 2);
            settingsType.GetField("agentsPerEnvironment").SetValue(draft, 3);
            settingsType.GetField("vesselClass").SetValue(draft, VesselClass.Small);
            settingsType.GetField("egoId").SetValue(draft, 4);
            var catalog = ScriptableObject.CreateInstance<VesselCatalog>();
            var model = GameObject.CreatePrimitive(PrimitiveType.Cube);
            catalog.entries = new[] { new VesselCatalog.Entry { vesselClass = VesselClass.Small, prefab = model, loaMeters = 12f } };
            var go = new GameObject("Visual simulation control test");
            try
            {
                var session = go.AddComponent(sessionType);
                sessionType.GetField("catalog").SetValue(session, catalog);
                Assert.That(sessionType.GetMethod("Apply").Invoke(session, new[] { draft }), Is.True);
                Assert.That(sessionType.GetProperty("ActorCount").GetValue(session), Is.EqualTo(6));
                var ego = (WaypointFollower)sessionType.GetProperty("Ego").GetValue(session);
                Assert.That(ego, Is.Not.Null);
                Assert.That(ego.transform.position.x, Is.GreaterThan(200f), "Second environment must use configured spacing.");
            }
            finally { Object.DestroyImmediate(go); Object.DestroyImmediate(model); Object.DestroyImmediate(catalog); }
        }

        [Test]
        public void ApplyingOverBudgetDraftCreatesNoVesselsAndExplainsLimit()
        {
            var settingsType = TestReflection.FindLoadedType("Sango.VisualSimulationSettings");
            var sessionType = TestReflection.FindLoadedType("Sango.VisualSimulationSession");
            var draft = System.Activator.CreateInstance(settingsType);
            settingsType.GetField("environmentCount").SetValue(draft, 16);
            settingsType.GetField("agentsPerEnvironment").SetValue(draft, 3);
            var go = new GameObject("Visual simulation control test");
            try
            {
                var session = go.AddComponent(sessionType);
                Assert.That(sessionType.GetMethod("Apply").Invoke(session, new[] { draft }), Is.False);
                Assert.That(sessionType.GetProperty("ActorCount").GetValue(session), Is.EqualTo(0));
                StringAssert.Contains("32", (string)sessionType.GetProperty("Status").GetValue(session));
            }
            finally { Object.DestroyImmediate(go); }
        }
    }
}
