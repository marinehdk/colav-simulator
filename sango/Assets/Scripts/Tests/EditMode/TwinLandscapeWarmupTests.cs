using NUnit.Framework;
using UnityEngine;
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
        [Test] public void HealthyLargeViewCanKeepLoadingButWaitIsBounded()
        {
            var gate = new TwinLandscapeWarmup(); gate.Begin("large",0);
            for (int i = 1; i <= 6; i++) gate.Observe(i*40,i*10,true,false);
            Assert.That(gate.State,Is.EqualTo("warming"),"Progress beyond 180 seconds is not a network failure.");
            for (int i = 7; i <= 15; i++) gate.Observe(i*40,60+i,true,false);
            Assert.That(gate.State,Is.EqualTo("failed"),"The absolute startup wait still has a bound.");
        }
        [Test] public void PreloadFollowsRouteBendRatherThanExtrapolatingStraightIntoLand()
        {
            var route = new[] { Vector3.zero, new Vector3(0,0,1000), new Vector3(2000,0,1000) };
            var ahead = TwinLandscapeWarmup.Ahead(new Vector3(10,0,500), route, 1000, 0);
            Assert.That(ahead, Is.EqualTo(new Vector3(500,0,1000)));
            Assert.That(TwinLandscapeWarmup.Ahead(new Vector3(0,0,500), route, 10000, 0), Is.EqualTo(route[2]));
            Assert.That(TwinLandscapeWarmup.Ahead(Vector3.zero, null, 1000, 90).x, Is.EqualTo(1000).Within(.01));
        }
    }
}
