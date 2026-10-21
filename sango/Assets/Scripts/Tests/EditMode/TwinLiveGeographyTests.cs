using System.IO;
using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// 青岛域 live 会话地理面（2026-10-21 场景布置）：
    /// ① TwinLiveGeographyProbe——enc_info JSON → 是否 UTM51 青岛域；
    /// ② 外部地理锚几何——QingdaoStaticScene.Open 注入的零登记平移锚下，
    /// 船位直落 (E-256315, N-3992326) 本地地形系（与 QingdaoStaticScene.LocalPosition 同式）。
    /// fixture 复用 telemetry-sample.json（真 WS 快照，provenance 见 TwinPipelineFixtureTests）。
    /// </summary>
    public class TwinLiveGeographyTests
    {
        const string k_FixtureRelPath = "Tests/Fixtures/telemetry-sample.json";

        static ColavTelemetry LoadRealFrame()
        {
            string path = Path.Combine(Application.dataPath, k_FixtureRelPath);
            Assert.That(File.Exists(path), Is.True, $"fixture 缺失：{path}");
            return ColavTelemetry.FromJson(File.ReadAllText(path));
        }

        [Test]
        public void EncInfoWithUtm51SelectsQingdao()
        {
            const string qingdao = "{\"ready\":true,\"origin_e\":247315.0,\"origin_n\":3982500.0,"
                + "\"width\":36000.0,\"height\":17500.0,\"utm_zone\":51,\"horizontal_crs\":\"EPSG:32651\","
                + "\"hemisphere\":\"north\",\"tile_url\":\"/api/enc_tile\",\"run_id\":\"abc\"}";
            Assert.That(TwinLiveGeographyProbe.IsQingdao(qingdao), Is.True);
        }

        [Test]
        public void NorwegianAndUnreadyEncInfoStayOnNorwayLandscape()
        {
            const string romsdal = "{\"ready\":true,\"utm_zone\":33,\"horizontal_crs\":\"EPSG:25833\"}";
            Assert.That(TwinLiveGeographyProbe.IsQingdao(romsdal), Is.False);
            const string unready = "{\"ready\":false,\"utm_zone\":51}";
            Assert.That(TwinLiveGeographyProbe.IsQingdao(unready), Is.False);
            Assert.That(TwinLiveGeographyProbe.IsQingdao(""), Is.False);
            Assert.That(TwinLiveGeographyProbe.IsQingdao(null), Is.False);
        }

        [Test]
        public void ExternalQingdaoAnchorPlacesShipInTerrainLocalFrame()
        {
            var frame = LoadRealFrame();
            var anchor = new TwinAnchor { EastM = 256315, NorthM = 3992326, LandingM = Vector2.zero };
            var own = TwinPose.ScenePosition(frame.truth[0], anchor);
            Assert.That(own.x, Is.EqualTo(frame.truth[0].east - 256315).Within(0.01f),
                "零登记平移锚：场景 x = E − manifest 中心东向");
            Assert.That(own.z, Is.EqualTo(frame.truth[0].north - 3992326).Within(0.01f),
                "场景 z = N − manifest 中心北向（QingdaoStaticScene.LocalPosition 同式）");
        }
    }
}
