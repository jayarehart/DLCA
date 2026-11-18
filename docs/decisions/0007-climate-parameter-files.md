# 0007. Climate parameter files, `ClimateParameters` and the selector

- **Status:** Proposed
- **Date:** 2026-11-18
- **Decided by:**

## Context

Record 0002 says DLCA ships AR5 and AR6 parameter sets as cited data, with AR6
as the default, and every result records the set it used. Until now the
parameters were uncited class attributes on `DLCAInputData`. Record 0005 says
the API takes and returns JSON-serialisable values. Issue #26 holds the
proposal and Jay's decisions D1–D6 (comment of 2026-11-18). The AR6 values come
from the IPCC-WG1/Chapter-7 code that generated Table 7.SM.7
([doi:10.5281/zenodo.5211357](https://doi.org/10.5281/zenodo.5211357)), because
ipcc.ch blocked downloading the PDFs.

## Decision

**Layout.** We will keep one JSON file per set in
`src/dlca/data/climate_parameters/` (`ar5.json`, `ar6.json`), loaded with
`importlib.resources`. Each value is a leaf `{value, unit, source, where}`,
optionally with `note`, `published` and `published_where`. `source` is a key
into the file's `sources`, and each source has a citation and a DOI. A test
enforces this. Indirect forcing has a `form`: `multiplicative` (AR5) or
`additive` (AR6). A `checks` block holds published values (as printed) for the
independent check. `schema_version` is 1.

**API.** `dlca.parameters.ClimateParameters` is a frozen, hashable dataclass of
plain floats and tuples, with `to_dict()` / `from_dict()`, `fingerprint()` (the
SHA-256 of its canonical JSON), `effective_radiative_efficiency(gas)` and
`fossil_ch4_co2_yield()`. `get_parameters(name="AR6")` loads a set (the name is
case-insensitive; unknown names raise `ValueError` listing the valid ones).
`available_parameter_sets()` lists them. Variants are made with
`dataclasses.replace()`: the name stays the same and the fingerprint changes.

**Science choices (Jay, issue #26):**

- D1: AR6 radiative efficiencies (REs) are unrounded, computed by
  `scripts/derive_ar6_radiative_efficiency.py`, with the rounded published
  values kept alongside. The script follows the IPCC code. That code evaluates
  the Meinshausen et al. (2020) formula re-referenced to the 2019 concentrations,
  for a +1 ppm (CO₂) or +1 ppb (CH₄, N₂O) step, then applies the rapid
  adjustments (+5%, −14%, +7%). This is the only method we found that
  reproduces the published AGWP₁₀₀(CO₂).
- D2: AR6 q₂ = 0.313998206372015, which reproduces AGTP₁₀₀(CO₂) = 3.95e-16.
- D3: neither set includes a carbon-cycle feedback (CCF) for non-CO₂ gases
  (`carbon_cycle_feedback: false`). So DLCA's AR6 CH₄ and N₂O metrics are lower
  than the AR6 headline values. Issue #33 covers adding it.
- D4: the fossil CH₄ → CO₂ yield is 0.5 mol/mol in AR5 (Cooper spreadsheet;
  Boucher et al. 2009, to confirm) and `null` in AR6 until it is confirmed from
  Table 7.15 or 7.SM. `fossil_ch4_co2_yield()` raises rather than guessing.
- D5: AR5 keeps the Cooper spreadsheet's CO₂ RE scale factor 0.99746898. It
  makes AGWP₁₀₀(CO₂) = 9.17e-14 and is labelled as not an IPCC value.
- D6: AR6 is the default.

## Alternatives considered

- **Keep parameters as Python constants.** Lost: no per-value unit or source,
  and not readable by a non-Python backend (0005).
- **AR6 REs as the slope of the 1750-referenced Meinshausen formula at 2019.**
  This is arguably the textbook definition. Lost: CO₂ RE 1.3877e-5 gives
  AGWP₁₀₀ = 9.30e-14, which does not reproduce Table 7.SM.7 (8.95e-14).
- **Rounded published REs (D1 option a).** Lost: AGWP₁₀₀(CO₂) is then 0.27% low.
- **A `Mapping` of molar masses and an `Indirect` sub-object** (as sketched in
  the proposal). Lost: flat float fields are simpler to hash, replace and
  serialise. (Rationale is a judgement call.)
- **CCF in M1 (D3 option b).** Lost: new physics in the engine, and it is not
  needed for the M1 checks.

## Consequences

- The engine (issues #27–#29) reads `ClimateParameters` instead of
  `DLCAInputData`. `DLCAInputData` stays until #31.
- Each `Result` (#31) records the set's name, `fingerprint()` and "no CCF".
- AR6 cannot be used for fossil CH₄ until the yield is confirmed (#30).
- Converting the yield to kg CO₂ per kg CH₄ is left to the engine. The old
  engine used nominal masses 44/16, not the set's molar masses (#27 decides).
- Changing any value is a `science` change and follows the deliberate lane.
- Not yet checked against the IPCC PDFs: the AR6 values, the exact table and
  section numbers in `where`, the AR5 CH₄ and N₂O AGWP₁₀₀ check values, and the
  AR6 SM's own citation.

## References

- Issue #26 (proposal and decisions D1–D6); issues #27–#31, #33; records 0002, 0005.
- Myhre et al. 2013, [doi:10.1017/CBO9781107415324.018](https://doi.org/10.1017/CBO9781107415324.018).
- Forster et al. 2021, [doi:10.1017/9781009157896.009](https://doi.org/10.1017/9781009157896.009).
- Meinshausen et al. 2020, [doi:10.5194/gmd-13-3571-2020](https://doi.org/10.5194/gmd-13-3571-2020).
- Joos et al. 2013, [doi:10.5194/acp-13-2793-2013](https://doi.org/10.5194/acp-13-2793-2013).
- Smith et al. 2021, IPCC-WG1/Chapter-7 code, [doi:10.5281/zenodo.5211357](https://doi.org/10.5281/zenodo.5211357).
