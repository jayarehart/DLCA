# Reference tests: the Cooper et al. (2020) spreadsheet

These tests run `dlca.engine` on seven emission cases and compare the results,
year by year, with the *temporal climate impacts* spreadsheet by Sam Cooper.
`dlca.engine` is a Python port of that spreadsheet (the column names match),
so the spreadsheet is an independent check **of the port**, not of the
physics. Checks against published IPCC values come in M1.

## Source and attribution

The reference values come from the spreadsheet published as supplementary
material `mmc2.xlsx` to:

> Cooper, S. J. G., Green, R., Hattam, L., Röder, M., Welfle, A., & McManus, M.
> (2020). Exploring temporal aspects of climate-change effects due to
> bioenergy. *Biomass and Bioenergy*, 142, 105778.
> https://doi.org/10.1016/j.biombioe.2020.105778

- **Spreadsheet:** "temporal climate impacts", **version 5 (01/10/2020)**, by
  Sam Cooper (University of Bath), with contributions from Laura Hattam, Will
  Hawkins and Marcelle McManus. Supported by the Supergen Bioenergy Hub (UKRI
  grant EP/S000771/1).
- **Licence:** CC-BY (stated in the spreadsheet, `intro!A8`: provided "as-is").
  The CSV files in `cases/` are derived from it: the spreadsheet's own formulas
  were run on the inputs below and the results exported. Nothing in the
  spreadsheet's method was changed.
- **The xlsx itself is not in this repository.** `generate_cases.py` takes its
  local path as an argument. The copy used here was 1,170,760 bytes, SHA-256
  `eb8e41611d313e99066cbf93e8b2e192462e49ea4bff09850380f7679d90ac75`.

Please cite the paper above wherever these reference cases are used.

## Parameter set

The spreadsheet uses IPCC AR5 values, unchanged for every case:

- CO₂ impulse response (Joos et al. 2013): a₀ = 0.2173; pools 0.224 / 0.2824 /
  0.2763 with τ = 394.4 / 36.54 / 4.304 yr.
