using UnityEngine;

namespace Sango
{
    /// <summary>
    /// 岛屿批量生成设置。Editor 场景构建器（M1SceneBootstrapper）与后续 GUI 共用。
    /// </summary>
    public struct IslandSettings
    {
        public int count;             // 岛屿数量
        public Vector2 sizeRange;     // 岛直径范围 m（每岛在区间内随机取值）
        public float maxHeight;       // 相对水线（y=0）的最大山高 m
        public int resolution;        // 单岛网格每边分段数（顶点数 (n+1)^2，n 钳制 8..256）
        public int seed;              // 确定性种子：同 seed 同结果
        public float clusterRadius;   // 岛群撒点半径 m（盘面均匀分布）
        public Material material;     // null 时用 HDRP/Lit 兜底材质（全岛共享一份实例，见 DefaultMaterial）
        public bool vertexColors;     // 写顶点色（沙/草/岩分带）。HDRP/Lit 默认不读顶点色，供未来自定义 shader 用
        public int noiseOctaves;       // 0 keeps the legacy profile; explicit experiment controls use 1..8.
        public float noiseScaleM, edgeDepthM, smoothA, smoothB, persistence, lacunarity;
        public Vector2 noiseOffset;
    }

    /// <summary>
    /// Perlin 程序化岛屿生成器（2D 噪声高度场 → 程序化 mesh，不用 Unity Terrain，PLAN §5 M1）。
    /// 提供 Editor 可直接调用的静态生成方法；材质由调用方传入。
    /// </summary>
    public static class PerlinIslandGenerator
    {
        /// <summary>
        /// 批量生成：返回 "Islands" 根节点，子节点 Island-N。撒点/尺寸/噪声域偏移全部由 seed 推导。
        /// </summary>
        public static GameObject GenerateIslands(IslandSettings s)
        {
            var rng = new Rng((uint)(s.seed == 0 ? 1 : s.seed)); // seed 0 是 xorshift 不动点，钳到 1
            var root = new GameObject("Islands");
            for (int i = 0; i < s.count; i++)
            {
                // 盘面均匀撒点：sqrt(U) 保证径向均匀
                float angle = rng.NextFloat() * Mathf.PI * 2f;
                float radius = Mathf.Sqrt(rng.NextFloat()) * Mathf.Max(1f, s.clusterRadius);
                float diameter = Mathf.Lerp(Mathf.Min(s.sizeRange.x, s.sizeRange.y), Mathf.Max(s.sizeRange.x, s.sizeRange.y), rng.NextFloat());

                var island = GenerateIsland(s.seed + i + 1, diameter, s.maxHeight, s.resolution, s.material, s.vertexColors);
                island.transform.SetParent(root.transform, false);
                island.transform.position = new Vector3(Mathf.Cos(angle) * radius, 0f, Mathf.Sin(angle) * radius);
                // 阶段2 提醒：千米级场景需浮点原点偏移（issue #79 坐标约定）；M1 场景仍在千米内，不做偏移。
            }
            return root;
        }

        /// <summary>
        /// 生成单岛：径向衰减 × fBm 高度场，边缘沉到水下保证自然岸线。同 seed 同 mesh。
        /// </summary>
        public static GameObject GenerateIsland(int seed, float diameter, float maxHeight, int resolution, Material material = null, bool vertexColors = false)
            => GenerateIsland(new IslandSettings { seed = seed, sizeRange = new Vector2(diameter, diameter),
                maxHeight = maxHeight, resolution = resolution, material = material, vertexColors = vertexColors });

        public static GameObject GenerateIsland(IslandSettings settings)
        {
            int n = Mathf.Clamp(settings.resolution, 8, 256);
            var mesh = BuildMesh(settings.seed, Mathf.Max(10f, settings.sizeRange.x), Mathf.Max(1f, settings.maxHeight), n,
                settings.vertexColors, settings);

            var go = new GameObject($"Island-{settings.seed}", typeof(MeshFilter), typeof(MeshRenderer));
            go.GetComponent<MeshFilter>().sharedMesh = mesh;
            go.GetComponent<MeshRenderer>().sharedMaterial = settings.material != null ? settings.material : DefaultMaterial();
            return go;
        }

