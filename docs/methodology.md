# Methodology

This page says what DLCA computes, in the order the calculation runs: from a
yearly emissions series, through the gases in the air, to forcing,
temperature and the reported metrics. The second half covers how a building
input becomes that yearly series. Each equation or rule links to the
decision record that sets it and to the function that computes it.

The page describes the code as it is. Where a record and this page seem to
differ, the record and the code decide. Please report the difference as an
issue.

## 1. Emissions input and the time grid

The engine works on whole years. Year 0 is the first entry, and every series
has one value per year. An emission $E_g[k]$ is the mass in kg of key $g$
emitted in year $k$. It is not kg of carbon. There are four keys
([`EMISSION_KEYS`][dlca.climate.EMISSION_KEYS]):

| Key | Gas | Note |
|---|---|---|
| `co2` | CO₂ | Negative values are uptake |
| `ch4` | non-fossil CH₄ | Not oxidised to CO₂ in the engine, and given no carbon credit ([0010](decisions/0010-carbon-cycle-feedback.md), C8) |
| `ch4_fossil` | fossil CH₄ | Adds to the CH₄ in the air, and is also oxidised to CO₂ (section 2) |
| `n2o` | N₂O | |

An emission in year $k$ enters the air in full at the start of year $k$.
Between whole years, every quantity follows its exact continuous solution.
So for a single pulse, the yearly results equal the closed-form values at
whole years (sections 3 and 5). Series go into
[`dlca.assess()`][dlca.result.assess], which runs every step below with one
parameter set and returns a [`Result`][dlca.result.Result]
([0008](decisions/0008-assess-entry-point-and-result.md)).

**Parameter sets.** DLCA ships two climate parameter sets, IPCC AR5 and IPCC
AR6, and AR6 is the default
([0002](decisions/0002-ar5-and-ar6-parameter-sets.md)). Each value in the
packaged JSON files carries its unit and its source
([0007](decisions/0007-climate-parameter-files.md)). Load a set with
[`get_parameters()`][dlca.parameters.get_parameters]. It returns a
[`ClimateParameters`][dlca.parameters.ClimateParameters]. Every result
records the set's name and fingerprint. The symbols below
($a_p$, $\tau_p$, $\tau_g$, $q_i$, $d_i$ and so on) are fields of that object.

## 2. Gases in the air (burden)

[`burden()`][dlca.climate.burden] gives the mass of each gas in the air in
each year, in kg. CH₄ and N₂O decay with one perturbation lifetime $\tau_g$
(AR5: 12.4 and 121 yr; AR6: 11.8 and 109 yr):

$$
m_g[k] = E_g[k] + m_g[k-1]\, e^{-1/\tau_g}
       = \sum_{j \le k} E_g[j]\, e^{-(k-j)/\tau_g}.
$$

The CH₄ mass $m_{\mathrm{CH_4}}$ holds `ch4` and `ch4_fossil` together.

CO₂ follows the four-pool impulse response of Joos et al. (2013), with the same
fractions $a_0 \ldots a_3$ and time constants $\tau_1 \ldots \tau_3$ in both
sets. Pool 0 is permanent:

$$
m_{\mathrm{CO_2},0}[k] = a_0 \sum_{j \le k} E'_{\mathrm{CO_2}}[j], \qquad
m_{\mathrm{CO_2},p}[k] = a_p \sum_{j \le k} E'_{\mathrm{CO_2}}[j]\, e^{-(k-j)/\tau_p}
\quad (p = 1, 2, 3).
$$

$E'_{\mathrm{CO_2}}$ is the CO₂ input plus two kinds of CO₂ that form in the
air: CO₂ from fossil CH₄ oxidation, $O[k]$ (below), and CO₂ from the
carbon-cycle feedback, $C_{\mathrm{cc}}[k]$ (section 7):

$$
E'_{\mathrm{CO_2}}[k] = E_{\mathrm{co2}}[k] + O[k] + C_{\mathrm{cc}}[k].
$$

**Fossil CH₄ oxidation**
([0011](decisions/0011-fossil-ch4-oxidation-residual.md)). The fossil CH₄
removed during year $k-1 \to k$ becomes CO₂ in year $k$:

$$
O[k] = Y \cdot \frac{44}{16} \cdot m_{\mathrm{fossil}}[k-1]\,
       \bigl(1 - e^{-1/\tau_{\mathrm{CH_4}}}\bigr), \qquad k \ge 1,
$$

