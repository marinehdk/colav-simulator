using System.Linq;
using NUnit.Framework;

namespace Sango.Tests
{
    public class FramePublisherOrientationTests
    {
        [TestCase(2)]
        [TestCase(3)]
        public void RowNormalizationPreservesColumnsChannelsAndOddMiddleRow(int height)
        {
            const int rowBytes = 8; // Two distinguishable RGBA pixels per row.
            var original = Enumerable.Range(0, rowBytes * height).Select(i => (byte)i).ToArray();
            var pixels = (byte[])original.Clone();
            FramePublisherCore.FlipRgbaRows(pixels, rowBytes, height, new byte[rowBytes]);
            for (int row = 0; row < height; row++)
                for (int columnByte = 0; columnByte < rowBytes; columnByte++)
                    Assert.That(pixels[row * rowBytes + columnByte],
                        Is.EqualTo(original[(height - row - 1) * rowBytes + columnByte]));
        }
    }
}
