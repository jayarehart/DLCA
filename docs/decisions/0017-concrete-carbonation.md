# 0017. Concrete carbonation: Lagerblad (2005), √t uptake in use, crushed stockpile at end of life

- **Status:** Proposed
- **Date:** 2026-11-20
- **Decided by:**
- **Extends:** 0014 (module timing), which says "a per-year profile needs a
  new record". This record adds two per-year profiles.

## Context

Concrete takes CO₂ back up by carbonation, in use and after demolition. Until
now a user could enter it only as a constant B1 amount per year. The concrete
example had −0.2 kg CO₂/m³ per year. Real carbonation depth grows with √t, so
a constant yearly amount has the wrong shape, and early uptake counts more in
GWI. The legacy model in `legacy/carbonation/` never ran and has known bugs
(#74), so it is neither a reference nor a base to port. Issue #74 holds the
proposal (K1–K8) and Jay's decisions of 2026-11-20. EN 16757 was dropped
because nobody had read it. Lagerblad (2005) is public and was read in full.

## Decision

We will model carbonation with Lagerblad (2005), CBI report 2:2005, as an
optional `carbonation` field on `Material` and on its B4 events (schema
version 3).

**Model (K1, K2).**

| Field | Meaning |
|---|---|
| `strength_class` | `<15`, `15-25`, `25-35`, `>35` MPa (cylinder). These are appendix A2.3's bands, used with Table 2's k values (Table 2 prints the second band as 15–20 MPa). |
| `cement` > 0 | Portland cement (clinker) content, kg per m³. For a blended cement, the Portland part only. |
| `surfaces` (≥ 1) | `{area, exposure, cover}`. `area` is m² per declared unit. `exposure` is `indoors`, `sheltered`, `exposed`, `wet` or `buried` (Table 2 rows). `cover` is `none` (× 1.0), `indoor_house` (× 0.7) or `outdoor_house` (× 0.9) (Table 3). |
| `end_of_life` | `{radius, years}`: crushed sphere radius in mm (required) and years in the stockpile (default 1). |
| `cao_share` | Mass share of CaO in the Portland cement, default 0.65. |
| `binder_factor` ≥ 1 | Factor on k, default 1.0. Table 4 is guidance only: it and appendix A2.4 disagree, so neither is encoded. |
| `degree_of_carbonation` | Default 0.75 (Lagerblad §5.1.5). Andersson et al. use 0.8–0.9. |
| `volume` | m³ of concrete per declared unit. Required unless the unit is `m3` (then it is 1 and may not be given). |

- Depth d = k·√t mm, with t in years since casting.
  k = Table 2 × cover factor × `binder_factor`.
- Uptake per m³ of carbonated concrete is
  a = `degree_of_carbonation` × `cement` × `cao_share` × 44.01/56.077 kg CO₂.
- Carbonated volume per declared unit V_c(t) = min(Σ area·d/1000, volume),
  following Andersson et al. (2013) eq. 2. U(t) = a·V_c(t).

**Timing (K3, K4; extends 0014).** All uptake is negative `co2` in two new
timeline parts.

| Part (module) | Years | Amount |
|---|---|---|
| `carbonation-uptake` | s + 1 .. e | U(t − s) − U(t − s − 1) in year t (Andersson et al. eq. 1) |
| `carbonation-eol` | RSP + 1 .. RSP + n | a·V_u·(f(j + 1) − f(j)) in year RSP + 1 + j |

- s is the casting year: 0 for the material's own item, or the year of a B4
  event that carries `carbonation`. e is RSP for the item in place at the end.
  For an item that is replaced, e is the year before the replacing event, so
  nothing carbonates in the event year. This matches year 0 for casting,
  when nothing carbonates either.
- In RSP + 1 (record 0014's end-of-life year) the uncarbonated remainder of
  the last item, V_u = volume − V_c(RSP − s), is crushed into spheres of
  radius r. The carbonated share after j years is
  f(j) = 1 − ((r − d)/r)³, with d = k·√j and f = 1 once d ≥ r. The stockpile k
  is Table 2 for `exposed` at the same strength class, times `binder_factor`,
  with no cover factor. The first stockpile year is the crushing year itself.
- Stockpile years past the series end are cut, and `CarbonationWarning` names
  the `years` that would keep them.
- Module order in the breakdown: `carbonation-uptake` after B1, and
  `carbonation-eol` after C4. `Timeline` and `BuildingResult` JSON go to
  version 3 and still read versions 1 and 2.

**Replacements (K5).** A B4 event restarts the clock in its year only if it
carries its own `carbonation` (per declared unit of the same material). The
replaced item's in-use uptake stops, and it gets **no** stockpile uptake. At
most one B4 event per year per material may carry `carbonation`.
`carbonation` is refused on B5 events and on `BuildingTotals`. A B4 event
without `carbonation`, on a material with an earlier carbonating item, keeps
the old clock and raises `CarbonationWarning`.

Schema version 1 and 2 files still load and may not use `carbonation`. Inputs
with no `carbonation` give the same numbers as before, bit for bit.

## Alternatives considered

- **EN 16757 (Annex BB/G).** Lost: nobody had read the standard. Public
  sources describe a formula of the same form, but that link is not checked.
- **Port the legacy fib/Possan-style model.** Lost: it never ran, has the bugs
  listed in #74, and its constants would each need a citation.
- **A constant B1 amount per year (the old way).** Lost: wrong shape, and it
  overstates late uptake against early uptake.
- **The user enters k directly.** Lost: there is less to check. A user can still raise k
  through `binder_factor` (it cannot go below 1).
- **Stockpile uptake for the replaced item from the event year.** Lost for
  v0.4: the user's B4 amount already holds its C1–C4, and a stockpile part
  would need its own placement rule.
- **No end-of-life uptake in v0.4.** Lost: that under-counts what is often the
  larger part of the uptake.
- **Other models (for example Jungclaus et al. 2025).** Deferred to #76.

## Consequences

- **Known limit: the stockpile may overstate.** Andersson et al. (2013)
  found end-of-life uptake today is only about 11 % of the theoretical
  maximum, because stockpiles let little air in. Open-air spheres with
  `exposed` k ignore this. For the concrete example, stockpile uptake is about
  1.1 times the in-use uptake.
- **Known under-count:** concrete replaced by a B4 event gets no crushed
  end-of-life uptake.
- **Known under-count:** at each carbonating B4 event, neither item
  carbonates in the event year. The old item stops at event year − 1, as the
  building stops at RSP before its end of life in RSP + 1, and the new item
  starts in event year + 1, as cast concrete does after year 0. In the
  `test_b4_with_carbonation_restarts_the_clock` case (k = 6, 2.5 m²/m³, B4 in
  year 20), one year of the old item's increment is about 2.7 % of its
  19-year uptake. The alternative is to let the old item carbonate through
  the event year.
- The volume cap treats the surfaces' carbonated layers as additive. Edges
  and corners, where layers overlap, are not corrected (Andersson et al.
  note the same). Thin or compact elements can therefore reach the cap a
  little early.
- One `degree_of_carbonation` per item. Andersson et al. use one per surface.
- No increase of k with rising atmospheric CO₂. Lagerblad (§5.1.2) suggests a
  factor of 1.5 for 50–100-year calculations. A user can apply it through
  `binder_factor`, but nothing does so by default.
- Uptake after the stockpile (for example recycled aggregate in new concrete,
  or fill) is not modelled.
- The `volume` field depends on the material's unit, so the committed JSON
  Schemas cannot check it, and they accept `carbonation` under schema
  versions 1 and 2. The models refuse both. The JSON Schemas are weaker than
  the models here, as already noted in records 0013 and 0016.
- The hand-entered B1 −0.2 lines are gone from `concrete.json` and from the
  topping in `steel.json`. `concrete.json`'s totals change (see
  `tests/data/inventories/README.md`).
- `legacy/carbonation/` is deleted (K6).

## References

- Issue #74 (proposal K1–K8 and Jay's decisions, 2026-11-20); #73 and record
  0016 (the same optional-field pattern); #76 (other models).
- Records 0008 (uptake as negative `co2`), 0013, 0014 (extended), 0015.
- Lagerblad, B. (2005). *Carbon dioxide uptake during concrete life cycle:
  state of the art*. CBI report 2:2005, Swedish Cement and Concrete Research
  Institute. Table 2 (k values), Table 3 (cover factors), Table 4 (binder
  factors, guidance only), §5.1.5 (uptake formula), §5.3.2 (worked examples,
  used in `tests/unit/test_inventory_carbonation.py`).
- Andersson, R., Fridh, K., Stripple, H., Häglund, M. (2013). Calculating CO₂
  uptake for existing concrete structures during and after service life.
  *Environ. Sci. Technol.* 47, 11625–11633. doi:10.1021/es401775w. Eq. 1
  (yearly increments), eq. 2 (multi-surface volume), the roof-tile example
  (k_V(11.5) = 0.646, used in the tests), Table 2 (stockpile times), and the
  11 % finding. The Supporting Information was not read.