where $m_{\mathrm{fossil}}$ is the CH₄ mass from `ch4_fossil` alone. $Y$ is the
yield in mol CO₂ per mol CH₄,
[`fossil_ch4_co2_yield()`][dlca.parameters.ClimateParameters.fossil_ch4_co2_yield]:
0.5 in AR5 and 0.75 in AR6 ([0007](decisions/0007-climate-parameter-files.md),
D4). The mass ratio 44/16 is
[`CO2_PER_CH4_MASS_RATIO`][dlca.climate.CO2_PER_CH4_MASS_RATIO]. So the CO₂
forms as the CH₄ decays, with the CH₄ perturbation lifetime. This is the
closed form of Boucher et al. (2009). Record 0011 keeps this method, and does
not use the 9.70-yr kernel that reproduces an IPCC Chapter 7 data file. At
GWP₁₀₀ the oxidation term is 1.866 × AGWP₁₀₀(CO₂) in DLCA, against 1.908 in
that file (AR6). Record 0011 breaks down the gap.

## 3. Radiative forcing

[`specific_forcing()`][dlca.climate.specific_forcing] gives the forcing per kg
of each gas in the air, in W m⁻² kg⁻¹. It converts a radiative efficiency
$\mathrm{RE}^{\mathrm{eff}}_g$, in W m⁻² ppb⁻¹, to a per-kg value:

$$
A_g = \mathrm{RE}^{\mathrm{eff}}_g \cdot \frac{M_{\mathrm{air}}}{M_g} \cdot
      \frac{10^9}{m_{\mathrm{atm}}},
$$

with $M$ the molar masses and $m_{\mathrm{atm}}$ the mass of the atmosphere.
The effective radiative efficiency
([`effective_radiative_efficiency()`][dlca.parameters.ClimateParameters.effective_radiative_efficiency])
holds the indirect effects of CH₄ and N₂O
([0007](decisions/0007-climate-parameter-files.md)):

| Gas | AR5 (multiplicative) | AR6 (additive) |
|---|---|---|
| CO₂ | $\mathrm{RE}_{\mathrm{CO_2}} \cdot s$, with the Cooper et al. scale factor $s = 0.99746898$ (D5) | $\mathrm{RE}_{\mathrm{CO_2}}$ ($s = 1$) |
| CH₄ | $\mathrm{RE}_{\mathrm{CH_4}}\,(1 + f_{\mathrm{O_3}} + f_{\mathrm{H_2O}})$, with $f_{\mathrm{O_3}} = 0.5$, $f_{\mathrm{H_2O}} = 0.15$ | $\mathrm{RE}_{\mathrm{CH_4}} + \mathrm{RE}_{\mathrm{O_3}} + \mathrm{RE}_{\mathrm{H_2O}}$ |
| N₂O | $\mathrm{RE}_{\mathrm{N_2O}} + c\, \mathrm{RE}^{\mathrm{eff}}_{\mathrm{CH_4}}$, with $c = -0.36$ ppb CH₄ per ppb N₂O | $\mathrm{RE}_{\mathrm{N_2O}} + \mathrm{RE}_{\mathrm{O_3}} + c\, \mathrm{RE}^{\mathrm{eff}}_{\mathrm{CH_4}}$, with $c = -1.7$ |

The AR6 radiative efficiencies are unrounded values derived by the method of
the IPCC Chapter 7 code (0007, D1).

[`forcing()`][dlca.climate.forcing] gives the forcing at the start of each
year, just after that year's pulse, as $F_g[k] = A_g\, m_g[k]$ (for CO₂, the
sum over the four pools). Between whole years each pool decays
exponentially, so the forcing integrated over year $j \to j+1$ is exact:

$$
\int_j^{j+1} F\,dt = \sum_p A\, m_p[j]\, g_p, \qquad
g_p = \begin{cases} 1 & \text{permanent CO}_2 \text{ pool}, \\
\tau_p\,\bigl(1 - e^{-1/\tau_p}\bigr) & \text{otherwise.} \end{cases}
$$

The integrated forcing $I[t]$ is the sum of these terms over years
$0 \ldots t-1$, so $I[0] = 0$.

**Absolute GWP.** [`agwp()`][dlca.climate.agwp] gives the forcing of a 1 kg
pulse integrated to horizon $H$, in closed form:

$$
\mathrm{AGWP}_{\mathrm{CO_2}}(H) = A_{\mathrm{CO_2}} \Bigl( a_0 H +
  \sum_{p=1}^{3} a_p \tau_p \bigl(1 - e^{-H/\tau_p}\bigr) \Bigr), \qquad