- Radiative efficiencies and adjustments: Myhre et al. 2013 (AR5 WG1 ch. 8).
- CH₄ lifetime 12.4 yr, forcing adjustment 1 + 0.15 + 0.5 = 1.65.
- N₂O (the spreadsheet's `gas1`, "Nitrous Oxide") lifetime 121 yr.
- Two-box climate response (Boucher & Reddy 2008): 0.631 / 0.429 K (W m⁻²)⁻¹,
  8.4 / 409.5 yr.
- Time horizon for the equivalence metrics: 100 yr (`intro!H26`).
- Oxidised CH₄ to CO₂ (when `fossil_CH4` is TRUE): 50% × 44/16 = 1.375 kg CO₂
  per kg CH₄ decayed (`intro!G31`).

## Cases

Emissions are pulses at the start of each year, years 0–500; positive is into
the atmosphere. Gases `gas2` (sulphate) and `gas3` (CFC-11) and the "other
forcing" column are set to 0 in every case.

| Case | Inputs (kg) | `fossil_CH4` |
|------|-------------|--------------|
| `co2_pulse` | 1 CO₂ at year 0 | FALSE |
| `ch4_pulse_biogenic` | 1 CH₄ at year 0 | FALSE |
| `ch4_pulse_fossil` | 1 CH₄ at year 0 | **TRUE** |
| `n2o_pulse` | 1 N₂O at year 0 | FALSE |
| `building_lifecycle` | A: 1000 CO₂, 2 CH₄, 0.1 N₂O at year 0. B: 10 CO₂, 0.05 CH₄, 0.002 N₂O every year 1–60. C: 200 CO₂, 1 CH₄, 0.02 N₂O at year 60 (added to that year's B). | FALSE |
| `negative_uptake` | −25 CO₂ every year 1–40 (−1000 in total) | FALSE |
| `late_pulse` | 1 CO₂ at year 250 | FALSE |

The shipped spreadsheet has `fossil_CH4 = TRUE`; the package's
`DLCAInputData.fossil_CH4` defaults to FALSE. Each case sets the flag
explicitly, and the tests set the engine's flag to match. The flag has no effect
on cases without CH₄. `building_lifecycle` uses FALSE so that it tests
multi-gas superposition apart from the fossil-CH₄ path, which
`ch4_pulse_fossil` covers.

## Files

Each `cases/<case>/` folder holds:

- `inputs.csv`: `year`, `CO2_flux`, `CH4_flux`, `N2O_flux` (kg per year, as a
  pulse at the start of the year). These are the values written into
  `inventory_and_effects` columns B, C and D (rows 7–507 = years 0–500).
- `settings.csv`: `fossil_CH4` (written to `intro!C31`) and `time_horizon`
  (`intro!H26`, unchanged at 100).
- `expected.csv`: the recalculated spreadsheet results, one row per year 0–500.

Numbers are written as the shortest text that round-trips the stored double.
LibreOffice stores cached results to 15 significant digits, so the expected
values carry about 1e-15 relative precision.

### `expected.csv` columns

All from rows 7–507 (years 0–500). "Start of year" means just after that
year's pulse.

| CSV column | Sheet | Column (row-6 header) | Units | Meaning |
|---|---|---|---|---|
| `year` | `inventory_and_effects` | A (`year`) | yr | |
| `CO2_mass` | `inventory_and_effects` | J (`CO2`) | kg | CO₂ in atmosphere, start of year |
| `CH4_mass` | `inventory_and_effects` | K (`CH4`) | kg | CH₄ in atmosphere |
| `N2O_mass` | `inventory_and_effects` | L (`gas1`) | kg | N₂O in atmosphere |
| `CO2_mass0`–`CO2_mass3` | `inventory_and_effects` | AX–BA (`CO2_mass0`–`CO2_mass3`) | kg | CO₂ decay pools |
| `CH4_to_CO2` | `inventory_and_effects` | BB (`CH4_to_CO2`) | kg | CO₂ added from oxidised CH₄ that year |
| `CO2_radfor` | `inventory_and_effects` | O (`CO2_radfor`) | W m⁻² | radiative forcing, start of year |
| `CH4_radfor` | `inventory_and_effects` | P (`CH4_radfor`) | W m⁻² | |
| `N2O_radfor` | `inventory_and_effects` | Q (`gas1_radfor`) | W m⁻² | |
| `CO2_IRF` | `inventory_and_effects` | U (`CO2_IRF`) | W yr m⁻² | forcing integrated up to the start of the year |
| `CH4_IRF` | `inventory_and_effects` | V (`CH4_IRF`) | W yr m⁻² | |
| `N2O_IRF` | `inventory_and_effects` | W (`gas1_IRF`) | W yr m⁻² | |
| `IRF_all` | `inventory_and_effects` | H (`Integrated_rad_forcing`) | W yr m⁻² | total |
| `CO2_temp` | `inventory_and_effects` | AA (`CO2_temp`) | K | temperature change, start of year |
| `CH4_temp` | `inventory_and_effects` | AB (`CH4_temp`) | K | |
| `N2O_temp` | `inventory_and_effects` | AC (`gas1_temp`) | K | |
| `temp_change` | `inventory_and_effects` | I (`Temp_change`) | K | total ΔT |
| `CO2_net`, `CH4_net`, `N2O_net` | `inventory_and_effects` | AG, AH, AI (`CO2_net`, `CH4_net`, `gas1_net`) | kg | cumulative net emissions |
| `GWP_static_CO2e` | `equivalency_metrics` | E (spreadsheet label: "GWP with sliding 100 year time-horizon") | kg CO₂e | cumulative net emissions × GWP₁₀₀ (formula checked by the generator) |
| `GTP_static_CO2e` | `equivalency_metrics` | F (spreadsheet label: "GTP with sliding 100 year time-horizon") | kg CO₂e | cumulative net emissions × GTP₁₀₀ (formula checked by the generator) |
| `IRF_over_AGWP_CO2` | `equivalency_metrics` | I (IRF by that year ÷ AGWP₁₀₀(CO₂)) | kg CO₂e | |
| `temp_over_AGTP_CO2` | `equivalency_metrics` | J (ΔT by that year ÷ AGTP₁₀₀(CO₂)) | kg CO₂e | |
| `GWP_sliding_CO2e` | `equivalency_metrics` | K (IRF at year 100 from emissions up to that year ÷ AGWP₁₀₀(CO₂)) | kg CO₂e | |
| `GTP_sliding_CO2e` | `equivalency_metrics` | L (ΔT at year 100 from emissions up to that year ÷ AGTP₁₀₀(CO₂)) | kg CO₂e | |

Notes on the spreadsheet itself (reported, not changed):

- `intro!E50` (AGTP₁₀₀ of CO₂) multiplies the third CO₂ pool by `p_1` instead
  of `p_3`, the same slip as in the engine's `calc_AGTP`. It gives
  5.46535e-16 K kg⁻¹ where the spreadsheet's own year-100 temperature for a
  1 kg CO₂ pulse is 5.46862e-16 K (0.06% apart). `GTP_static_CO2e`,
  `temp_over_AGTP_CO2` and `GTP_sliding_CO2e` all divide by it.
- `GWP_sliding_CO2e` and `GTP_sliding_CO2e` use the per-year CO₂ and CH₄
  AGWP/AGTP tables in `equivalency_metrics` columns N, O, S and T. These are
  pasted values, not formulas, so they do not respond to the case inputs or to
  `fossil_CH4`. The CH₄ ones include the oxidised-CH₄ CO₂ (for example,
  AGWP₁₀₀(CH₄) = 2.6179e-12 there, against 2.6097e-12 from the formula in
  `intro!D51`).
- The `gas3` AGWP/AGTP columns R and W in `equivalency_metrics` use `gas2` or
  `gas1` parameters. They do not affect these cases, since `gas3` is 0.

## How the cases were generated

```bash
uv run --no-project --with openpyxl python -I \
    tests/reference/generate_cases.py /path/to/mmc2.xlsx
```

- **Tools:** openpyxl 3.1.5 and **LibreOffice 26.8.0.3**
  (`bce0998afefdbc355585ca324285661a2170ba77`) on macOS. The generator needs
  LibreOffice 7 or later.
- **Steps:** the generator copies the workbook into a temporary directory,
  writes each case's inputs into the green input cells with openpyxl (keeping
  the formulas), recalculates with
  `soffice --headless --calc --convert-to xlsx`, and reads the results back
  with `data_only=True`.
- **Checks it makes:**
  - the workbook is the expected one (it has the `intro` sheet, says
    version 5, has AGWP₁₀₀(CO₂) = 9.171093e-14, and every column header is
    as expected; for `equivalency_metrics`, whose headers are formulas, it
    checks the start of each column's row-8 formula instead);
  - the recalculation ran: cumulative net emissions match each case's inputs,
    and the CO₂-only positive control gives year-100 IRF = 9.17109e-14 W yr m⁻²
    = AGWP₁₀₀(CO₂), with zero CH₄ and N₂O mass.
- **Deterministic:** two runs give byte-identical CSVs.
- **Not run in CI.** Only the CSVs are committed.

## Tests

`test_cooper_reference.py` runs the engine (`calc_decay`, `calc_AGWP`,
`calc_AGTP` with a time horizon of 100) on each case's `inputs.csv` and
compares 24 result columns with `numpy.testing.assert_allclose`:

- `rtol = 1e-9`;
- `atol = 1e-9 × max |expected|` for that column.

Where the engine disagrees, the test is marked `xfail(strict=True)` with the
suspected cause and the measured size. Those are fixed in M1. **Never edit the
expected values or the tolerances to make a test pass.**
