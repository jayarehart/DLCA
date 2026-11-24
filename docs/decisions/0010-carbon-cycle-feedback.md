# 0010. Carbon-cycle feedback for CH₄ and N₂O

- **Status:** Accepted
- **Date:** 2026-11-19
- **Decided by:** Jay Arehart, 2026-11-23 (accepted with a note in C7, #95)

## Context

When CH₄ or N₂O warm the climate, the land and ocean sinks take up less carbon,
so extra CO₂ stays in the air: the carbon-cycle feedback (CCF). The Joos et al.
(2013) CO₂ response already contains it for CO₂, so metrics without CCF for the
other gases are inconsistent (Gasser et al. 2017). AR6's headline CH₄ and N₂O
metrics include it. Record 0007 D3 left it out of M1. Issue #33 holds the
proposal and Jay's decisions C1–C8 (accepted as recommended, 2026-11-19), and
the check of the parameters against Gasser et al. (2017).

The IPCC Chapter-7 code computes the CCF by a 0.1-year rectangle-rule
convolution. Its response function is a δ term minus exponentials that
integrate to zero, so the two parts nearly cancel and the step error does not.
At dt = 0.1 the CCF part of CH₄ AGWP₁₀₀ is 9.6% low and of AGTP₁₀₀ 30% low.
Run at smaller steps, the code converges to the exact closed form (agreement
within 5e-6 after Richardson extrapolation). The printed Table 7.SM.7 values
(CH₄ GWP₁₀₀ 27.9, N₂O 273) come from dt = 0.1.

## Decision

We will add the AR6 CCF of Gasser et al. (2017), computed exactly:

- **Sets (C1).** AR6 uses Gasser et al. (2017), Table 1 "Mean" row. AR5 has
  no CCF: `carbon_cycle_feedback=True` on AR5 raises `ValueError`.
- **Target (C2).** The exact value, not the IPCC code's dt = 0.1 value. AR6
  CH₄ GWP₁₀₀ is 28.02 and N₂O 274.4. The independent check is the IPCC code
  Richardson-extrapolated to dt → 0 (the `*_ccf` checks in `ar6.json`).
  Table 7.SM.7 is kept as an `xfail(strict=True)` test.
- **Where (C3).** At the burden step. `burden()` computes the CH₄ + N₂O
  temperature, the carbon the sinks release, and adds that CO₂ to the CO₂
  emissions as `Burden.ccf_co2`. Only CH₄ and N₂O drive it; CO₂ (including
  CO₂ from fossil CH₄ and the CCF CO₂) does not, and there is no iteration.
- **Whole years (C4).** The carbon released up to year k is
  `C[k] = γ Σᵢ wᵢ Sᵢ[k]`, with `Sᵢ` the temperature filtered by `exp(−t/τᵢ)`
  by the trapezoid rule over each year; `C[k] − C[k−1]` is added to year k.
  Sliding GWI and GTP count CCF CO₂ as CO₂ emitted in the year it forms.
  `agwp()`, `agtp()` and the static factors use the exact closed form.
- **Parameters (C5).** γ = 3.015 GtC yr⁻¹ K⁻¹ (stored as 3.015e12 kg C),
  weights (0.6368, 0.3322, 0.0310), time constants (2.376, 30.14, 490.1) yr,
  M_C = 12.0 g mol⁻¹ (IPCC code). DLCA's own CO₂ IRF is used inside the CCF.
- **Switch and default (C6).** The existing
  `ClimateParameters.carbon_cycle_feedback`: AR6 ships `true`, AR5 `false`.
  The switch and values are in `fingerprint()`, so the #37 guard rejects a
  burden made with CCF on and used with CCF off.
- **Reporting (C7).** No new `Result` field; `Burden.to_dict()` gains
  `ccf_co2`; the `Result` schema version goes to 3 (now 4, see
  0009).
- **Biogenic carbon (C8).** `ch4` stays CH₄ with no carbon credit. AR6
  Table 7.15's non-fossil value subtracts 44.01/16.043 kg CO₂ per kg CH₄ (the
  CO₂ the biogenic carbon came from); in DLCA that belongs in the inventory.

## Alternatives considered

- **Copy the IPCC 0.1-year scheme (C2 b).** Matches the printed tables, but
  builds in a step-dependent 10–30% error in the CCF term, and cannot be done
  cleanly in an annual engine. Lost.
- **CCF at the forcing step (C3).** Leaves the extra CO₂ out of `Burden` and
  of `temperature()`, which takes a `Burden` (#29 T1). Lost.
- **AR5 with Gasser (C1 c), or Collins et al. 2013 (C1 b).** Gasser with AR5
  parameters gives CH₄ GWP₁₀₀ 30.9, not AR5's 34, so it would not be an AR5
  value; Collins was not examined. Left for a later issue if wanted.
- **CCF off by default (C6 b).** No M1 number moves, but the default AR6 set
  stays below the AR6 headline values and inconsistent with its CO₂ IRF. Lost.
- **A `ccf=` argument on the functions.** A second thing to keep in step
  between `burden()` and `forcing()` that the fingerprint would not cover. Lost.

## Consequences

- Default AR6 results move: CH₄ GWP₁₀₀ 26.37 → 28.02 (+6.3%), N₂O GWP₁₀₀
  260.6 → 274.4 (+5.3%), CH₄ GTP₁₀₀ 4.90 → 5.58. CO₂ and AR5 do not move.
  With CCF off, every output is bit-identical to M1.
- DLCA does not reproduce Table 7.SM.7 or Table 7.15's CH₄ rows within their
  rounding. The fossil row also has an unexplained +0.042 oxidation residual
  (#44).
- For a pulse, the whole-year dynamic GWI and GTP differ from the closed form
  by up to 8.2e-4 (N₂O GWP₂₀), as the fossil oxidation already does (S2-A).
- The CCF response was fitted for a +0.2 °C step on a present-day background
  and is not linear in step size (Gasser et al. 2017, Fig. 3). Uncertainty
  (their ±1 SD rows, γ 4.264 and 1.964) is out of scope.
- AR6 tests that pin M1 values for a single gas use the explicit no-CCF
  variant.

## References

- Issue #33 (proposal, Gasser check, decisions C1–C8, plan after #37); #37 and
  record 0009; #44; records 0007 (D3 superseded), 0008.
- Gasser, T., et al., 2017, Earth Syst. Dynam., 8, 235–253,
  [doi:10.5194/esd-8-235-2017](https://doi.org/10.5194/esd-8-235-2017).
- Smith, C. J., et al., 2021, IPCC-WG1/Chapter-7 code,
  [doi:10.5281/zenodo.5211357](https://doi.org/10.5281/zenodo.5211357),
  `src/ar6/metrics/gasser.py` at commit 2f948c8.
- Forster, P., et al., 2021, AR6 WG1 Chapter 7,
  [doi:10.1017/9781009157896.009](https://doi.org/10.1017/9781009157896.009),
  Tables 7.15 and 7.SM.7.
