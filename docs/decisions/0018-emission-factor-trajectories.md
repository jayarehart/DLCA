# 0018. Emission-factor trajectories for B4 and end-of-life emissions

- **Status:** Proposed
- **Date:** 2026-11-20
- **Decided by:**
- **Extends:** 0013 (inventory schema), 0014 (module timing) and 0015
  (`BuildingResult`).

## Context

Replacements (B4) and end of life (C1–C4) happen decades after construction,
when the grid and industry may emit less. Today their amounts use today's
factors, so a B4 event in year 40 counts the same kg as one in year 1. The M4
roadmap asks for three kinds of trajectory: constant, linear to a target
year, or a series the user gives. Biogenic release has no field of its own:
the user enters it inside C1–C4 and B4 amounts as `co2` and non-fossil `ch4`
(record 0016). Scaling those amounts as a whole would therefore also cut a
timber product's release, while its uptake credit stays whole. Issue #81 holds
the proposal (E1–E5) and Jay's decisions of 2026-11-20.

## Decision

We will let a building carry an optional multiplier m(y) that scales the
fossil gases of its B4 events and of its C1–C4 amounts.

**What a trajectory is (E1).** m(y) is defined on study years: year 0 is
construction, and there is no calendar year. m(0) = 1.

| Kind | Fields | m(y) |
|---|---|---|
| `constant` | none | 1 in every year |
| `linear` | `target` ≥ 0, `target_year` ≥ 1 (whole number) | 1 − (1 − `target`)·y/`target_year` for y ≤ `target_year`, then `target` |
| `series` | `values`: at least one, each finite and ≥ 0, first value 1 | `values[y]`. Years past the last value use the last value. A series longer than RSP + 2 is accepted and its extra values are ignored. |

A delayed decline (m = 1 for a while, then falling) needs a `series`.

**What it scales (E2, E3).** One multiplier for every scaled gas.

| Amount | Year used for m | Scaled gases |
|---|---|---|
| Each B4 event | the event's year | `co2`, `ch4_fossil`, `n2o` |
| C1, C2, C3, C4 | RSP + 1 | `co2`, `ch4_fossil`, `n2o` |

- Non-fossil `ch4` is never scaled.
- A B4 amount is the new item's A1–A5 plus the old item's C1–C4 (record
  0013). Both happen in the event year, so one m fits the whole amount.
- These are not scaled: A1–A3, A4, A5, B1–B3, B5, B7, biogenic uptake (record
  0016) and carbonation (record 0017). B6 gets its own trajectory in #82.
- A trajectory other than `constant` is refused if the `BuildingTotals`, any
  `Material` or any B4 or B5 event has a `biogenic` field. This applies to any
  `biogenic` field, not only one with `released_co2` > 0: a user may enter a
  release while leaving `released_co2` at 0. The refusal covers B5 events
  as well as B4 (Jay, 2026-11-20, amending E2 after review): the release of a
  B5 item's biogenic carbon would usually be entered in the material's
  C1–C4, which is scaled. The refusal looks at `kind`, so a trajectory that is
  constant in effect (`series` [1], or `linear` with `target` 1) is refused
  too.
- All of C1–C4 is scaled, including C4 (landfill and incineration). The
  trajectory is a scenario the user chooses, and the documentation says so.

**Where it lives (E4).** An optional field `b4_c_trajectory` on
`BuildingTotals` and `BuildingInventory`. There is no per-material override.

- The value is a shared `Trajectory` type, chosen by `kind`:
  `{"kind": "constant"}`, `{"kind": "linear", "target": …, "target_year": …}`
  or `{"kind": "series", "values": [...]}`. #82 can reuse it.
- Absent (`None`, left out of the JSON) means `constant`.
- Inventory `schema_version` goes from 3 to 4. Versions 1–3 still load and may
  not use the field. The JSON Schema files are regenerated.
- Inputs without the field, or with an explicit `constant`, give the same
  numbers as v0.4.0, bit for bit.

**How results record it (E5).**

- The trajectory is recorded only through the building input that
  `BuildingResult` already stores. `BuildingResult` JSON goes to
  `schema_version` 4 and still reads versions 1–3.
- `Result` (schema 4) is unchanged: `assess()` sees only the scaled
  emissions.
- `Timeline` JSON (version 3) is unchanged: its parts hold the scaled amounts
  and gain no new modules.
- The rows of every breakdown still add up to the total (record 0015, R8).

**Independent check.** This is a closed-form case, written down in #81 before
any code. RSP = 60, `linear`, `target` = 0, `target_year` = 50, so
m(y) = 1 − y/50 up to year 50 and 0 after.

