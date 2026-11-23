# 0020. Trajectories for biogenic items: their CO₂ is not scaled

- **Status:** Proposed
- **Date:** 2026-11-20
- **Decided by:**
- **Supersedes:** 0018, in part: the refusal of a non-constant
  `b4_c_trajectory` on a building with any `biogenic` field (E2, as amended
  to cover B5 events).

## Context

Record 0018 lets a `b4_c_trajectory` m(y) scale the fossil gases (`co2`,
`ch4_fossil`, `n2o`) of B4 events and of C1–C4. Biogenic release has no field
of its own: users enter it inside those amounts as `co2` and non-fossil `ch4`
(record 0016). Scaling it would cut the release of stored carbon while the
uptake credit stays whole, so 0018 refused any trajectory other than
`constant` on a building with a `biogenic` field. No building with a timber
product could use a trajectory. Issue #86 holds the proposal (G1–G4) and
Jay's decisions of 2026-11-20.

## Decision

We will leave a biogenic item's CO₂ out of the trajectory instead of
refusing.

- **What is left unscaled (G1, G2).** On a biogenic item, the `co2` of its
  C1–C4 and B4 amounts is used as entered. `ch4_fossil` and `n2o` are still
  scaled by m(RSP + 1) or m(event year), since neither can hold biogenic
  carbon. Non-fossil `ch4` is never scaled, as before. `released_co2` is not
  read, so it stays reporting only (record 0016).
- **What a biogenic item is (G2, G3, G4).** A `Material` is biogenic if it,
  or any of its B4 or B5 events, has a `biogenic` field. The field's
  presence is enough, whatever its `released_co2` (0 included) or `regrowth`
  (`"none"` included). A `BuildingTotals` is one item, biogenic if it or any
  of its events has the field. Other materials in the same building get the
  full trajectory.
- **B4 and B5 (G4).** A biogenic material's B4 `co2` is unscaled at every
  event. B5 amounts stay unscaled, as in 0018. A B5 event's `biogenic` field
  counts because that item's release is usually entered in the material's
  C1–C4.
- **Telling the user (G3).** Documentation only, with no runtime warning.
- **Breakdowns.** No amount is split, so every breakdown still adds up to the
  total (record 0015, R8) with no new rule.
- **Versions.** No field changes. The inventory schema stays at version 5,
  and `BuildingResult` and `Timeline` JSON are unchanged. Version 5 is not
  yet released (v0.5.0 waits on #86). Inputs that loaded before give the same
  numbers, bit for bit.

**Independent check.** Worked by hand in #86 before any code. RSP = 60,
`linear` to 0 in year 50: m(25) = 0.5, m(61) = 0. Quantities are 1.

| Material | Input | Expected |
|---|---|---|
| Timber: `biogenic` {100, `instant`, `released_co2` 80} | C3: co2 100, n2o 1 | co2 100, n2o 0 |
| Timber | B4, year 25: co2 40, ch4_fossil 2, n2o 0.2 | 40, 1, 0.1 |
| Timber | uptake | −100 kg CO₂ in year 0, as with `constant` |
| Steel: no `biogenic` | C3 co2 100; B4 in year 25, co2 40 | 0; 20 |
| Steel with a `biogenic` B5 event in year 10, co2 10 | C3 co2 100; B5 | 100; 10 |
| Steel, quantity 2, with a `biogenic` B4 event only (year 25, co2 40) | C3 co2 100; B4 | 200; 80 |
| `BuildingTotals` with `biogenic` | C3: co2 100, n2o 1; B4 in year 25, co2 40 | 100, 0; 40 |

The issue's first example (`released_co2` 80 of 100 kg in C3) now expects
100, not 80.

These deliberate mistakes each make a check fail (run in the PR):

- The fear: scaling a biogenic material's `co2` gives C3 = 0, not 100.
- Exempting the whole building gives Steel C3 = 100, not 0.
- Exempting every gas gives Timber C3 n2o = 1, not 0.
- Ignoring B5 events gives the B5 material's C3 = 0, not 100.
- Ignoring B4 events gives the B4 material's C3 = 0, not 200 (the row was
  added after the fresh-session review on PR #90 found the gap).

Positive control: Timber's C3 is the same under `linear` as under
`constant`. The same comparison on Steel, in the same building, detects the
change (100 → 0 and 40 → 20).

## Alternatives considered

- **(a) Keep `released_co2` unscaled and scale the rest**: co2 →
  `released_co2` + m·(co2 − `released_co2`). Lost: it makes a reporting
  field move emissions. It needs a rule for which C module holds the
  unscaled part, because `released_co2` is one number for all of C1–C4. It
  also needs a guard, since a `released_co2` larger than the CO₂ it sits in
  would raise emissions above what was entered.
- **(b) A per-module biogenic CO₂ field** on each amount. Lost: exact, but a
  schema change for a corner case, and it states the same carbon twice
  (beside `released_co2`).
- **Exempt every gas of a biogenic item.** Lost: it drops a safe reduction of
  `ch4_fossil` and `n2o`.
- **Per amount instead of per material** (C1–C4 by the item in place at end
  of life, a B4 amount by the item it replaces). Lost: it needs a rule for
  which item's release sits in which B4 amount (a B4 amount holds the old
  item's C1–C4, while `Event.biogenic` describes the new item), which is
  easy to get wrong.
- **Whole building.** Lost: one timber item would switch the trajectory off
  for all the concrete and steel.
- **Only items with `regrowth` other than `"none"`.** Lost: a release of
  stored carbon should not follow a supply-chain trajectory either way.
- **A warning per exempted material.** Lost: it would fire on every valid
  timber input under a trajectory.
- **Keep the refusal.** Lost: it locks every building with timber out of
  trajectories.

## Consequences

- Buildings with biogenic items can use a trajectory. Their non-biogenic
  materials get the full reduction.
- **Overstates, never understates.** The fossil CO₂ of a biogenic material's
  C1–C4 and B4 amounts (demolition, transport, processing) gets no
  reduction. A material that gets a timber B4 replacement is exempt in full,
  including the first B4 amount, which holds the old item's fossil
  end-of-life CO₂.
- The limit in 0018 stays: a biogenic release entered in C on a material
  with no `biogenic` field is scaled, and only the documentation covers it.
- When Jay accepts this record, 0018's Status becomes "Superseded in part by
  0020".

## References

- Issue #86: the proposal and Jay's decisions of 2026-11-20
  (<https://github.com/jayarehart/DLCA/issues/86#issuecomment-7052695019>).
- Records 0015 (R8), 0016 and 0018 (E2, and its B5 amendment in PR #89).
- `tests/analytic/test_trajectory_biogenic.py`.
