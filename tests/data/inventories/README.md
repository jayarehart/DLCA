# Example inventories (illustrative)

Shared test data for the inventory schemas (record 0013), the timing engine
(record 0014), the roll-up (#59) and the M5 tutorials. Issue #60 holds the
proposal and Jay's approval (2026-11-19).

**Every number in these files is illustrative.** The values are made up,
rounded and meant to be plausible. They do not come from an EPD, a dataset or
any study, so they have no source and no licence beyond this repository's. Do
not cite them as data about real products. The ranges below are rough orders
of magnitude from general knowledge, so a reader can judge whether a number is
plausible. They are not citations.

| File | Schema | What it is |
|---|---|---|
| `timber.json` | `BuildingInventory` | CLT floor on glulam beams |
| `steel.json` | `BuildingInventory` | Steel beams with a composite deck |
| `concrete.json` | `BuildingInventory` | 250 mm reinforced flat slab |
| `totals.json` | `BuildingTotals` | Whole-building totals with their own numbers (not a roll-up of the other three) |

Load them with the pytest fixtures `example_inventories` (name to
`BuildingInventory`) and `example_totals` (a `BuildingTotals`) in
`tests/conftest.py`.

## Common frame (illustrative)

- The three inventories are the **floor structure of a 1,000 m² office
  floor**: no columns, foundations or finishes. They can be compared like for
  like.
- `study_period` = 60 years for all three.
- No B6 or B7: operational energy and water are M4.
- All amounts are kg per declared unit (B1 per unit per year, B4/B5 per unit
  per event).
- All CH₄ in A1–A3 comes from fossil supply chains, so it is `ch4_fossil`.
  The only non-fossil `ch4` is timber landfill gas in C4.
- A4, A5 and C1–C3 are fuel use, so CO₂ only. At this rounding, the CH₄ and
  N₂O from fuel use are negligible.
- A4 uses about 0.1 kg CO₂ per t·km by truck (range 0.06–0.15).
- **The timber inventory has no biogenic carbon** (no uptake, no biogenic
  CO₂ at end of life) until M3. Its A1–A3 is fossil only. Until then it is
  not a fair comparison with steel or concrete.

Columns below: A1–A3 as co2 / ch4_fossil / n2o, the other modules co2 only
unless marked.

## `timber.json` (illustrative)

| Assembly / material | Qty | Unit | A1–A3 | A4 | A5 | C1 | C2 | C3 | C4 | Events |
|---|---|---|---|---|---|---|---|---|---|---|
| Floor / CLT panels | 200 | m3 | 120 / 0.2 / 0.01 | 25 | 5 | 3 | 2 | 5 | 2, ch4 2.0 | B5 year 30: co2 2 |
| Frame / Glulam beams | 30 | m3 | 140 / 0.2 / 0.01 | 25 | 5 | 3 | 2 | 5 | 2, ch4 2.0 | none |
| Frame / Steel connectors | 2000 | kg | 2.0 / 0.003 / 0.00005 | 0.05 | 0.02 | 0.01 | 0.005 | 0.02 | 0.001 | none |

- CLT and glulam fossil CO₂ in A1–A3: about 100–200 kg/m³ (drying, glue,
  processing energy). Glulam is a little higher (more glue lines).
- A4: 0.47 t/m³ × 500 km × 0.1. Engineered timber often travels far.
- B5 year 30: refinishing the exposed soffit, about 0.4 kg CO₂/m² of floor ÷
  0.2 m³/m² = 2 kg/m³.
- C4 `ch4` 2.0 kg/m³ (non-fossil): a placeholder for landfill gas from wood
  that decomposes, after capture and oxidation. Range 0.5–10 kg/m³. Very
  uncertain. Biogenic carbon proper is M3.
- Connector steel: 1.5–2.5 kg CO₂/kg.

**Hand total, A1–A3:**

- co2: 200 × 120 + 30 × 140 + 2000 × 2.0 = 24,000 + 4,200 + 4,000 = **32,200 kg**
- ch4_fossil: 200 × 0.2 + 30 × 0.2 + 2000 × 0.003 = 40 + 6 + 6 = **52 kg**
- n2o: 200 × 0.01 + 30 × 0.01 + 2000 × 0.00005 = 2 + 0.3 + 0.1 = **2.4 kg**

About 34 kg CO₂e per m² of floor (range 20–60 for fossil only).

**Hand total, whole series (all modules and events):**

- co2: CLT 200 × (150 + 12 + 2) = 32,800; glulam 30 × (170 + 12) = 5,460;
  connectors 2000 × 2.106 = 4,212. Total **42,472 kg**.
- ch4: (200 + 30) × 2.0 = **460 kg**. ch4_fossil **52 kg**, n2o **2.4 kg**
  (A1–A3 only).

**Hand total by module, co2 (kg):** A1–A3 32,200; A4 200 × 25 + 30 × 25 +
2000 × 0.05 = 5,850; A5 1,190; C1 710; C2 470; C3 1,190; C4 462; B5 400
(all in year 30). Sum 42,472.

## `steel.json` (illustrative)

| Assembly / material | Qty | Unit | A1–A3 | A4 | A5 | C1 | C2 | C3 | C4 | Events |
|---|---|---|---|---|---|---|---|---|---|---|
| Frame / Steel beams | 30 | t | 1500 / 2 / 0.05 | 50 | 20 | 10 | 5 | 20 | 1 | none |
| Frame / Intumescent coating | 750 | m2 | 5 / 0 / 0 | 0.1 | 0.5 | 0 | 0 | 0 | 0.5 | B4 years 25 and 50: co2 6 each |
| Floor / Steel deck | 12 | t | 2500 / 3 / 0.06 | 50 | 20 | 10 | 5 | 20 | 1 | none |
| Floor / Concrete topping | 120 | m3 | 300 / 0.4 / 0.01 | 7 | 15 | 10 | 12 | 5 | 3 | B1: co2 −0.2 per year |

- Beams 30 kg/m², deck 12 kg/m², topping about 120 mm on average: a typical
  composite floor.
- Steel sections (mostly recycled scrap): 1.0–2.0 t CO₂/t. Galvanised deck
  (mostly blast-furnace steel): 2.0–3.0 t/t.
- Coating: about 1–2 kg of product per m² at 3–5 kg CO₂/kg. The coated area
  of 750 m² comes from about 25 m² per t of beam.
- B4: the coating is replaced twice in 60 years. Each event is the new
  coating's A1–A5 (5.6) plus the old coating's C1–C4 (0.5) = 6.1, rounded to
  6 kg/m². The sum is written in by hand, as record 0013 requires.
- The concrete topping uses the same per-unit factors as the slab in
  `concrete.json`.

**Hand total, A1–A3:**

- co2: 30 × 1500 + 750 × 5 + 12 × 2500 + 120 × 300 = 45,000 + 3,750 + 30,000 + 36,000 = **114,750 kg**
- ch4_fossil: 30 × 2 + 12 × 3 + 120 × 0.4 = 60 + 36 + 48 = **144 kg**
- n2o: 30 × 0.05 + 12 × 0.06 + 120 × 0.01 = 1.5 + 0.72 + 1.2 = **3.42 kg**

About 120 kg CO₂e per m² of floor (range 80–200).

**Hand total, whole series:**

- co2: beams 30 × 1606 = 48,180; coating 750 × (6.1 + 2 × 6) = 13,575;
  deck 12 × 2606 = 31,272; topping 120 × (352 − 0.2 × 60) = 40,800. Total
  **133,827 kg**.
- ch4 **0 kg**, ch4_fossil **144 kg**, n2o **3.42 kg**.

**Hand total by module, co2 (kg):** A1–A3 114,750; A4 30 × 50 + 750 × 0.1 +
12 × 50 + 120 × 7 = 3,015; A5 3,015; C1 1,620; C2 1,650; C3 1,440; C4 777;
B1 120 × −0.2 = −24 per year, −1,440 over 60 years; B4 750 × 6 = 4,500 in
each of years 25 and 50, 9,000 in all. Sum 133,827.

## `concrete.json` (illustrative)

| Assembly / material | Qty | Unit | A1–A3 | A4 | A5 | C1 | C2 | C3 | C4 | Events |
|---|---|---|---|---|---|---|---|---|---|---|
| Slab / Concrete C30/37 | 250 | m3 | 300 / 0.4 / 0.01 | 7 | 15 | 10 | 12 | 5 | 3 | B1: co2 −0.2 per year |
| Slab / Rebar | 25 | t | 1000 / 1.5 / 0.03 | 30 | 20 | 10 | 5 | 20 | 1 | none |

- Concrete A1–A3: 250–350 kg CO₂/m³ for ordinary Portland cement mixes.
- Rebar (electric-arc, recycled): 0.7–1.5 t CO₂/t, at 100 kg per m³ of
  concrete.
- A4: 2.4 t/m³ × 30 km × 0.1 ≈ 7. A5 includes about 3 % waste and pumping.
- B1 is carbonation uptake: −0.2 kg CO₂/m³ per year, so −12 kg/m³ over 60
  years, about 4 % of A1–A3 (range 2–20 % for indoor slabs over a life). It
  is the only negative number in the set.
- C2: 2.4 t/m³ × 50 km × 0.1 = 12.

**Hand total, A1–A3:**

- co2: 250 × 300 + 25 × 1000 = 75,000 + 25,000 = **100,000 kg**
- ch4_fossil: 250 × 0.4 + 25 × 1.5 = 100 + 37.5 = **137.5 kg**
- n2o: 250 × 0.01 + 25 × 0.03 = 2.5 + 0.75 = **3.25 kg**

About 105 kg CO₂e per m² of floor (range 60–150).

**Hand total, whole series:**

- co2: concrete 250 × (352 − 12) = 85,000; rebar 25 × 1086 = 27,150. Total
  **112,150 kg**.
- ch4 **0 kg**, ch4_fossil **137.5 kg**, n2o **3.25 kg**.

**Hand total by module, co2 (kg):** A1–A3 100,000; A4 250 × 7 + 25 × 30 =
2,500; A5 4,250; C1 2,750; C2 3,125; C3 1,750; C4 775; B1 250 × −0.2 = −50
per year, −3,000 over 60 years. Sum 112,150.

## `totals.json` (illustrative)

A `BuildingTotals` with its own numbers, so tests of the totals path do not
depend on the inventories. Whole-building kg, `study_period` = 50 years.

| Module | Amount |
|---|---|
| A1–A3 | co2 250,000, ch4_fossil 300, n2o 8 |
| A4 | co2 10,000 |
| A5 | co2 15,000 |
| B2 (per year, years 1–50) | co2 500 |
| B4 events | year 20: co2 8,000; year 40: co2 8,000 |
| B5 event | year 25: co2 20,000, ch4_fossil 20 |
| C1, C2, C3 | co2 5,000, 4,000, 3,000 |
| C4 | co2 2,000, ch4 50 |

**Hand total, A1–A3:** co2 **250,000 kg**, ch4_fossil **300 kg**, n2o
**8 kg** (one amount, so no sum).

**Hand total, whole series:**

- co2: 289,000 (one-off modules) + 50 × 500 + 2 × 8,000 + 20,000 = **350,000 kg**
- ch4 **50 kg**, ch4_fossil 300 + 20 = **320 kg**, n2o **8 kg**.

## What the set covers

Units `m3`, `t`, `kg` and `m2`. One assembly (concrete) and two (timber,
steel). Every gas key and every one-off module. A B4 list with two events
(steel and totals), a B5 event (timber and totals), per-year B1 with a
negative value (concrete and topping), and per-year B2 in totals.