\mathrm{AGWP}_g(H) = A_g\, \tau_g \bigl(1 - e^{-H/\tau_g}\bigr)
\quad (g = \mathrm{CH_4}, \mathrm{N_2O}).
$$

For `ch4_fossil`, the oxidised CO₂ is added:

$$
\mathrm{AGWP}_{\mathrm{fossil}}(H) = \mathrm{AGWP}_{\mathrm{CH_4}}(H) +
  Y \cdot \frac{44}{16} \int_0^H \frac{1}{\tau_{\mathrm{CH_4}}}
  e^{-u/\tau_{\mathrm{CH_4}}}\, \mathrm{AGWP}_{\mathrm{CO_2}}(H - u)\, du,
$$

which the code evaluates in closed form. With the AR6 set, the CH₄ and N₂O
values also hold the carbon-cycle feedback term (section 7).

## 4. Global warming impact (GWI)

[`gwi()`][dlca.climate.gwi] returns three series in kg CO₂-equivalent, each
divided by $\mathrm{AGWP}_{\mathrm{CO_2}}(H)$ from the same parameter set
([`GWI`][dlca.climate.GWI]).

**Dynamic** GWI is the cumulative forcing to year $t$:

$$
\mathrm{GWI}_{\mathrm{dyn}}[t] = \frac{\sum_g I_g[t]}{\mathrm{AGWP}_{\mathrm{CO_2}}(H)}.
$$

For a 1 kg pulse in year 0, this is
$\mathrm{AGWP}_g(t) / \mathrm{AGWP}_{\mathrm{CO_2}}(H)$ at every whole year $t$.

**Sliding** GWI is the forcing up to the fixed year $H$ from the emissions of
years $0 \ldots t$. An emission in year $k$ gets the remaining horizon
$H_k = \max(H - k, 0)$:

$$
\mathrm{GWI}_{\mathrm{sl}}[t] = \frac{1}{\mathrm{AGWP}_{\mathrm{CO_2}}(H)}
  \sum_{k \le t} \sum_{g} E^{\mathrm{sl}}_g[k]\, \mathrm{AGWP}^{*}_g(H_k),
$$

where $g$ runs over CO₂, CH₄ and N₂O, and $\mathrm{AGWP}^{*}$ is the AGWP
without the carbon-cycle feedback. $E^{\mathrm{sl}}_{\mathrm{CO_2}}$ is
$E'_{\mathrm{CO_2}}$ of section 2, $E^{\mathrm{sl}}_{\mathrm{CH_4}}$ is `ch4`
plus `ch4_fossil`, and $E^{\mathrm{sl}}_{\mathrm{N_2O}}$ is `n2o`. CO₂ from fossil CH₄ oxidation
and from the feedback counts as CO₂ emitted in the year it forms, through
$E'_{\mathrm{CO_2}}$. For a whole-number $H$,
$\mathrm{GWI}_{\mathrm{sl}}[t] = \mathrm{GWI}_{\mathrm{dyn}}[H]$ for
$t \ge H$. Anything emitted in year $H$ or later counts zero here.

**Static** GWI is the static GWP of section 6.

For a fossil CH₄ pulse, the whole-year sliding value differs from the
closed form of section 3 by 0.02% to 0.05% (AR5 and AR6, $H$ = 20 and 100),
because the oxidised CO₂ enters in whole years.

## 5. Temperature change and GTP

[`temperature()`][dlca.climate.temperature] uses the two-box climate
response of the parameter set: sensitivities $q_1, q_2$ in K (W m⁻²)⁻¹ and
response times $d_1, d_2$ in years. Box $i$ steps exactly from one whole year
to the next, on the forcing of each component $p$ (each CO₂ pool, CH₄, N₂O)
decaying from its value at the start of the year:

$$
T_i[j+1] = T_i[j]\, e^{-1/d_i} + \sum_p F_p[j]\, h(\tau_p, d_i, q_i, 1), \qquad
T[t] = T_1[t] + T_2[t], \qquad T[0] = 0,
$$

where $h$ is the box's response at time $t$ to a unit forcing that starts at 0:

$$
h(\tau, d, q, t) = \begin{cases}
q\,\bigl(1 - e^{-t/d}\bigr) & \text{constant forcing (permanent CO}_2\text{ pool)}, \\[4pt]
\dfrac{q\,\tau}{\tau - d}\bigl(e^{-t/\tau} - e^{-t/d}\bigr) & \text{forcing decaying with } \tau.
\end{cases}
$$