| Input | Expected |
|---|---|
| B4 event in year 25: 100 kg CO₂ | 50 kg CO₂ |
| B4 event in year 25: 10 kg `ch4`, 10 kg `ch4_fossil`, 1 kg `n2o` | `ch4` 10 kg, `ch4_fossil` 5 kg, `n2o` 0.5 kg |
| B4 event in year 55 | 0 |
| C1–C4 (year 61) | 0 |
| A1–A3 | unchanged |
| B5 event in year 25: 100 kg CO₂ | 100 kg CO₂ |
| `series` [1, 0.5]: B4 event in year 25 (100 kg CO₂); 100 kg CO₂ in C | 50 kg; 50 kg |
| A `biogenic` field with a trajectory other than `constant` | refused |
| The same building with an explicit `constant` | accepted; same as no trajectory |

These deliberate mistakes must each make a check fail:

- Indexing m by the event year − 1 gives m(24) = 0.52, so 52 kg instead of 50.
- Scaling B5 events gives 50 kg instead of 100.
- Scaling non-fossil `ch4` gives 5 kg instead of 10.

"Scaling A1–A3", which #81 listed, cannot make any check fail: m(0) = 1 is
required, so scaling year 0 is a no-op. The run showed this (all checks
passed), and the B5 mistake took its place.

Positive control: `constant` gives the same `assess()` result as no
trajectory, and the same comparison detects the `linear` case.

## Alternatives considered

- **Scale all gases, as first proposed.** Lost: biogenic release lives inside
  C1–C4 and B4 amounts, so scaling every gas cuts the release of stored carbon
  while the uptake stays whole.
- **Scale fossil gases and keep `released_co2` unscaled instead of
  refusing.** Lost for v0.5: `released_co2` is one number for all of C1–C4.
  The module breakdown would need a rule for which module holds it, and that
  rule is a science choice of its own. Left to a follow-up issue.
- **Refuse only when `released_co2` > 0.** Lost: it misses a release that the
  user entered without declaring it.
- **A calendar `start_year`, so targets read as e.g. 2050.** Lost: a second
  way to say the same thing. It may come back with #82 if grid data needs it.
- **A delayed start for `linear`.** Lost: a `series` already does it.
- **A `series` of exactly RSP + 2 values.** Lost: Jay chose a shorter series
  that holds its last value, so one series can be reused across study
  periods. The cost is that a wrong length is not caught.
- **Scale only B4 and C1–C3, or let the user list the modules.** Lost: kept
  simple. All of C1–C4 is scaled, as a scenario the user chooses.
- **One trajectory per gas.** Lost: no current use. It may come later.
- **A per-material override.** Lost for v0.5.
- **Name the field `emission_factor_trajectory`.** Lost: the name becomes
  ambiguous once B6 has its own trajectory (#82).
- **Also store the computed m(y) series in `BuildingResult` JSON.** Lost:
  redundant, since the stored building rebuilds it (as 0015 R7 argues for
  `Timeline`).

## Consequences

- **What gets easier.** Users can test how decarbonising supply changes the
  impact of B4 and end-of-life emissions. The `Trajectory` type is ready for
  B6 (#82).
- **What gets harder.** A building with any biogenic material cannot use a
  trajectory other than `constant` until the follow-up lifts the refusal.
- **Limits.**
  - The multiplier scales the whole fossil amount, including process
    emissions that do not fall as energy supply decarbonises (for example
    cement calcination inside a B4 amount, or fossil CO₂ from incinerating
    plastics in C4). Choosing a trajectory that fits the materials is up to
    the user.
  - A wrong `series` length passes without an error.
  - A biogenic release entered as `co2` in C1–C4 on a material with no
    `biogenic` field is scaled without any warning. Only the documentation can
    cover this.
- **Commitments.**
  - Inventory schema 4 and `BuildingResult` schema 4.
  - `src/dlca/inventory/aggregate.py` changes for the version bump, which #81
    did not list.
  - If #82 lands later and changes the schema, it bumps the versions again.

## References

- Issue #81: the proposal, and Jay's decisions of 2026-11-20
  (<https://github.com/jayarehart/DLCA/issues/81#issuecomment-7049947498>).
  Jay confirmed the longer-series rule in the #81 working session on
  2026-11-20.
- Records 0005, 0008, 0013, 0014, 0015, 0016, 0017.
- `docs/roadmap.md`, M4 item 1. Issue #82 (B6) reuses the trajectory type.
