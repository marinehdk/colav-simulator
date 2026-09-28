using NUnit.Framework;
using Sango;

namespace Sango.Tests
{
    /// <summary>
    /// M3 缝钉子④回环测试（spec #86 Testing Decisions：DetectionResult loopback，
    /// serialize→deserialize→serialize 无损）。钉死 detection-result-v1.md 的 JSON 形状：
    /// 框 = box_xyxy 像素数组（左上原点、y 向下）+ class_id/class_name/confidence。
    /// 期望值来自独立事实（契约文档字面量），不回声实现。
    /// </summary>
    public class DetectionResultRoundTripTests
    {
        /// <summary>detection-result-v1.md §2 的契约示例字面量（冻结）。</summary>
        const string k_ContractSample =
            "{\"frame_seq\":41,\"frame_time_s\":12.5,\"source\":\"yolo-a4000\"," +
            "\"detections\":[{\"box_xyxy\":[100.0,120.0,340.0,260.0],\"class_id\":1,\"class_name\":\"ship\",\"confidence\":0.87}]}";

        static DetectionResult.Box SampleBox()
        {
            return new DetectionResult.Box
            {
                box_xyxy = new[] { 100f, 120f, 340f, 260f },
                class_id = 1,
                class_name = "ship",
                confidence = 0.87f,
            };
        }

        [Test]
        public void ContractSample_DeserializesToDocumentedFields()
        {
            var r = DetectionResult.FromJson(k_ContractSample);
            Assert.That(r, Is.Not.Null);
            Assert.That(r.frame_seq, Is.EqualTo(41));
            Assert.That(r.frame_time_s, Is.EqualTo(12.5).Within(1e-9));
            Assert.That(r.source, Is.EqualTo("yolo-a4000"));
            Assert.That(r.detections, Has.Length.EqualTo(1));
            Assert.That(r.detections[0].box_xyxy, Has.Length.EqualTo(4));
            Assert.That(r.detections[0].box_xyxy[0], Is.EqualTo(100f).Within(1e-4));
            Assert.That(r.detections[0].box_xyxy[1], Is.EqualTo(120f).Within(1e-4));
            Assert.That(r.detections[0].box_xyxy[2], Is.EqualTo(340f).Within(1e-4));
            Assert.That(r.detections[0].box_xyxy[3], Is.EqualTo(260f).Within(1e-4));
            Assert.That(r.detections[0].class_id, Is.EqualTo(1));
            Assert.That(r.detections[0].class_name, Is.EqualTo("ship"));
            Assert.That(r.detections[0].confidence, Is.EqualTo(0.87f).Within(1e-5));
        }

        [Test]
        public void Loopback_SerializeDeserializeSerialize_StringStable()
        {
            var original = new DetectionResult
            {
                frame_seq = 7,
                frame_time_s = 3.25,
                source = "ground-truth",
                detections = new[] { SampleBox() },
            };
            var once = original.ToJson();
            var back = DetectionResult.FromJson(once);
            var twice = back.ToJson();
            Assert.That(twice, Is.EqualTo(once), "serialize→deserialize→serialize 字符串逐位无损");
        }

        [Test]
        public void Loopback_MultiBox_OrderAndValuesPreserved()
        {
            var original = new DetectionResult
            {
                frame_seq = 2,
                frame_time_s = 0.5,
                source = "ground-truth",
                detections = new[]
                {
                    SampleBox(),
                    new DetectionResult.Box
                    {
                        box_xyxy = new[] { 0f, 0f, 1920f, 1080f },
                        class_id = 0,
                        class_name = "buoy",
                        confidence = 1f,
                    },
                },
            };
            var back = DetectionResult.FromJson(original.ToJson());
            Assert.That(back.detections, Has.Length.EqualTo(2));
            Assert.That(back.detections[0].class_name, Is.EqualTo("ship"), "框顺序保持");
            Assert.That(back.detections[1].class_name, Is.EqualTo("buoy"));
            Assert.That(back.detections[1].box_xyxy[2], Is.EqualTo(1920f).Within(1e-3));
            Assert.That(back.detections[1].box_xyxy[3], Is.EqualTo(1080f).Within(1e-3));
            Assert.That(back.detections[1].confidence, Is.EqualTo(1f).Within(1e-6));
        }

        [Test]
        public void FromJson_MissingFieldsTolerated_EmptyDocument()
        {
            var r = DetectionResult.FromJson("{}");
            Assert.That(r, Is.Not.Null, "空文档可反序列化（阶段2 早期帧允许无 detections 键）");
            Assert.That(r.frame_seq, Is.EqualTo(0));
            Assert.That(r.detections, Is.Null.Or.Empty);
        }
    }
}