**Absolute GTP.** [`agtp()`][dlca.climate.agtp] gives the temperature change at
$H$ from a 1 kg pulse, in closed form:

$$
\mathrm{AGTP}_g(H) = A_g \sum_p a_p \sum_{i=1}^{2} h(\tau_p, d_i, q_i, H),
$$

with the four CO₂ pools for CO₂ ($a_0$ with constant forcing), and one
component ($a = 1$, $\tau_g$) for CH₄ and N₂O. For `ch4_fossil`, the oxidised
CO₂ is added as for the AGWP, with $\mathrm{AGTP}_{\mathrm{CO_2}}(H-u)$ in the
integral. For a pulse, $T[t]$ equals $\mathrm{AGTP}_g(t)$ at whole years.

[`gtp()`][dlca.climate.gtp] returns dynamic, sliding and static series
([`GTP`][dlca.climate.GTP]), each divided by $\mathrm{AGTP}_{\mathrm{CO_2}}(H)$:
dynamic is $T[t] / \mathrm{AGTP}_{\mathrm{CO_2}}(H)$; sliding is the GWI sliding
formula with $\mathrm{AGTP}^{*}$ in place of $\mathrm{AGWP}^{*}$; static uses
$\mathrm{GTP}_H$ in place of $\mathrm{GWP}_H$ (section 6).

The AR6 climate response uses $q_2 = 0.313998$, the value that reproduces the
published AGTP₁₀₀(CO₂) = 3.95 × 10⁻¹⁶ K kg⁻¹. It differs from the
Supplementary Material's two-layer model
([0007](decisions/0007-climate-parameter-files.md), D2).

## 6. Static GWP, for comparison

[`static_gwp()`][dlca.climate.static_gwp] ignores timing. For each key it
multiplies the cumulative net emissions to year $t$ by that key's metric
value, and sums over the keys ([`StaticGWP`][dlca.climate.StaticGWP]):

$$
\mathrm{GWP}_{g,H} = \frac{\mathrm{AGWP}_g(H)}{\mathrm{AGWP}_{\mathrm{CO_2}}(H)}, \qquad
\mathrm{GWI}_{\mathrm{st}}[t] = \sum_g \mathrm{GWP}_{g,H} \sum_{k \le t} E_g[k].
$$

The factor for `ch4_fossil` holds its oxidised CO₂, and with AR6 the CH₄ and
N₂O factors hold the carbon-cycle feedback. The static GTP in
[`gtp()`][dlca.climate.gtp] is the same with
$\mathrm{GTP}_{g,H} = \mathrm{AGTP}_g(H) / \mathrm{AGTP}_{\mathrm{CO_2}}(H)$.

The default AR6 set gives CH₄ GWP₁₀₀ = 28.02 and N₂O GWP₁₀₀ = 274.4
([0010](decisions/0010-carbon-cycle-feedback.md)). AR5 gives 28.46 and 264.8,
without carbon-cycle feedback.

## 7. Carbon-cycle feedback

When CH₄ and N₂O warm the climate, land and ocean sinks take up less carbon,
so extra CO₂ stays in the air
([0010](decisions/0010-carbon-cycle-feedback.md)). The Joos et al. CO₂
response already holds this feedback for CO₂, so only CH₄ and N₂O drive it.
DLCA uses the response of Gasser et al. (2017), Table 1, "Mean" row, in the
AR6 set only. The switch is
[`ClimateParameters.carbon_cycle_feedback`][dlca.parameters.ClimateParameters]:
`true` for AR6 and `false` for AR5. Turning it on for AR5 raises an error.

The carbon the sinks release up to time $t$ is

$$
C(t) = \gamma \sum_{i=1}^{3} w_i \int_0^t T_{\mathrm{CH_4+N_2O}}(s)\, e^{-(t-s)/\tau_i}\, ds,
$$

with $\gamma = 3.015$ GtC yr⁻¹ K⁻¹, weights $w = (0.6368, 0.3322, 0.0310)$,
time constants $\tau = (2.376, 30.14, 490.1)$ yr, and $T_{\mathrm{CH_4+N_2O}}$
the temperature change from the CH₄ and N₂O in the air. CO₂ from fossil CH₄
and the feedback CO₂ itself do not drive it, and there is no iteration.

In [`burden()`][dlca.climate.burden], the integral is taken over whole years
by the trapezoid rule (0010, C4). With $r_i = e^{-1/\tau_i}$:

