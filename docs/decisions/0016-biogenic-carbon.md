# 0016. Biogenic carbon: declared uptake, regrowth options, storage report

- **Status:** Proposed
- **Date:** 2026-11-20
- **Decided by:**
- **Supersedes:** 0013, in part: its "no biogenic field" rule (S7). Schema
  version 2 adds one.

## Context

Timber and other bio-based products take CO₂ from the air as they grow, hold
it, and release some of it at end of life. `assess()` takes uptake as negative
`co2` (record 0008). Record 0010 (C8) gives no carbon credit for non-fossil CH₄
in the engine, so the carbon a biogenic CH₄ release came from must be counted
once, in the inventory. The old model (`create_flux_mat`, removed in #61)
sampled a Cherubini et al. (2011) Gaussian at whole years and cut it at t < 0.
So it took up 97.9 % (rotation 50 and 80) to 101.4 % (rotation 2) of the
carbon, and gave B4 replacements no uptake. Issue #73 holds the proposal
(B1–B7) and Jay's decisions of 2026-11-20: B1–B7 accepted; B6 amended with a
`released_co2` field; the Gaussian window set to the whole right tail.

## Decision

We will take biogenic carbon as an optional `biogenic` field (schema version
2) on `Material` (kg CO₂ per declared unit), on `BuildingTotals` (kg CO₂) and
on each B4/B5 `Event`:

| Field | Meaning |
|---|---|
| `co2` ≥ 0 | Carbon held in the product, as kg CO₂ (carbon × 44.01/12.011) |
| `regrowth` | `"none"`, `"instant"` or `"gaussian"` |
| `rotation` | whole years ≥ 2, for `"gaussian"` only (required there) |
| `released_co2` ≥ 0, default 0 | Part of `co2` that the user's C1–C4 (or event) entries release as CO₂; reporting only |

- **Uptake** is `co2` × quantity as negative `co2`, starting in the product's
  year: year 0 for the material or building, or the event's year. It goes in
  its own timeline part, module `"biogenic-uptake"`, listed first in the
  breakdown (B7).
- `"instant"`: all in the product's year. `"none"`: no uptake.
- `"gaussian"`: μ = rotation/2, σ = μ/2. The share in year k ≥ 0 after the
  product's year is the normal pdf integrated over [k, k + 1), divided by its
  integral over [0, ∞). Uptake after the series end is cut off. `timeline()`
  warns (`BiogenicCarbonWarning`) when more than 1e-9 of an item's uptake is
  cut, and names the `years` that would keep it.
- **Release** is not written by the tool. Users enter it in C1–C4 (or in a B4
  event) as `co2` and non-fossil `ch4` (B3).
- **Counted once** (B5). The engine adds no credit for `ch4`. Uptake is the
  declared `co2` only, whatever form the carbon leaves in. `timeline()` warns
  when an item's `released_co2` plus its C1–C4 and event `ch4` × 44.01/16.043
  is more than its declared `co2`. That includes non-fossil `ch4` with no
  `biogenic` at all.
- **Storage** (B6, amended). `biogenic_balance()` and `BuildingResult.biogenic`
  report, per material, declared − `released_co2` − `ch4` × 44.01/16.043 as
  stored. Nothing is emitted for it.
- Schema version 1 files still load and may not use `biogenic`. Files with no
  biogenic carbon dump as before. `Timeline` and `BuildingResult` JSON go to
  version 2 and still read version 1.

## Alternatives considered

- **Uptake entered by hand as negative A1–A3 `co2`.** Lost: nothing can check
  the carbon balance (B1).
- **Gaussian over the rotation only, [0, rotation), rescaled to 1.** Lost:
  Jay chose the whole right tail (2026-11-20). It is closer to Cherubini's curve.
  The cost is that the balance is exact only for a long enough series, hence
  the warning.
- **Uptake before harvest** (growth before year 0). Lost: it needs negative
  years. That is a timing change (record 0014).
- **A credit of 44.01/16.043 kg CO₂ per kg of `ch4`.** Lost: it double-counts
  whenever the carbon content is also declared (B5).
- **Storage derived from C entries alone.** Lost: C `co2` mixes fossil fuel
  CO₂ with biogenic CO₂, so the split must come from the user
  (`released_co2`).

## Consequences

- B4 replacements of timber items get uptake only if their event carries
  `biogenic`. Nothing checks that it does.
- The over-release check sees only `released_co2` and non-fossil `ch4`. A user
  who puts biogenic CO₂ in C without saying so in `released_co2` gets a
  storage figure that is too high.
- Existing inputs with non-fossil `ch4` and no `biogenic` now warn, including
  `totals.json` and the Cooper reference cases. Their numbers do not change.
- `CO2_PER_CH4_CARBON` = 44.01/16.043 is used only for the report and the
  warning. Fossil CH₄ oxidation keeps 44/16 (decision D1 on #27).
- Long rotations started late in the series (for example a B4 event near RSP
  with rotation > H) lose some uptake unless `years` is raised.

## References

- Issue #73 (proposal B1–B7 and Jay's decisions); #74 (carbonation, next in
  M3).
- Records 0008, 0010 (C8), 0013 (partly superseded), 0014, 0015.
- Cherubini, F., Peters, G. P., Berntsen, T., Strømman, A. H., Hertwich, E.
  (2011). CO₂ emissions from biomass combustion for bioenergy: atmospheric
  decay and contribution to global warming. *GCB Bioenergy* 3(5), 413–426.
  doi:10.1111/j.1757-1707.2011.01102.x. Only the μ = r/2, σ = μ/2 form was
  taken (as in the old code); its GWP_bio tables were not checked.
- IPCC AR6 WG1, Table 7.SM.7 (AGWP100 and AGTP100 of CO₂), used by
  `tests/analytic/test_biogenic.py`.