        static Mesh BuildMesh(int seed, float diameter, float maxHeight, int n, bool vertexColors, IslandSettings settings)
        {
            // 选 Mathf.PerlinNoise 而非自写 value noise：官方文档保证同输入同输出（无内部随机状态），
            // 零分配且对岛屿地形足够；Perlin 无 seed 参数，确定性由 seed 推导的采样域偏移实现。
            var rng = new Rng((uint)seed);
            var offset = new Vector2(rng.NextFloat() * 1024f, rng.NextFloat() * 1024f);
            float noiseScale = 2.2f / diameter; // 整岛约 2 个噪声周期，特征尺度 ~ 半径级
            bool custom = settings.noiseOctaves > 0;
            if (custom) { offset += settings.noiseOffset; noiseScale = 1f / Mathf.Max(1f, settings.noiseScaleM); }

            int vertCount = (n + 1) * (n + 1);
            var verts = new Vector3[vertCount];
            var uvs = new Vector2[vertCount];
            var colors = vertexColors ? new Color[vertCount] : null;

            for (int j = 0; j <= n; j++)
            {
                for (int i = 0; i <= n; i++)
                {
                    int idx = j * (n + 1) + i;
                    float u = i / (float)n;
                    float v = j / (float)n;
                    float x = (u - 0.5f) * diameter;
                    float z = (v - 0.5f) * diameter;
                    float r = Mathf.Sqrt(x * x + z * z) / (diameter * 0.5f);

                    // 径向衰减：0.55R 起平滑降到边缘 0；边缘再压 -3m 保证岸线在网格内闭合
                    float falloff = 1f - Mathf.SmoothStep(0.55f, 1f, r);
                    if (custom)
                    {
                        float rx = Mathf.Pow(Mathf.Abs(x) / (diameter * 0.5f), Mathf.Max(1f, settings.smoothA));
                        float rz = Mathf.Pow(Mathf.Abs(z) / (diameter * 0.5f), Mathf.Max(1f, settings.smoothB));
                        float edge = Mathf.Pow(rx + rz, 1f / Mathf.Max(1f, (settings.smoothA + settings.smoothB) * 0.5f));
                        falloff = 1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.25f, 1f, edge));
                    }
                    var sample = offset + new Vector2(x, z) * noiseScale;
                    float h01 = custom ? FbmConfigured(sample, settings) : Fbm(sample);
                    float h = falloff * ((h01 - 0.35f) * maxHeight) - (1f - falloff) * (custom ? settings.edgeDepthM : 3f);

                    verts[idx] = new Vector3(x, h, z);
                    uvs[idx] = new Vector2(u, v);
                    if (vertexColors) colors[idx] = HeightColor(h, maxHeight);
                }
            }

            // 顺时针绕序（俯视），法线朝上：(vi, vi+n+1, vi+1) + (vi+1, vi+n+1, vi+n+2)
            var tris = new int[n * n * 6];
            int ti = 0;
            for (int j = 0; j < n; j++)
            {
                for (int i = 0; i < n; i++)
                {
                    int vi = j * (n + 1) + i;
                    tris[ti++] = vi;
                    tris[ti++] = vi + n + 1;
                    tris[ti++] = vi + 1;
                    tris[ti++] = vi + 1;
                    tris[ti++] = vi + n + 1;
                    tris[ti++] = vi + n + 2;
                }
            }

            var mesh = new Mesh
            {
                name = $"IslandMesh-{seed}",
                // 程序化 mesh 超 65k 顶点时 n>254 才需要 32 位索引；256 钳制下 257*257=66049，开 32 位兜底
                indexFormat = vertCount > 65000 ? UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16,
                vertices = verts,
                uv = uvs,
                triangles = tris,
            };
            if (vertexColors) mesh.colors = colors;
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            return mesh;
        }

        // 3 octave fBm，归一化到 0..1 近似
        static float Fbm(Vector2 p)
        {
            float f = 0f, amp = 1f, norm = 0f;
            for (int o = 0; o < 3; o++)
            {
                f += amp * Mathf.PerlinNoise(p.x, p.y);
                norm += amp;
                p *= 2.03f;
                p += new Vector2(17.31f, 9.7f);
                amp *= 0.5f;
            }
            return f / norm;
        }

        static float FbmConfigured(Vector2 p, IslandSettings settings)
        {
            float value = 0f, amplitude = 1f, total = 0f;
            for (int octave = 0; octave < Mathf.Clamp(settings.noiseOctaves, 1, 8); octave++)
            {
                value += amplitude * Mathf.PerlinNoise(p.x, p.y);
                total += amplitude;
                p = p * Mathf.Max(1f, settings.lacunarity) + new Vector2(17.31f, 9.7f);
                amplitude *= Mathf.Clamp(settings.persistence, 0.1f, 1f);
            }
            return value / total;
        }

        static Color HeightColor(float h, float maxHeight)
        {
            if (h < 0.3f) return new Color(0.76f, 0.70f, 0.50f); // 沙
            if (h < maxHeight * 0.5f) return new Color(0.32f, 0.45f, 0.25f); // 草
            return new Color(0.45f, 0.42f, 0.40f); // 岩
        }

        /// <summary>
        /// 默认材质兜底：HDRP/Lit（工程含 HDRP 17.3 必在）。返回共享实例，由调用方决定是否落成资产；
        /// Editor 场景保存时未落盘的材质会被内嵌进场景文件，可接受。
        /// Shader.Find 在 build 里需 shader 进入打包集合——M1 场景仅 Editor 内构建与运行，无此约束。
        /// </summary>
        public static Material DefaultMaterial()
        {
            var shader = Shader.Find("HDRP/Lit");
            if (shader == null) shader = Shader.Find("Standard"); // 理论兜底，HDRP 工程到不了
            return new Material(shader);
        }

        /// <summary>
        /// 自写 xorshift32：System.Random 的实现随 CLR 细节而异，自写保证同种子跨 Unity/平台版本完全一致。
        /// </summary>
        struct Rng
        {
            uint _s;
            public Rng(uint seed) { _s = seed == 0u ? 1u : seed; }
            public uint NextUInt() { _s ^= _s << 13; _s ^= _s >> 17; _s ^= _s << 5; return _s; }
            public float NextFloat() { return (NextUInt() >> 8) / 16777216f; } // [0,1)
        }
    }
}
