# DLCA

Dynamic life cycle assessment (DLCA) for buildings.

DLCA models the greenhouse-gas emissions of buildings, assemblies and
materials as they occur over time, rather than lumping them into a single
point in time. It reports cumulative global warming impact (GWI) and global
temperature change potential (GTP) over the chosen study period.

## Status

Version 0.5.0, working towards 1.0. The climate engine, building inventory,
biogenic carbon, concrete carbonation and operational energy are in place.
The public API may still change before 1.0; the [changelog](changelog.md)
lists every change, and the [roadmap](roadmap.md) shows what is left.

Releases are published on [GitHub](https://github.com/jayarehart/DLCA/releases)
only. DLCA is not on PyPI, so `pip install dlca` will not find it. See
[Install](install.md).

## Where to go next

- [Install](install.md): from a release tag, a release wheel or source.
- [Quick start](quickstart.md): assess an emission series, then a building.
- [Inputs](inputs.md): the two building input schemas, as JSON Schema.
- [API reference](api/index.md): every public name, with its docstring.
- [Decision records](decisions/README.md): why the science and the API are
  the way they are.
- [Citing](citing.md): how to cite DLCA.

## License

DLCA's code is released under the
[MIT License](https://github.com/jayarehart/DLCA/blob/main/LICENSE).

!!! warning "Cambium data are not MIT"

    Two packaged data files, `cambium2024_gea_aer_gen_c.csv` and
    `cambium2024_gea_historical.csv`, are extracts of the Cambium 2024 data
    from the National Laboratory of the Rockies (formerly NREL). They are not
    under the MIT License. They carry NLR's own terms, including a credit
    requirement. Read
    [the notice](https://github.com/jayarehart/DLCA/blob/main/src/dlca/data/CAMBIUM_NOTICE.md)
    before you redistribute them or use them in a publication.
