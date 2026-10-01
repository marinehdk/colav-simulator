using NUnit.Framework;
using System.Runtime.Serialization;

namespace Sango.Tests
{
    public class DetectionRequiredFieldsTests
    {
        const string Valid = "{\"frame_seq\":0,\"frame_time_s\":0.0,\"source\":\"yolo-detector\",\"detections\":[{\"box_xyxy\":[1,2,30,40],\"class_id\":8,\"class_name\":\"boat\",\"confidence\":0.7}]}";

        [TestCase("\"frame_seq\":0,")]
        [TestCase("\"class_id\":8,")]
        [TestCase(",\"confidence\":0.7")]
        public void MissingRequiredFieldsAreRejectedRatherThanDefaulted(string field)
        {
            Assert.Throws<SerializationException>(() => DetectionResult.FromJsonStrict(Valid.Replace(field, "")));
        }

        [Test]
        public void ExplicitZeroValuesAndEmptyResultsRemainValid()
        {
            Assert.That(DetectionResult.FromJsonStrict(Valid).frame_seq, Is.Zero);
            var empty = DetectionResult.FromJsonStrict("{\"frame_seq\":0,\"frame_time_s\":0,\"source\":\"yolo-detector\",\"detections\":[]}");
            Assert.That(empty.detections, Is.Empty);
        }
    }
}