$$
\begin{aligned}
S_i[k] &= S_i[k-1]\, r_i + \tfrac{1}{2}\bigl(T[k-1]\, r_i + T[k]\bigr), \\
C[k] &= \gamma \sum_i w_i S_i[k], \\
C_{\mathrm{cc}}[k] &= \bigl(C[k] - C[k-1]\bigr)\, \frac{M_{\mathrm{CO_2}}}{M_{\mathrm{C}}}.
\end{aligned}
$$

$C_{\mathrm{cc}}[k]$ is added to year $k$'s CO₂ (`Burden.ccf_co2`), so forcing,
temperature and the dynamic metrics include it with no further change.
[`agwp()`][dlca.climate.agwp] and [`agtp()`][dlca.climate.agtp] add the exact
closed form of the same convolutions. Its rate is
$\gamma\,(T * r_F)$, with $r_F(t) = \delta(t) \sum_i w_i - \sum_i (w_i/\tau_i)\, e^{-t/\tau_i}$.
DLCA uses this exact value rather than the IPCC code's 0.1-yr numerical
step, so its values differ from the printed IPCC ones. DLCA gives CH₄ GWP₁₀₀ 28.02 against the printed 27.9 in Table 7.SM.7 (0010,
C2). For a pulse, the whole-year dynamic GWI and GTP differ from the closed form
by up to 8.2 × 10⁻⁴ (N₂O GWP₂₀).

## 8. Minimum horizon

[`gwi()`][dlca.climate.gwi], [`gtp()`][dlca.climate.gtp],
[`static_gwp()`][dlca.climate.static_gwp] and
[`assess()`][dlca.result.assess] refuse a horizon below
[`MIN_HORIZON`][dlca.climate.MIN_HORIZON] = 10⁻⁶ yr with a `ValueError`
([0012](decisions/0012-minimum-horizon.md)). Below about 10⁻⁹ yr the closed
forms lose precision; at 10⁻⁶ yr their relative error is at most about
3 × 10⁻⁹. [`agwp()`][dlca.climate.agwp] and [`agtp()`][dlca.climate.agtp]
still accept any $H \ge 0$, because the sliding metrics evaluate them at the
remaining horizons $H_k$.

## 9. Building inventory and module timing

A building is entered in one of two schemas
([0013](decisions/0013-inventory-schema.md)):
[`BuildingTotals`][dlca.inventory.BuildingTotals] holds whole-building
amounts by EN 15978 module, and
[`BuildingInventory`][dlca.inventory.BuildingInventory] holds assemblies of
materials, each with amounts per declared unit. A material's emitted amount
is its `quantity` times the per-unit amount, with no unit conversion. Module D
is not part of the tool. Replacements (B4) and refurbishments (B5) are dated
events the user enters, not values derived from a service life. See
[Inputs](inputs.md) for the fields.

[`timeline()`][dlca.inventory.timeline] places the amounts in time
([0014](decisions/0014-module-timing.md)). With RSP the `study_period`:

| Module | Year(s) |
|---|---|
| A1-A3, A4, A5 | 0 |
| B1, B2, B3, B6, B7 | each of 1 … RSP |
| B4, B5 events | the event's year, 1 … RSP |
| C1, C2, C3, C4 | RSP + 1, as one pulse |

Amounts in the same year add. The series runs over years
$0 \ldots \mathrm{RSP} + 1 + H$ ($\mathrm{RSP} + H + 2$ values), so the
end-of-life pulse gets a full horizon $H$. End of life falls one year after
the study period. EN 15978 is a static method and gives no calendar year to
any module, so these years are DLCA's convention.

## 10. Roll-up and breakdown

[`assess_building()`][dlca.inventory.assess_building] calls
[`timeline()`][dlca.inventory.timeline], then runs
[`assess()`][dlca.result.assess] on the whole building and again on each row
of four breakdowns ([0015](decisions/0015-building-roll-up-and-breakdown.md)):
by module, by gas (input key), by material and by assembly (the last two for a
`BuildingInventory` only). The result is a
[`BuildingResult`][dlca.inventory.BuildingResult], and each row is a
[`Metrics`][dlca.inventory.Metrics] with six series: GWI and GTP, each
dynamic, sliding and static.

The engine is linear in the emissions, so in each breakdown the rows add up
to the total, within $10^{-9} \sum |\text{row}|$ in every year and series. A
gas row holds what its input key causes: the `ch4_fossil` row includes its
oxidised CO₂, and the CH₄ and N₂O rows include their feedback CO₂.

