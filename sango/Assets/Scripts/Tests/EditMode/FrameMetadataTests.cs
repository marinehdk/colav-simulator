using NUnit.Framework;
using Sango;

namespace Sango.Tests
{
    /// <summary>
    /// M3 缝钉子② 元数据组装测试（spec #86 Testing Decisions：FramePublisher encode-path
    /// 的 frame metadata assembly，无 socket）。钉死线上协议常量（frame-publisher-v1.md）：
    /// 主题 "sango.frame"、端点 tcp://127.0.0.1:5556、默认关闸。
    /// 期望值来自协议文档字面量，不回声实现。
    /// </summary>
    public class FrameMetadataTests
    {
        [Test]
        public void BuildMetadata_AssignsEveryField()
        {
            var m = FramePublisherCore.BuildMetadata(42, 12.345, 1920, 1080, 84213, "sango");
            Assert.That(m.frame_seq, Is.EqualTo(42));
            Assert.That(m.frame_time_s, Is.EqualTo(12.345).Within(1e-9));
            Assert.That(m.width, Is.EqualTo(1920));
            Assert.That(m.height, Is.EqualTo(1080));
            Assert.That(m.jpeg_bytes, Is.EqualTo(84213));
            Assert.That(m.source, Is.EqualTo("sango"));
        }

        [Test]
        public void MetadataToJson_RoundTripPreservesFields()
        {
            var m = FramePublisherCore.BuildMetadata(7, 0.5, 1280, 720, 51200, "sango");
            var back = FramePublisherCore.MetadataToJson(m);
            Assert.That(back, Does.Contain("\"frame_seq\":7"));
            Assert.That(back, Does.Contain("\"width\":1280"));
            Assert.That(back, Does.Contain("\"jpeg_bytes\":51200"));
        }

        [Test]
        public void SeamConsts_AreDocumentedDefaults()
        {
            Assert.That(SangoSeamConfig.PublisherEnabled, Is.False, "默认构建发布器必须关（验收故事 5）");
            Assert.That(SangoSeamConfig.PublisherEndpoint, Is.EqualTo("tcp://127.0.0.1:5556"));
            Assert.That(SangoSeamConfig.PublisherTopic, Is.EqualTo("sango.frame"));
            Assert.That(SangoSeamConfig.PublisherCliFlag, Is.EqualTo("--sango-publisher"));
        }
    }
}
