---
title: "DLCA: Dynamic life cycle assessment for buildings in Python"
tags:
  - Python
  - life cycle assessment
  - dynamic LCA
  - buildings
  - embodied carbon
  - greenhouse gas
  - radiative forcing
authors:
  - name: Jay Arehart
    orcid: 0000-0002-9434-1783
    affiliation: 1
  # TODO(Jay): CITATION.cff and .zenodo.json also list Fatemah Khajah
  # (University of Colorado Boulder). JOSS asks for a complete author list,
  # and every co-author must agree to be listed. Add her here, or say why not.
affiliations:
  - name: "TODO(Jay): affiliation (none is recorded in the repository for Jay Arehart)"
    index: 1
# TODO(Jay): set to the submission date, in the form "9 October 2024".
date: 24 November 2026
bibliography: paper.bib
---

<!--
Draft skeleton for issue #102. Sections marked TODO(Jay) are Jay's to write.
This paper describes the software only: no case-study numbers and no research
findings (see AGENTS.md, "Data safety").
JOSS asks for 750-1750 words in all.
-->

# Summary

Buildings emit greenhouse gases over their whole life: when materials are
made and the building is built, every year it is used, when parts are
replaced, and at its end of life. A conventional life cycle assessment (LCA)
adds these emissions up as if they all happened at once, and weights each gas
with a single global warming potential. DLCA is a Python package that keeps
the timing. It takes the emissions of a building, assembly or material year by
year, follows each gas in the atmosphere, and computes the radiative forcing
and temperature change they cause. It reports cumulative global warming
impact (GWI) and global temperature change potential (GTP), each as a
dynamic, a sliding and a static series, so the timed and untimed results can
be compared on the same inputs. Climate parameters from the IPCC Fifth (AR5)
and Sixth (AR6) Assessment Reports ship with the package, with AR6 as the
default [@Myhre2013; @Forster2021].

# Statement of need

TODO(Jay). Prompts:

- What gap does DLCA fill? What can a building LCA practitioner or researcher
  not do, or not do reproducibly, without it?
- Who uses it: researchers, practitioners, students, tool builders (the web
  app planned in decision record 0005)?
- Which research questions does timing change the answer to (in general
  terms, with no unpublished results)?
- Why a Python package with JSON inputs rather than a spreadsheet?

# State of the field

TODO(Jay). Prompts:

- Which other tools or methods compute dynamic or time-adjusted LCA metrics,
  and how does DLCA differ from each (scope, climate model, building focus)?
- JOSS asks for a "build versus contribute" reason: why a new package rather
  than a contribution to an existing one?
- DLCA began as a Python port of the spreadsheet of @Cooper2020; say how the
  package relates to it.

# Software design

DLCA has two layers. The climate engine (`dlca.climate`) works on a yearly
emissions series of four keys (CO₂, non-fossil CH₄, fossil CH₄ and N₂O, in kg
per year) and has no knowledge of buildings. The inventory layer
(`dlca.inventory`) turns a building description into that series and then
calls the engine. Users who already have a yearly emissions series can call
the engine through `dlca.assess()`; users with a building call
`dlca.assess_building()`.

The public API is pure functions with JSON-serialisable inputs and outputs, so
the same calls work from a script, a notebook or a web backend. JSON Schemas
for both building input formats ship with the package. Climate parameters live
in packaged JSON files in which every value carries its unit and its source.
Every result records the package version and a fingerprint of the parameter
set that produced it, so a stored result says how it was made. From v1.0.0
the public names, the JSON formats and the numbers follow Semantic
Versioning: a patch release never moves an output number.

Science and design choices are written down as decision records in the
repository. Each one gives the choice, the alternatives considered and the
consequences, and the methodology page of the documentation links each
equation to its record and to the function that computes it.

# Functionality

