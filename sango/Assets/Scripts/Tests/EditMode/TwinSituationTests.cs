using NUnit.Framework;

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
    }
}
