using System.Reflection;
using NUnit.Framework;

namespace Sango.Tests
{
    /// <summary>Imagery source parameterization (P1-B 2026-10-19; ArcGIS default
    /// 2026-10-21): env resolution and the WMTS request-shape invariants for both
    /// non-ion sources. Component wiring is plain field assignment on the Cesium
    /// overlay components and stays untested by design.</summary>
    public class QingdaoImagerySourceTests
    {
        System.Type Scene => TestReflection.FindAssemblyCSharpType("Sango.QingdaoStaticScene");

        object Resolve(string imagery, string token)
            => Scene.GetMethod("ResolveImagerySource", BindingFlags.Public | BindingFlags.Static)
                .Invoke(null, new object[] { imagery, token });

        string TileUrl(string token, double lon, double lat, int level)
            => (string)Scene.GetMethod("TiandituTileUrl", BindingFlags.Public | BindingFlags.Static)
                .Invoke(null, new object[] { token, lon, lat, level });

        string ArcgisUrl(double lon, double lat, int level)
            => (string)Scene.GetMethod("ArcgisTileUrl", BindingFlags.Public | BindingFlags.Static)
                .Invoke(null, new object[] { lon, lat, level });

        [Test]
        public void DefaultAndArcgisResolveToArcgisSinceBingTilesAreUnreachable()
        {
            // 2026-10-21: the Bing tile CDN (t*.virtualearth.net) behind ion asset 2
            // is unreachable from the a4000 deployment network, so the unset-env
            // default flipped from ion to ArcGIS World_Imagery.
            Assert.That(Resolve(null, null).ToString(), Is.EqualTo("Arcgis"), "no env = ArcGIS default");
            Assert.That(Resolve("", "").ToString(), Is.EqualTo("Arcgis"));
            Assert.That(Resolve("arcgis", null).ToString(), Is.EqualTo("Arcgis"));
            Assert.That(Resolve("ARCGIS", "secret").ToString(), Is.EqualTo("Arcgis"));
        }

        [Test]
        public void IonIsExplicitAndTiandituStillNeedsItsToken()
        {
            Assert.That(Resolve("ion", "secret").ToString(), Is.EqualTo("Ion"));
            Assert.That(Resolve("tianditu", "secret").ToString(), Is.EqualTo("Tianditu"));
            Assert.That(Resolve("TIANDITU", "secret").ToString(), Is.EqualTo("Tianditu"));
            Assert.That(Resolve("tianditu", null).ToString(), Is.EqualTo("Arcgis"),
                "token slot empty must not activate Tianditu");
            Assert.That(Resolve("tianditu", "  ").ToString(), Is.EqualTo("Arcgis"));
            Assert.That(Resolve("esri", "secret").ToString(), Is.EqualTo("Arcgis"),
                "unrecognized source falls back to ArcGIS");
        }

        [Test]
        public void TiandituBaseUrlCarriesTheTokenAsQueryParameter()
        {
            // The Unity WMTS component exposes no headers/query fields, so the
            // token rides the baseUrl query; cesium-native (pinned 1bca8021)
            // preserves it and switches '?'->'&' when building GetTile requests.
            string url = (string)Scene.GetMethod("TiandituBaseUrl", BindingFlags.Public | BindingFlags.Static)
                .Invoke(null, new object[] { "AB CD" });
            Assert.That(url, Is.EqualTo("https://t0.tianditu.gov.cn/img_w/wmts?tk=AB%20CD"));
        }

        [Test]
        public void ProbeUrlMirrorsTheCesiumNativeKvpGetTileRequest()
        {
            // Scene origin (terrain.json 120.2949968072661 E, 36.04500104524274 N)
            // -> Web Mercator z7 tile col 106, row 50 (hand-computed guard value).
            // Key order and casing match cesium-native's own KVP construction so
            // the probe exercises the same request shape the overlay issues.
            string url = TileUrl("k3", 120.2949968072661, 36.04500104524274, 7);
            Assert.That(url, Is.EqualTo(
                "https://t0.tianditu.gov.cn/img_w/wmts?tk=k3&request=GetTile&version=1.0.0&service=WMTS"
                + "&format=tiles&layer=img&style=default&tilematrixset=w&tilematrix=7&tilerow=50&tilecol=106"));
        }

        [Test]
        public void ArcgisProbeUrlMirrorsTheWmtsKvpGetTileRequest()
        {
            // Same origin and tile math as the Tianditu guard above; the ArcGIS
            // overlay fields (World_Imagery/GoogleMapsCompatible/image/jpeg) must
            // match the probe one-for-one.
            string url = ArcgisUrl(120.2949968072661, 36.04500104524274, 7);
            Assert.That(url, Is.EqualTo(
                "https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/WMTS"
                + "?service=WMTS&request=GetTile&version=1.0.0&layer=World_Imagery&style=default"
                + "&tilematrixset=GoogleMapsCompatible&format=image/jpeg&tilematrix=7&tilerow=50&tilecol=106"));
        }

        [Test]
        public void ProbeUrlClampsPoleLatitudesIntoTheMercatorRange()
        {
            Assert.That(TileUrl("k", 0, 89.9, 1), Does.Contain("tilerow=0"));
            Assert.That(TileUrl("k", 0, -89.9, 1), Does.Contain("tilerow=1"));
            Assert.That(ArcgisUrl(0, 89.9, 1), Does.Contain("tilerow=0"));
            Assert.That(ArcgisUrl(0, -89.9, 1), Does.Contain("tilerow=1"));
        }
    }
}