**Climate engine.** CO₂ follows the four-pool impulse response of
@Joos2013. CH₄ and N₂O decay with one perturbation lifetime each. Forcing
uses effective radiative efficiencies that include the indirect effects of
CH₄ and N₂O. Fossil CH₄ is oxidised to CO₂ following @Boucher2009. With the
AR6 parameters, the carbon-cycle feedback of CH₄ and N₂O follows
@Gasser2017. Temperature uses the two-box climate response of each parameter
set [@Forster2021; @Smith2021]. Between whole years every quantity follows its
exact continuous solution, so for a single pulse the yearly results equal the
closed-form absolute GWP and GTP.

**Metrics.** For a chosen horizon, DLCA returns dynamic GWI and GTP (the
cumulative effect up to each year), sliding GWI and GTP (each emission
assessed up to a fixed end year), and static GWP and GTP (no timing), all in
kg CO₂-equivalent.

**Building inventory.** A building is entered either as whole-building totals
by EN 15978 life cycle module [@EN15978] or as assemblies of materials with
amounts per declared unit. `timeline()` places each module in time: product
and construction stages in year 0, use-stage modules in each year of the
study period, replacements and refurbishments in the years the user gives,
and end of life one year after the study period. `assess_building()` returns
the whole-building result and breakdowns by module, gas, material and
assembly, which add up to the total.

**Optional processes.** Biogenic carbon uptake can be instant, absent, or
spread over the regrowth period with the curve of @Cherubini2011. Concrete
carbonation during use and after demolition follows @Lagerblad2005 and
@Andersson2013. Future changes in emission factors for replacements and end
of life can be set as constant, linear or year-by-year trajectories.
Operational energy (module B6) can be entered by fuel, with packaged
electricity factors from US EPA eGRID2023 [@EPA2025eGRID], year-by-year
factors from Cambium 2024 by NLR (formerly NREL) [@Gagnon2025], fuel factors from the EPA GHG
Emission Factors Hub [@EPA2025Hub], or the user's own factors.

The documentation (<https://jayarehart.github.io/DLCA/>) has installation
instructions, a quick start, four tutorials that run on every build, a page
on the input formats, the methodology and the API reference.

# Quality control

The test suite has four kinds of tests. Unit tests check single functions
and classes. Analytic tests compare results with closed-form solutions and
published IPCC values. Reference tests compare results, year by year, with
seven emission cases computed by the spreadsheet of @Cooper2020; since DLCA
began as a port of that spreadsheet, these check the port rather than the
physics. Property-based tests, written with Hypothesis, check invariants that
must hold for any valid input, such as the breakdowns adding up to the total.

Continuous integration runs the tests on Linux (Python 3.10 and 3.13), macOS
and Windows (Python 3.13), and also runs the linter, validates the citation
metadata, and builds and installs the wheel. The documentation is built with
`mkdocs build --strict`, which executes the tutorial notebooks and fails if a
cell raises, a link is broken, or the API reference misses a public name.

Changes to equations, parameters, timing or reference data follow a stricter
process: a decision by the maintainer before code is written, a check whose
expected value comes from outside the code, and a run with a deliberate
mistake to show that the check can fail.

# Research impact statement

TODO(Jay). Prompts:

- JOSS screens for research impact that has already happened, at least use by
  the developers. Where has DLCA been used (published or in-review work,
  theses, courses)? Cite only what is public.
- Are any related papers published, in review or about to be submitted? JOSS
  asks authors to say so.

# AI usage disclosure

TODO(Jay). JOSS requires this section. Prompts:

- Which AI tools and models were used, and for what: code, tests,
  documentation, this paper? (The repository's `AGENTS.md` sets the rules for
  AI agents working in it.)
- What kind of help, and how much?
- Confirm that people reviewed, edited and validated the AI-assisted work and
  made the core design decisions.

# Acknowledgements

TODO(Jay). Prompts:

- Funding, with a statement on whether the funder had any role.
- Contributors and colleagues, including the internal reviewers of v1.0.0rc1.
- The authors of the spreadsheet of @Cooper2020, which DLCA began as a port
  of.

# References
