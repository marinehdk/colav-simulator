using System.Collections.Generic;
using UnityEngine;

namespace Sango.Vessels.Mast
{
    /// <summary>
    /// P3-S2 thermal tagging (spec #90; IR=温度 tag 简化模型，plan裁决 3): walks
    /// the registered vessel renderers and drives each material's base color
    /// toward its <see cref="IrTemperatureTier"/> grayscale while the IR mode is
    /// active, restoring the original on EO. Combined with the
    /// <see cref="IrViewPass"/> white-hot ramp the tagged vessels read as hot
    /// targets against the cold sea/sky background (night theme is the canonical
    /// IR scene). Registration happens from TwinSessionDriver slot wiring —
    /// twin slots are ephemeral (rebuilt per attach), so registrations are
    /// keyed by renderer and dropped when the renderer dies.
    /// Scope note: material mutation is process-wide, but the tag applies only
    /// while sensor_mode=ir is active (a twin-bridge control state); Demo-mode
    /// *rendering code paths* are untouched and EO restores the exact colors.
    /// </summary>
    public static class ThermalTagApplier
    {
        private static readonly List<Renderer> Registered = new List<Renderer>();
        private static readonly Dictionary<Renderer, List<Color>> Originals = new Dictionary<Renderer, List<Color>>();
        private static readonly int BaseColorId = Shader.PropertyToID("_BaseColor");
        private static readonly int EmissiveColorId = Shader.PropertyToID("_EmissiveColor");
        private static readonly int EmissiveIntensityId = Shader.PropertyToID("_EmissiveIntensity");

        /// <summary>Registers a vessel root (idempotent): every renderer under it is tagged.</summary>
        public static void Register(GameObject vesselRoot)
        {
            if (vesselRoot == null) return;
            foreach (var renderer in vesselRoot.GetComponentsInChildren<Renderer>(true))
            {
                if (renderer == null || Registered.Contains(renderer)) continue;
                Registered.Add(renderer);
            }
            if (Requested) Apply();
        }

        /// <summary>True while the IR tag is applied (TwinBridgeService sensor_mode=ir).</summary>
        public static bool Requested { get; private set; }

        /// <summary>Registered renderer count (diagnostics/tests).</summary>
        public static int RegisteredCount => Registered.Count;

        /// <summary>Applies the tier grays (idempotent; originals snapshotted once).</summary>
        public static void Apply()
        {
            Requested = true;
            PruneDead();
            foreach (var renderer in Registered)
            {
                if (renderer == null) continue;
                var materials = renderer.sharedMaterials;
                if (materials == null) continue;
                if (!Originals.TryGetValue(renderer, out var stored) || stored == null || stored.Count != materials.Length)
                {
                    var colors = new List<Color>(materials.Length);
                    foreach (var material in materials) colors.Add(material != null && material.HasProperty(BaseColorId) ? material.GetColor(BaseColorId) : Color.white);
                    Originals[renderer] = colors;
                }
                ApplyTierColors(renderer, materials, irOn: true);
            }
        }

        /// <summary>Restores the snapshotted colors (sensor_mode back to eo/lidar).</summary>
        public static void Revert()
        {
            Requested = false;
            PruneDead();
            foreach (var pair in Originals)
            {
                var renderer = pair.Key;
                if (renderer == null) continue;
                var materials = renderer.sharedMaterials;
                if (materials == null || pair.Value == null || pair.Value.Count != materials.Length) continue;
                for (int i = 0; i < materials.Length; i++)
                {
                    var material = materials[i];
                    if (material == null || !material.HasProperty(BaseColorId)) continue;
                    material.SetColor(BaseColorId, pair.Value[i]);
                }
            }
            Originals.Clear();
        }

        /// <summary>EditMode-visible pure step: tier gray per material slot (stored originals feed Revert).</summary>
        public static void ApplyTierColors(Renderer renderer, Material[] materials, bool irOn)
        {
            for (int i = 0; i < materials.Length; i++)
            {
                var material = materials[i];
                if (material == null || !material.HasProperty(BaseColorId)) continue;
                if (irOn)
                {
                    var tier = IrTemperature.TierForMaterial(MaterialKey(renderer, material, i));
                    float gray = IrTemperature.TierGray(tier);
                    var color = new Color(gray, gray, gray, 1f);
                    material.SetColor(BaseColorId, color);
                    // Emission nudge: hot tiers glow through night lighting (HDRP Lit reads
                    // _EmissiveColor/_EmissiveIntensity; harmless no-op on shaders without them).
                    if (material.HasProperty(EmissiveColorId))
                    {
                        material.SetColor(EmissiveColorId, color * Mathf.LinearToGammaSpace(gray) * 0.5f);
                        if (material.HasProperty(EmissiveIntensityId)) material.SetFloat(EmissiveIntensityId, gray * 2f);
                    }
                }
                else
                {
                    material.SetColor(BaseColorId, Color.white);
                }
            }
        }

        private static string MaterialKey(Renderer renderer, Material material, int slot)
            => $"{renderer.name}.{material.name}#{slot}";

        private static void PruneDead()
        {
            for (int i = Registered.Count - 1; i >= 0; i--)
                if (Registered[i] == null) Registered.RemoveAt(i);
        }
    }
}