The sliding series give an emission in year $k$ the horizon $\max(H - k, 0)$.
When $\mathrm{RSP} + 1 \ge H$, the end-of-life pulse counts zero there. Rows
with an input emission in year $H$ or later are listed in
`BuildingResult.sliding_incomplete`, and `assess_building()` warns once.

## 11. Biogenic carbon

A material, a `BuildingTotals`, or a B4 or B5 event may carry a
[`Biogenic`][dlca.inventory.Biogenic] field: the carbon held in the product,
as kg CO₂, and how it regrows ([0016](decisions/0016-biogenic-carbon.md)).
The uptake is negative `co2` in its own timeline part, module
[`biogenic-uptake`][dlca.inventory.UPTAKE_MODULE], starting in the product's
year $s$ (0, or the event's year):

- `"instant"`: all in year $s$.
- `"none"`: no uptake.
- `"gaussian"`: the Cherubini et al. (2011) curve with $\mu = r/2$ and
  $\sigma = \mu/2$, for rotation $r$ (below).

For `"gaussian"`, the share in year $s + k$, $k \ge 0$, is the normal density
integrated over $[k, k+1)$, divided by its integral over $[0, \infty)$, with
$\Phi$ the standard normal distribution function:

$$
\text{share}_k = \frac{\Phi\bigl(\frac{k+1-\mu}{\sigma}\bigr) - \Phi\bigl(\frac{k-\mu}{\sigma}\bigr)}
  {1 - \Phi\bigl(\frac{-\mu}{\sigma}\bigr)}.
$$

Uptake after the series end is cut, with a
[`BiogenicCarbonWarning`][dlca.inventory.BiogenicCarbonWarning] when more
than 10⁻⁹ of an item's uptake is lost.

The tool writes no release. Users enter it in C1–C4 (or a B4 event) as `co2`
and non-fossil `ch4`. Because the engine never oxidises non-fossil `ch4`,
its carbon is counted once by taking it off the uptake: per material, the
uptake is the declared carbon of items with regrowth other than `"none"`, less
$44.01/16.043$ kg CO₂ per kg of `ch4` in C1–C4 and in B4/B5 events, and never
below zero. [`biogenic_balance()`][dlca.inventory.biogenic_balance] reports
the declared, released and stored carbon. Nothing is emitted for storage.

## 12. Concrete carbonation

A material may carry a [`Carbonation`][dlca.inventory.Carbonation] field
([0017](decisions/0017-concrete-carbonation.md)). The method is Lagerblad
(2005). The carbonation depth after $t$ years is $d = k\sqrt{t}$ mm, where $k$
is Lagerblad's Table 2 value (strength class × exposure) times the cover
factor of Table 3 times `binder_factor`. The uptake per m³ of carbonated
concrete is

$$
a = \alpha \cdot c_{\mathrm{cem}} \cdot x_{\mathrm{CaO}} \cdot \frac{44.01}{56.077}
    \quad [\mathrm{kg\ CO_2\ m^{-3}}],
$$

with $\alpha$ the `degree_of_carbonation` (default 0.75), $c_{\mathrm{cem}}$ the
Portland `cement` content in kg m⁻³, and $x_{\mathrm{CaO}}$ the `cao_share`
(default 0.65). Following Andersson et al. (2013, eq. 2), the carbonated volume per declared
unit is $V_c(t) = \min\bigl(\sum_s A_s d_s / 1000,\ V\bigr)$ over the surfaces
$s$, and the uptake is $U(t) = a\,V_c(t)$.

| Part (module) | Years | Uptake in year $y$ |
|---|---|---|
| [`carbonation-uptake`][dlca.inventory.CARBONATION_UPTAKE_MODULE] | $c + 1 \ldots e$ | $U(y - c) - U(y - c - 1)$ |
| [`carbonation-eol`][dlca.inventory.CARBONATION_EOL_MODULE] | $\mathrm{RSP} + 1 \ldots \mathrm{RSP} + n$ | $a\,V_u\,\bigl(f(j+1) - f(j)\bigr)$, with $j = y - \mathrm{RSP} - 1$ |

Here $c$ is the casting year (0, or a B4 event that carries `carbonation`),
and $e$ is RSP, or the year of the replacing B4 event. In year RSP + 1 the
remaining volume $V_u = V - V_c(\mathrm{RSP} - c)$ of the last item is crushed
into spheres of radius $r$. Their carbonated share after $j$ years is
$f(j) = 1 - \bigl((r - k_e\sqrt{j})/r\bigr)^3$, and 1 once $k_e\sqrt{j} \ge r$.
$k_e$ is the Table 2 value for `exposed` at the same strength class, times
`binder_factor`, with no cover factor. All uptake is negative `co2`.

Record 0017 lists the limits. The open-air stockpile may overstate
end-of-life uptake (Andersson et al. found about 11% of the theoretical
maximum in practice). Concrete replaced by a B4 event gets no stockpile
uptake.

## 13. Emission-factor trajectories

A building may carry a `b4_c_trajectory`, a multiplier $m(y)$ on study years
with $m(0) = 1$ ([0018](decisions/0018-emission-factor-trajectories.md)). It
is a [`Trajectory`][dlca.inventory.Trajectory] of one of three kinds:

| Kind | $m(y)$ |
|---|---|
| [`constant`][dlca.inventory.ConstantTrajectory] | 1 |
| [`linear`][dlca.inventory.LinearTrajectory] | $1 - (1 - \text{target})\,\min(y, y_T)/y_T$, with $y_T$ the `target_year` |
| [`series`][dlca.inventory.SeriesTrajectory] | `values[y]`, holding the last value after the end |

[`timeline()`][dlca.inventory.timeline] multiplies the fossil gases (`co2`,
`ch4_fossil`, `n2o`) of each B4 event by $m(\text{event year})$, and those of
C1–C4 by $m(\mathrm{RSP} + 1)$. Non-fossil `ch4` is never scaled, and nor
are A1–A5, B1–B3, B5, B7, biogenic uptake or carbonation. On a biogenic item
(a material, or a `BuildingTotals`, that has a `biogenic` field itself or on
any of its B4 or B5 events), the `co2` of its B4 and C1–C4 amounts is left as
entered, because it holds the release of stored carbon
([0020](decisions/0020-trajectories-for-biogenic-items.md)). So the
trajectory may overstate, never understate, those items' emissions. A
trajectory scales the whole fossil amount, process emissions included.
Choosing a trajectory that fits the materials is up to the user.

## 14. Operational energy (B6)

B6 can be given as energy use by fuel, as a list of
[`EnergyUse`][dlca.inventory.EnergyUse] lines
([0019](decisions/0019-operational-energy-b6.md)). In each year
$y = 1 \ldots \mathrm{RSP}$, a line adds

$$
\text{B6}_g(y) = \text{amount} \times \text{factor}_g(y) \times m(y),
$$

with $m$ the line's own trajectory, applied to the fossil gases only. The
factor sources are:

- **eGRID2023 Rev 2** (US EPA): annual total output emission rates by
  subregion or state, as published in lb/MWh, converted with
  1 lb = 0.45359237 kg and 1 MWh = 3600 MJ.
- **EPA GHG Emission Factors Hub 2025**, Table 1: natural gas 53.06 kg CO₂,
  1.0 g CH₄ and 0.10 g N₂O per mmBtu; fuel oil No. 2 73.96 kg CO₂, 3.0 g CH₄
  and 0.60 g N₂O per mmBtu.
- **Cambium 2024** (NLR), year by year, by GEA region and scenario
  ([0021](decisions/0021-cambium-b6-factors.md)). The calendar-year series is
  NLR's eGRID-based historical values (2014–2023), a straight line from 2023 to
  Cambium 2030 (Cambium's 2025 point is not used), Cambium 2030–2050 with
  straight lines between the 5-year points, and the end values held. B6 in
  study year $y$ uses the factor of calendar year `year_zero` + $y$, and a
  non-constant trajectory is refused on a Cambium line.
- A user `factor`: one set of kg per unit for every year, or a series by
  study year that holds its last value.

[`to_study_years()`][dlca.inventory.to_study_years] turns calendar-year values
into study years in the same way: a straight line between given years, with
the end values held. CH₄ from the packaged factors is fossil (`ch4_fossil`).
The packaged factors cover combustion and generation only. They include no
transmission and distribution losses and no upstream emissions, so they
understate B6, most of all for natural gas.

## 15. Stability of results

From v1.0.0, DLCA follows Semantic Versioning for its public names, its JSON
formats and its numbers ([0022](decisions/0022-public-api-and-stability-promise.md)).
A patch release never moves an output number, beyond
$\max(10^{-12}|x|, 10^{-15})$ in its unit. A change that moves numbers (a
science change, a bug fix, or a corrected source value) is at least a minor
release, with a decision record or issue and a "Numbers changed" entry in the
changelog. Every result records `dlca_version` and the parameter set's
fingerprint, so a stored result says which release and parameters made it.

## References

- Andersson, R., Fridh, K., Stripple, H., Häglund, M. (2013). Calculating CO₂
  uptake for existing concrete structures during and after service life.
  *Environ. Sci. Technol.* 47, 11625–11633.
  [doi:10.1021/es401775w](https://doi.org/10.1021/es401775w).
- Boucher, O., Friedlingstein, P., Collins, B., Shine, K. P. (2009). The
  indirect global warming potential and global temperature change potential due
  to methane oxidation. *Environ. Res. Lett.* 4, 044007.
  [doi:10.1088/1748-9326/4/4/044007](https://doi.org/10.1088/1748-9326/4/4/044007).
- Cherubini, F., Peters, G. P., Berntsen, T., Strømman, A. H., Hertwich, E.
  (2011). CO₂ emissions from biomass combustion for bioenergy: atmospheric
  decay and contribution to global warming. *GCB Bioenergy* 3(5), 413–426.
  [doi:10.1111/j.1757-1707.2011.01102.x](https://doi.org/10.1111/j.1757-1707.2011.01102.x).
- Cooper, S. J. G., Green, R., Hattam, L., Röder, M., Welfle, A., McManus, M.
  (2020). Exploring temporal aspects of climate-change effects due to
  bioenergy. *Biomass and Bioenergy* 142, 105778.
  [doi:10.1016/j.biombioe.2020.105778](https://doi.org/10.1016/j.biombioe.2020.105778).
- EN 15978:2011. *Sustainability of construction works: assessment of
  environmental performance of buildings, calculation method.*
- Forster, P., et al. (2021). The Earth's energy budget, climate feedbacks and
  climate sensitivity. In *Climate Change 2021: The Physical Science Basis*
  (IPCC AR6 WG1), Chapter 7, pp. 923–1054, and its Supplementary Material.
  [doi:10.1017/9781009157896.009](https://doi.org/10.1017/9781009157896.009).
- Gagnon, P., et al. (2025). *Cambium 2024 Scenario Descriptions and
  Documentation.* National Renewable Energy Laboratory.
  <https://docs.nlr.gov/docs/fy25osti/93005.pdf>. Data: Cambium 2024,
  <https://scenarioviewer.nlr.gov/>.
- Gasser, T., et al. (2017). Accounting for the climate–carbon feedback in
  emission metrics. *Earth Syst. Dynam.* 8, 235–253.
  [doi:10.5194/esd-8-235-2017](https://doi.org/10.5194/esd-8-235-2017).
- Joos, F., et al. (2013). Carbon dioxide and climate impulse response
  functions for the computation of greenhouse gas metrics: a multi-model
  analysis. *Atmos. Chem. Phys.* 13, 2793–2825.
  [doi:10.5194/acp-13-2793-2013](https://doi.org/10.5194/acp-13-2793-2013).
- Lagerblad, B. (2005). *Carbon dioxide uptake during concrete life cycle:
  state of the art.* CBI report 2:2005, Swedish Cement and Concrete Research
  Institute.
- Meinshausen, M., et al. (2020). The shared socio-economic pathway (SSP)
  greenhouse gas concentrations and their extensions to 2500. *Geosci. Model
  Dev.* 13, 3571–3605.
  [doi:10.5194/gmd-13-3571-2020](https://doi.org/10.5194/gmd-13-3571-2020).
- Myhre, G., et al. (2013). Anthropogenic and natural radiative forcing. In
  *Climate Change 2013: The Physical Science Basis* (IPCC AR5 WG1), Chapter 8,
  pp. 659–740, and its Supplementary Material.
  [doi:10.1017/CBO9781107415324.018](https://doi.org/10.1017/CBO9781107415324.018).
- Smith, C. J., et al. (2021). IPCC-WG1/Chapter-7 code.
  [doi:10.5281/zenodo.5211357](https://doi.org/10.5281/zenodo.5211357).
- US EPA (2025). Emissions & Generation Resource Integrated Database (eGRID),
  2023, Revision 2. <https://www.epa.gov/egrid>.
- US EPA (2025). GHG Emission Factors Hub, January 2025.
  <https://www.epa.gov/system/files/documents/2025-01/ghg-emission-factors-hub-2025.pdf>.
