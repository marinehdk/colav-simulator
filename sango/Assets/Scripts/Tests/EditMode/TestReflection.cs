using NUnit.Framework;

namespace Sango.Tests
{
    /// <summary>
    /// 测试程序集共享反射小件：被测类型在 Assembly-CSharp（Assets/Scripts/Runtime/ 无
    /// asmdef 覆盖，asmdef 无法引用预定义程序集），EditMode 经此解析。
    /// WeatherFogOverrideTests / WaterDecalSpeedGateTests 两处逐字重复的收编（W1 code-review F1）。
    /// </summary>
    internal static class TestReflection
    {
        public static System.Type FindAssemblyCSharpType(string fullName)
        {
            foreach (var asm in System.AppDomain.CurrentDomain.GetAssemblies())
            {
                if (asm.GetName().Name != "Assembly-CSharp") continue;
                var t = asm.GetType(fullName);
                Assert.That(t, Is.Not.Null, $"Assembly-CSharp 缺类型 {fullName}");
                return t;
            }
            Assert.Fail("Assembly-CSharp 程序集未加载");
            return null;
        }
    }
}
