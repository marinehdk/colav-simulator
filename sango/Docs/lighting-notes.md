# Lighting notes — night navigation lights & water reflection (M2-D, spec #83)

## Day/night threshold

`NavigationLightsCore.IsLightsOn(timeOfDayHours)` mirrors `WeatherController.ApplySun`'s
elevation formula exactly (`60·cos(π(h−12)/12)`): lights are **on when elevation ≤ 0**,
i.e. h ∈ [0, 6] ∪ [18, 24] on the existing [0, 24] slider. Rationale: at elevation 0
(6 h / 18 h) direct sun contributes nothing (ApplySun intensity is at its 0.1 lux floor),
so the horizon boundary belongs to the night side; the 17.5 h dusk preset (sun +7.8°) is
still pre-sunset, so lights stay off there (COLREGs: lights sunset→sunrise).
**If you change ApplySun's elevation model, change the threshold with it** (both spots
are commented as coupled).

## Water reflection path: FALLBACK (R2 settled)

R2 asked whether HDRP Water's specular response to **local point lights** reads as a
light path at demo camera distances. Measured (batchmode render-request readback, night,
B0 calm, 300/600/200 lm lights): the specular response **exists** (water near the ship
brightens +118%…+247% with lights on, near-field strongest) but is **not readable** —
absolute luminance ~0.003–0.005 linear, and the ON/OFF delta is only 1.5–1.8× the frame's
global drift noise (exposure adaptation between frames; measured via a far control patch).
Per the spec protocol ("take the fallback without ceremony"), ships use **per-light fake
reflection streaks**:

- One horizontal quad per light, additive blend (`HDRP/Unlit`, transparent surface +
  `_BLEND_MODE_ADD`, SrcAlpha×color + dst, α = 0.55, HDR color ×3), hovering 0.25 m
  above the water.
- Every frame the quad's long axis aims at the camera and it extends from the light
  toward the viewer (mirror-image geometry); it rides the hull anchor (heave included).
- Size: length = clamp(0.45·LOA + 3 m, 4, 30), width = 4× lamp size
  (Small fishing ≈ 4.7×1.9 m, Medium liner ≈ 12.6×7.2 m).
- Verified numerically: same-frame contrast vs adjacent open water = **1.95×** mean
  (5× max) — the streak is the brightest feature in the night frame near the ship.
- Day state: the whole rig tree is deactivated, so streaks, lamp quads and point lights
  all cost and emit nothing at noon (zero glow by construction, not by tuning).

If a future pipeline raises the real specular response (e.g. exposure override tuning or
brighter lights), the probe is kept for re-measurement:
`Sango/M2D/Run Water Reflection Spike` (batchmode numeric report → /tmp/sango-m2d-spike.json).

## Light set (per ship, built at runtime from hull bounds)

| Light | Color | Anchor (local, bow +Z) | Point light | Lamp |
|---|---|---|---|---|
| Port sidelight | RED (1, 0.12, 0.08) | −X extreme, deck, forward 1/3 | 50 m, 300 lm | crossed quads 0.03·LOA, ×12 nits |
| Starboard sidelight | GREEN (0.15, 1, 0.25) | +X extreme (mirror) | 50 m, 300 lm | same |
| Masthead | WHITE (1, 0.98, 0.92) | centerline, hull top, +0.4·half-length | 80 m, 600 lm | same |
| Stern | WHITE | centerline, deck, aft extreme | 50 m, 200 lm | same |

Anchors come from the pure function `NavigationLightsCore.DeriveAnchors(Bounds)` — no
per-model hand placement, works for any future catalog entry. Roots of catalog prefabs
carry a baked non-uniform scale (local units ≠ metres); anything sized in metres must be
divided by `lossyScale` before use as a local scale (hit twice now — see M2-B evidence).

No new controls: on/off follows the existing **T** time-cycle hotkey and the time slider.
