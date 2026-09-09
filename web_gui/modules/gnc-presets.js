// Preset identity and environment are resolved exclusively from backend bindings.
export function presetBinding(catalog, stackId) {
  for (const preset of catalog?.product_presets || []) {
    for (const [environment, id] of Object.entries(preset.variants)) {
      if (id === stackId) return { preset, environment };
    }
  }
  return null;
}

export function presetStackId(catalog, presetId, environment = 'off') {
  const preset = catalog?.product_presets?.find((item) => item.id === presetId);
  return preset?.variants?.[environment] ?? null;
}
