using NUnit.Framework;
using Sango;
using Unity.RenderStreaming;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Tests
{
    public class TwinStreamQualityTests
    {
        [Test]
        public void CodecWithoutFormatParametersCannotBreakStateOrEvidenceSampling()
        {
            var type = TestReflection.FindAssemblyCSharpType("Sango.TwinStreamQuality");
            var codec = JsonUtility.FromJson<VideoCodecInfo>("{\"m_MimeType\":\"video/VP8\"}");
            Assert.That(type.GetMethod("EncoderName").Invoke(null, new object[] { codec }), Is.Null);
            var hardware = JsonUtility.FromJson<VideoCodecInfo>("{\"m_MimeType\":\"video/H264\",\"m_SdpFmtpLine\":\"implementation_name=NvCodec\"}");
            Assert.That(type.GetMethod("EncoderName").Invoke(null, new object[] { hardware }), Is.EqualTo("NvCodec"));
        }

        [Test]
        public void StreamCameraDisablesUnstableWaterReflectionsAndPreservesOtherOverrides()
        {
            var go = new GameObject("water reflection test");
            try
            {
                var camera = go.AddComponent<Camera>();
                var hd = go.AddComponent<HDAdditionalCameraData>();
                var settings = hd.renderingPathCustomFrameSettings;
                settings.SetEnabled(FrameSettingsField.TransparentSSR, true);
                settings.SetEnabled(FrameSettingsField.WaterDecals, true);
                hd.renderingPathCustomFrameSettings = settings;
                var mask = hd.renderingPathCustomFrameSettingsOverrideMask;
                mask.mask[(uint)FrameSettingsField.WaterDecals] = true;
                hd.renderingPathCustomFrameSettingsOverrideMask = mask;
                var sender = go.AddComponent<VideoStreamSender>();
                sender.sourceCamera = camera;

                var type = TestReflection.FindAssemblyCSharpType("Sango.TwinStreamQuality");
                System.Activator.CreateInstance(type, new object[] { sender });

                Assert.That(hd.customRenderingSettings, Is.True);
                Assert.That(hd.renderingPathCustomFrameSettingsOverrideMask.mask[(uint)FrameSettingsField.TransparentSSR], Is.True);
                Assert.That(hd.renderingPathCustomFrameSettings.IsEnabled(FrameSettingsField.TransparentSSR), Is.False);
                Assert.That(hd.renderingPathCustomFrameSettingsOverrideMask.mask[(uint)FrameSettingsField.WaterDecals], Is.True);
                Assert.That(hd.renderingPathCustomFrameSettings.IsEnabled(FrameSettingsField.WaterDecals), Is.True);
            }
            finally { Object.DestroyImmediate(go); }
        }

        [Test]
        public void ProfilesSetRealCaptureAndEncoderParametersAndRejectUnknownRequests()
        {
            var go = new GameObject("quality test");
            try
            {
                var camera = go.AddComponent<Camera>();
                var sender = go.AddComponent<VideoStreamSender>();
                sender.sourceCamera = camera;
                var type = TestReflection.FindAssemblyCSharpType("Sango.TwinStreamQuality");
                var quality = System.Activator.CreateInstance(type, new object[] { sender });
                Assert.That(sender.width, Is.EqualTo(1920));
                Assert.That(sender.height, Is.EqualTo(1080));
                Assert.That(sender.frameRate, Is.EqualTo(30));
                Assert.That(camera.GetComponent<HDAdditionalCameraData>().antialiasing,
                    Is.EqualTo(HDAdditionalCameraData.AntialiasingMode.SubpixelMorphologicalAntiAliasing));
                Assert.That(type.GetMethod("TryApply").Invoke(quality, new object[] { "1440p" }), Is.True);
                Assert.That(sender.width, Is.EqualTo(2560));
                Assert.That(sender.height, Is.EqualTo(1440));
                Assert.That(sender.minBitrate, Is.EqualTo(12000));
                Assert.That(sender.maxBitrate, Is.EqualTo(30000));
                Assert.That(type.GetMethod("TryApply").Invoke(quality, new object[] { "4k" }), Is.False);
                Assert.That(sender.width, Is.EqualTo(2560));
                Assert.That(type.GetMethod("TryApply").Invoke(quality, new object[] { "1080p" }), Is.True);
                Assert.That(sender.minBitrate, Is.EqualTo(8000));
                Assert.That(sender.maxBitrate, Is.EqualTo(16000));
            }
            finally { Object.DestroyImmediate(go); }
        }
    }
}
