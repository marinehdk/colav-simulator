using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    public class NorwayChartFrameTests
    {
        [TestCase(-3000,-3000,1.3628f)]
        [TestCase(3000,3000,1.4365f)]
        [TestCase(-9000,-9000,12.4159f)]
        [TestCase(9000,9000,12.6269f)]
        public void EllipsoidToChartHeightMatchesGdalControlPoints(float x,float z,float expected)
            => Assert.That(NorwayChartFrame.SeaLevelCorrection(new Vector3(x,0,z)),Is.EqualTo(expected).Within(0.03f));

        [Test]
        public void CurrentEncAndVesselsShareFixedProjectedOrigin()
        {
            var anchor = NorwayChartFrame.Anchor;
            // Current API: EPSG:25833, ENC southwest (39000,6956450).
            // Ownship (39000,6957000) = 62.4558125192 N, 6.0437370541 E.
            Assert.That(anchor.ToLocal(39000, 6957000), Is.EqualTo(new Vector2(-3000, -2450)));
            Assert.That(anchor.ToLocal(40000, 6958000), Is.EqualTo(new Vector2(-2000, -1450)));
            Assert.That(anchor.ToLocal(45000, 6962450), Is.EqualTo(new Vector2(3000, 3000)));
            Assert.That(anchor.LandingM, Is.EqualTo(Vector2.zero), "No Singapore relocation.");
            Assert.That(NorwayChartFrame.Contains(new Vector2(3000, 3000)), Is.True);
            Assert.That(NorwayChartFrame.Contains(new Vector2(21000, -5000)), Is.False);
        }
    }
}
