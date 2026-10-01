using NUnit.Framework;
using Sango;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Tests
{
    /// <summary>
    /// M9-1 WakeFoamRig 适配器 rig 构建 smoke EditMode 测试（先例 M4BAdapterTests /
    /// NavigationLights rig 测试）：立方船壳（根局部包围盒 x±1, y 0..1, z±2，模型单位=米）——
    /// ① rig 三件套构建（艏浪粒子×2 预算 72/侧、艉迹 ribbon 56 顶点拓扑、水线环 48 顶点）；
    /// ② High/Low 档驱动（发射率/强度观测口 + 整树开关）；③ High 档 decal 压制、Low 档
    /// 不碰 decal。适配器在 Assembly-CSharp，经反射驱动（TestReflection 先例；预算常量同经
    /// 反射读取——asmdef 不可见预定义程序集）；档位经 M8Quality.SetTier 静态记账
    /// （TearDown 复原 High，防跨测试泄漏）。
    /// </summary>
    public class WakeFoamRigSmokeTests
    {
        GameObject _ship;

        [SetUp]
        public void SetUp()
        {
            _ship = new GameObject("m9-test-ship");
            var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            Object.DestroyImmediate(cube.GetComponent<Collider>());
            cube.transform.SetParent(_ship.transform, false);
            cube.transform.localPosition = new Vector3(0f, 0.5f, 0f);
            cube.transform.localScale = new Vector3(2f, 1f, 4f); // 包围盒 x±1, y 0..1, z±2（LOA 4 局部）
        }

        [TearDown]
        public void TearDown()
        {
            M8Quality.SetTier(M8QualityTier.High); // 复原静态记账（防跨测试泄漏）
            if (_ship != null) Object.DestroyImmediate(_ship); // OnDestroy 连带清世界系 ribbon 树
        }

        Component AddRig()
        {
            var type = TestReflection.FindAssemblyCSharpType("Sango.WakeFoamRig");
            var rig = _ship.AddComponent(type);
            type.GetField("loaMeters").SetValue(rig, 12f);
            return rig;
        }

        // 预算常量经反射读（Assembly-CSharp 对测试 asmdef 不可见；const FieldInfo.GetValue(null) 合法）
        static int SprayBudget()
            => (int)TestReflection.FindAssemblyCSharpType("Sango.WakeFoamRig")
                .GetField("MaxSprayParticlesPerSide").GetValue(null);

        static float SprayMaxRate()
            => (float)TestReflection.FindAssemblyCSharpType("Sango.WakeFoamRig")
                .GetField("MaxSprayRatePerSide").GetValue(null);

        static void Invoke(object obj, string method, params object[] args)
            => obj.GetType().GetMethod(method).Invoke(obj, args);

        static void InvokePrivate(object obj, string method)
            => obj.GetType().GetMethod(method,
                   System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                .Invoke(obj, null); // BuildRig 私有（M4BAdapterTests 同款反射先例）

        static T ReadProp<T>(object obj, string name)
            => (T)obj.GetType().GetProperty(name).GetValue(obj);

        static void SetField(object obj, string name, object value)
            => obj.GetType().GetField(name).SetValue(obj, value);

        // ── ① rig 构建 smoke ────────────────────────────────────────────────────────
        [Test]
        public void BuildRig_CreatesSprayRibbonRing_WithBudgetTopology()
        {
            var rig = AddRig();
            InvokePrivate(rig, "BuildRig");
            Assert.That(ReadProp<bool>(rig, "RigBuilt"), Is.True, "rig 构建成功（立方船壳有 MeshFilter）");

            var root = _ship.transform.Find("WakeFoamRig");
            Assert.That(root, Is.Not.Null, "船子树存在");
            var sprays = root.GetComponentsInChildren<ParticleSystem>();
            Assert.That(sprays.Length, Is.EqualTo(2), "艏浪左右双臂（V 形）");
            foreach (var ps in sprays)
            {
                Assert.That(ps.main.maxParticles, Is.EqualTo(SprayBudget()),
                    "粒子预算 72/侧（头注 ≤144 总量锚）");
                Assert.That(ps.main.simulationSpace, Is.EqualTo(ParticleSystemSimulationSpace.World),
                    "世界系模拟：喷出后留水面不随船");
            }

            var ribbonGo = GameObject.Find("WakeFoam.World/WakeRibbon");
            Assert.That(ribbonGo, Is.Not.Null, "世界系 ribbon 树存在（挂场景根）");
            var ribbonMesh = ribbonGo.GetComponent<MeshFilter>().sharedMesh;
            Assert.That(ribbonMesh.vertexCount, Is.EqualTo(768), "128 samples × centre wash plus two Kelvin arms");
            Assert.That(ribbonMesh.triangles.Length, Is.EqualTo(2286), "three strips, 762 triangles total");
            Assert.That(ribbonGo.GetComponent<MeshRenderer>().enabled, Is.False, "首帧零强度不画");
            var foamMaterial = ribbonGo.GetComponent<MeshRenderer>().sharedMaterial;
            Assert.That(foamMaterial.GetShaderPassEnabled("DepthForwardOnly"), Is.False,
                "transparent foam must not write an opaque depth footprint over water");
            Assert.That(foamMaterial.GetFloat("_ZTestDepthEqualForOpaque"), Is.EqualTo(4f),
                "transparent HDRP forward must use LEqual, rather than opaque Equal");
            Assert.That(foamMaterial.GetFloat("_EnableBlendModePreserveSpecularLighting"), Is.Zero,
                "zero foam coverage must not leave an opaque specular plate");

            var ringGo = root.Find("WaterlineFoamRing");
            Assert.That(ringGo, Is.Not.Null, "水线泡沫环存在");
            var ringMesh = ringGo.GetComponent<MeshFilter>().sharedMesh;
            Assert.That(ringMesh.vertexCount, Is.EqualTo(48), "24 段 × 2 顶点");
            Assert.That(ringMesh.triangles.Length, Is.EqualTo(144), "24 段 × 2 三角 × 3 索引");
        }

        // ── ② 档位驱动：High 发射/强度，Low 整树休眠 ─────────────────────────────────
        [Test]
        public void ApplySpeed_HighTier_DrivesSprayRateAndRibbon()
        {
            var rig = AddRig();
            InvokePrivate(rig, "BuildRig");
            M8Quality.SetTier(M8QualityTier.High);

            Invoke(rig, "ApplySpeed", 0f); // 静止：门内恒零
            Assert.That(ReadProp<float>(rig, "LastSprayRatePerSide"), Is.EqualTo(0f), "静止零发射");
            Assert.That(ReadProp<float>(rig, "LastWakeIntensity01"), Is.EqualTo(0f), "静止零强度");

            Invoke(rig, "ApplySpeed", 5f); // 12 m 船巡航 5 m/s：双因子饱和
            Assert.That(ReadProp<float>(rig, "LastSprayRatePerSide"), Is.EqualTo(SprayMaxRate()).Within(1e-4f),
                "全强发射率 = 预算上限 55/s·侧");
            Assert.That(ReadProp<float>(rig, "LastWakeIntensity01"), Is.EqualTo(1f), "全强泡沫强度 1");
            Assert.That(ReadProp<float>(rig, "LastRingAlpha01"), Is.EqualTo(1f), "环 alpha 随速度爬坡");

            var ribbonGo = GameObject.Find("WakeFoam.World/WakeRibbon");
            Assert.That(ribbonGo.GetComponent<MeshRenderer>().enabled, Is.True, "强度 > 0 提交 ribbon draw");
            // 历史全填充于艉柱（未推进）：56 顶点横向展开 ±半宽（RibbonHalfWidthM(12)=0.75）
            var vertices = ribbonGo.GetComponent<MeshFilter>().sharedMesh.vertices;
            Assert.That(Vector3.Distance(vertices[0], vertices[1]), Is.EqualTo(1.5f).Within(1e-3f), "initial centre wash width");
        }

        [Test]
        public void MovingWakeHeadTracksSternAndArmsExpandBehindIt()
        {
            var rig = AddRig();
            InvokePrivate(rig, "BuildRig");
            for (int i = 0; i < 35; i++)
            {
                _ship.transform.position += Vector3.forward;
                Invoke(rig, "ApplySpeed", 5f);
            }
            _ship.transform.position += Vector3.forward * 0.25f;
            Invoke(rig, "ApplySpeed", 5f);
            var vertices = GameObject.Find("WakeFoam.World/WakeRibbon").GetComponent<MeshFilter>().sharedMesh.vertices;
            var head = (vertices[0] + vertices[1]) * 0.5f;
            Assert.That(head.z, Is.EqualTo(_ship.transform.position.z - 2f).Within(1e-3f), "sub-spacing motion must not leave head frozen");
            float nearWidth = Vector3.Distance((vertices[2] + vertices[3]) * 0.5f, (vertices[4] + vertices[5]) * 0.5f);
            int tail = vertices.Length - 6;
            float farWidth = Vector3.Distance((vertices[tail + 2] + vertices[tail + 3]) * 0.5f,
                (vertices[tail + 4] + vertices[tail + 5]) * 0.5f);
            Assert.That(farWidth, Is.GreaterThan(nearWidth + 10f), "diverging wave arms must widen along the actual trail");
        }

        [Test]
        public void ApplySpeed_LowTier_SleepsWholeRig()
        {
            var rig = AddRig();
            InvokePrivate(rig, "BuildRig");
            // GameObject.Find 不回 inactive 对象：休眠断言先抓引用后切档
            var rigRoot = _ship.transform.Find("WakeFoamRig").gameObject;
            var worldRoot = GameObject.Find("WakeFoam.World");
            Assert.That(worldRoot, Is.Not.Null, "构建后世界系 ribbon 树在场");
            M8Quality.SetTier(M8QualityTier.Low);

            Invoke(rig, "ApplySpeed", 5f); // 低档即便全速也休眠（decal 接管）
            Assert.That(ReadProp<float>(rig, "LastSprayRatePerSide"), Is.EqualTo(0f), "低档零发射");
            Assert.That(rigRoot.activeSelf, Is.False, "船子树整树休眠");
            Assert.That(worldRoot.activeSelf, Is.False, "世界系 ribbon 树休眠");
        }

        // ── ③ High 档 decal 压制 / Low 档不碰 decal ─────────────────────────────────
        [Test]
        public void ApplyDecalSuppression_HighForcesDecalsOff_LowUntouched()
        {
            var gateType = TestReflection.FindAssemblyCSharpType("Sango.BoatWaterDecals");
            var gate = _ship.AddComponent(gateType);
            var bowGo = new GameObject("bow");
            bowGo.transform.SetParent(_ship.transform, false);
            var wakeGo = new GameObject("wake");
            wakeGo.transform.SetParent(_ship.transform, false);
            gateType.GetField("bowDecal").SetValue(gate, bowGo.AddComponent<WaterDecal>());
            gateType.GetField("wakeDecal").SetValue(gate, wakeGo.AddComponent<WaterDecal>());
            var bow = bowGo.GetComponent<WaterDecal>();
            var wake = wakeGo.GetComponent<WaterDecal>();
            bow.enabled = true;
            wake.enabled = true; // 预置启用，验证压制会真关

            var rig = AddRig();
            InvokePrivate(rig, "BuildRig");
            SetField(rig, "decals", gate);

            M8Quality.SetTier(M8QualityTier.High);
            Invoke(rig, "ApplyDecalSuppression");
            Assert.That(bow.enabled, Is.False, "High 档艏波 decal 压制（粒子+ribbon 接管）");
            Assert.That(wake.enabled, Is.False, "High 档尾迹 decal 压制");

            M8Quality.SetTier(M8QualityTier.Low);
            bow.enabled = true;
            wake.enabled = true;
            Invoke(rig, "ApplyDecalSuppression");
            Assert.That(bow.enabled, Is.True, "Low 档不碰 decal（BoatWaterDecals 语义原样）");
            Assert.That(wake.enabled, Is.True, "Low 档不碰 decal（decalGate 契约不受影响）");
        }

        [Test]
        public void ApplyDecalSuppression_NullDecals_NoThrow()
        {
            var rig = AddRig();
            InvokePrivate(rig, "BuildRig"); // decals 未注入（构建器缺 decal 的防御路径）
            M8Quality.SetTier(M8QualityTier.High);
            Assert.DoesNotThrow(() => Invoke(rig, "ApplyDecalSuppression"));
        }
    }
}
