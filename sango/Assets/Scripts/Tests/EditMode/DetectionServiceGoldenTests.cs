using NUnit.Framework;
using Sango;

namespace Sango.Tests
{
    /// <summary>
    /// M9 Python 服务端样例 JSON golden 回注（detection-return-v1.md §5）：
    /// 样例即 tools/sango_detector_service.py 的线上输出形状（compact JSON，
    /// COCO boat=8 过滤 + class_name 映射 + 每帧恰一结果含权威空 detections）。
    /// 期望值来自 Python 侧事实（服务实现），C# 侧只验证契约可解析、字段逐项对齐。
    /// </summary>
    public class DetectionServiceGoldenTests
    {
        /// <summary>service 单检测帧输出形状（含序号/时刻/source 透传与 boat 框）。</summary>
        const string k_ServiceSample =
            "{\"frame_seq\":17,\"frame_time_s\":3.402,\"source\":\"yolo-detector\"," +
            "\"detections\":[{\"box_xyxy\":[120.5,88.0,412.25,301.5],\"class_id\":8,\"class_name\":\"boat\",\"confidence\":0.634}]}";

        /// <summary>service 无检测帧输出形状：detections=[] 是权威空结果（YOLO 没看到）。</summary>
        const string k_ServiceEmptySample =
            "{\"frame_seq\":18,\"frame_time_s\":3.602,\"source\":\"yolo-detector\",\"detections\":[]}";

        [Test]
        public void ServiceSample_ParsesToContractFields()
        {
            var r = DetectionResult.FromJson(k_ServiceSample);
            Assert.That(r, Is.Not.Null);
            Assert.That(r.frame_seq, Is.EqualTo(17));
            Assert.That(r.frame_time_s, Is.EqualTo(3.402).Within(1e-9));
            Assert.That(r.source, Is.EqualTo("yolo-detector"));
            Assert.That(r.detections, Has.Length.EqualTo(1));
            var box = r.detections[0];
            Assert.That(box.class_id, Is.EqualTo(8), "COCO boat=8 原样透传为 class_id");
            Assert.That(box.class_name, Is.EqualTo("boat"));
            Assert.That(box.confidence, Is.EqualTo(0.634f).Within(1e-5));
            Assert.That(box.box_xyxy, Has.Length.EqualTo(4));
            Assert.That(box.box_xyxy[0], Is.EqualTo(120.5f).Within(1e-3));
            Assert.That(box.box_xyxy[1], Is.EqualTo(88.0f).Within(1e-3));
            Assert.That(box.box_xyxy[2], Is.EqualTo(412.25f).Within(1e-3));
            Assert.That(box.box_xyxy[3], Is.EqualTo(301.5f).Within(1e-3));
        }

        [Test]
        public void ServiceEmptySample_ParsesToZeroDetections()
        {
            var r = DetectionResult.FromJson(k_ServiceEmptySample);
            Assert.That(r, Is.Not.Null);
            Assert.That(r.frame_seq, Is.EqualTo(18));
            Assert.That(r.detections, Is.Not.Null.And.Empty, "空数组必须保留（区别于缺字段的 null）");
        }

        [Test]
        public void ServiceSample_RoundTrip_Lossless()
        {
            var back = DetectionResult.FromJson(k_ServiceSample).ToJson();
            var twice = DetectionResult.FromJson(back).ToJson();
            Assert.That(twice, Is.EqualTo(back), "Python JSON → C# → 再序列化 → 再解析逐位无损");
        }

        [Test]
        public void ServiceSample_WithUnknownExtraField_Tolerated()
        {
            // Python 侧只加不减的演进（如未来加 infer_ms）必须不破坏 Unity 解析
            const string withExtra = "{\"frame_seq\":1,\"frame_time_s\":0.5,\"source\":\"yolo-detector\"," +
                                     "\"infer_ms\":42.1,\"detections\":[]}";
            var r = DetectionResult.FromJson(withExtra);
            Assert.That(r.frame_seq, Is.EqualTo(1));
            Assert.That(r.detections, Is.Empty);
        }

        [Test]
        public void FreshEmptyServiceResult_TakesLivePath_RendersNothing()
        {
            // 契约语义钉死：新鲜空结果 = live 接管（渲染零框），绝不回退真值
            var r = DetectionResult.FromJson(k_ServiceEmptySample);
            double nowS = r.frame_time_s + 0.1;
            Assert.That(DetectionFreshness.PreferLiveOverGroundTruth(r, nowS), Is.True);
            Assert.That(r.detections, Is.Empty);
        }

        [Test]
        public void StaleServiceResult_FallsBackToGroundTruth()
        {
            var r = DetectionResult.FromJson(k_ServiceSample);
            Assert.That(
                DetectionFreshness.PreferLiveOverGroundTruth(r, r.frame_time_s + DetectionFreshness.MaxAgeS + 0.01),
                Is.False, "age 超 0.5s 窗 → 回退 ground-truth");
        }
    }
}
