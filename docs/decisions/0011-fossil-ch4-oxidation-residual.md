# 0011. Fossil CH₄ oxidation keeps the perturbation lifetime; the AR6 gap is documented

- **Status:** Proposed
- **Date:** 2026-11-19
- **Decided by:**

## Context

Fossil CH₄ (`ch4_fossil`) is oxidised to CO₂. DLCA forms the CO₂ as the CH₄
pulse decays with its perturbation lifetime (11.8 yr in AR6), times the yield
(0.75 in AR6) and 44/16 (decision D1 on #27). This follows the closed form of
Boucher et al. (2009) (decision S2-A on #30). The IPCC-WG1/Chapter-7 file
`data_input/metrics/ch4_extra_response_functions.csv` (commit 2f948c8) gives
an AR6 oxidation term at GWP₁₀₀ of 1.908 × AGWP₁₀₀(CO₂). DLCA gives 1.866.
The gap depends on the horizon: IPCC/DLCA is 1.33 at H = 1 and 1.006 at
H = 500. The code that made the file is not in the IPCC repo, and the method
is not stated in AR6.

Issue #44 found the method by fitting. CH₄ that decays with a **9.70-yr**
lifetime, times 0.75 × 44.01/16.043, convolved with the file's own CO₂ AGWP
and AGTP on a 0.1-yr left-rectangle rule, reproduces both columns within the
file's 4-figure rounding (largest relative difference 5e-4, H = 0.5–500 yr).
The fitted yield is 1.000001 × 0.75 × 44.01/16.043. With 11.8 yr in the same
emulator, IPCC/emulator is 1.21 at H = 1, so the fit can tell the two
lifetimes apart.

## Decision

We will keep DLCA's method: the oxidised CO₂ forms as the CH₄ perturbation
decays (11.8 yr in AR6), with exact integration in `agwp()`/`agtp()` and whole
years in `burden()`. We will not adopt the IPCC file's 9.70-yr kernel or its
0.1-yr step, and we will not change the 44/16 ratio (D1). The gap to the IPCC
file is documented here. No code or parameter changes.

The gap at GWP₁₀₀ (oxidation term ÷ AGWP₁₀₀(CO₂)):

| Step | Value | Change |
|---|---|---|
| DLCA (11.8 yr, 44/16, exact) | 1.8657 | |
| Removal lifetime 9.7 yr | 1.9018 | +0.036 |
| Molar masses 44.01/16.043 | 1.8972 | −0.005 |
| 0.1-yr left-rectangle rule (Σ rate·dt = 1.0052, not 1) | 1.9079 | +0.011 |
| IPCC file | 1.9079 | |

## Alternatives considered

- **A. Adopt a 9.70-yr oxidation lifetime for AR6 only.** It would close the
  lifetime part (+0.036) and leave the step-error part (about +0.5% at
  H ≥ 20, +10% at H = 1). Lost because 9.7 yr has no stated source. It also
  breaks carbon consistency: for a pulse, the extra CH₄ destroyed is
  ΔC/τ_perturbation, so a 9.7-yr kernel forms CO₂ faster than the CH₄ in the
  same calculation decays, and for decades part of the carbon counts as both
  CH₄ and CO₂. The file's own CH₄ forcing (`RFCH4`) decays with 11.8 yr; at
  t = 10 yr the CH₄ left (0.429) plus the CH₄ oxidised (0.643) is 1.072 of
  the pulse, about 7% double counting. One arithmetic candidate, 1/(1/9.1 − 1/150) = 9.69 yr (total
  lifetime without a 150-yr soil sink), is a guess and was not verified.
- **C. Copy the IPCC scheme exactly (9.70 yr and the 0.1-yr rectangle).**
  It matches the file, but it builds in a numerical error. Record 0010 (C2)
  declined to do that for the carbon-cycle feedback. Lost.

## Consequences

- No output moves. AR5, the Cooper et al. (2020) reference match, and all
  non-fossil results are unaffected.
- The AR6 fossil CH₄ oxidation term stays below the IPCC file: 2.2% low at
  GWP₁₀₀, which is 0.14% of the fossil CH₄ GWP₁₀₀. The fossil CH₄ total is
  still above the file (DLCA 29.88, against 27.859 + 1.908 = 29.77 in the file
  and 29.8 in Table 7.15), because DLCA carries record 0010's exact CCF. At short horizons the oxidation term is up to 25%
  low (H = 1), where it is a small part of the fossil CH₄ total.
- The `ar6.json` description is not changed (the proposal had offered a note
  there). The parameter file feeds the fingerprint (record 0009, #46), and this
  record is the single place for the gap.
- Tests must not use the IPCC file's fossil-CO₂ columns as a tight target for
  DLCA.
- If the IPCC authors' method is found later and has a physical basis, a new
  record can supersede this one.

## Reproducing the fit

The IPCC CSVs are third-party data and are not committed. Read them in a
scratch directory with `python -I`. `t` is the `Time` column; `AGWP_CO2` is
`AGWPCO2` from `ch4_co2_response_functions.csv`. Compare with
`AGWP_fossilCO2` from `ch4_extra_response_functions.csv`; use `AGTPCO2` and
`AGTP_fossilCO2` for the AGTP check.

```python
Y = 0.75 * 44.01 / 16.043
rate = Y * np.exp(-t / tau) / tau  # sampled at the step start
ox = np.convolve(rate, AGWP_CO2)[: len(t)] * 0.1  # dt = 0.1 yr
```

## References

- Issue #44 (residual, proposal and fit, Jay's choice of option B); #33 and
  record 0010 (CCF, C2 and C8); decisions D1 (#27) and S2-A (#30).
- Smith, C. J., et al., 2021, IPCC-WG1/Chapter-7 code,
  [doi:10.5281/zenodo.5211357](https://doi.org/10.5281/zenodo.5211357),
  `data_input/metrics/ch4_extra_response_functions.csv` and
  `ch4_co2_response_functions.csv` at commit 2f948c8 (added in 2068673).
- Forster, P., et al., 2021, AR6 WG1 Chapter 7,
  [doi:10.1017/9781009157896.009](https://doi.org/10.1017/9781009157896.009),
  Table 7.15.
- Boucher, O., et al., 2009, Environ. Res. Lett., 4, 044007,
  [doi:10.1088/1748-9326/4/4/044007](https://doi.org/10.1088/1748-9326/4/4/044007).
