# Install

Python 3.10 or newer is required.

Releases are published on [GitHub](https://github.com/jayarehart/DLCA/releases)
only. DLCA is not on PyPI, so `pip install dlca` will not find it.

## From a tag

This builds the package from source and works for any release tag, for
example `v0.5.0`:

```bash
pip install "git+https://github.com/jayarehart/DLCA.git@v0.5.0"
```

## From a release wheel

Releases made by the release workflow (after v0.5.0) have a wheel attached.
Take its link from the release page, or use the pattern below (replace
`X.Y.Z` with the release you want):

```bash
pip install https://github.com/jayarehart/DLCA/releases/download/vX.Y.Z/dlca-X.Y.Z-py3-none-any.whl
```

## From source, for development

```bash
git clone https://github.com/jayarehart/DLCA.git
cd DLCA
uv sync          # or: pip install .
```

See
[CONTRIBUTING.md](https://github.com/jayarehart/DLCA/blob/main/CONTRIBUTING.md)
for how releases are made and for the development workflow.

## Check the install

```python
import importlib.metadata

import dlca

print(importlib.metadata.version("dlca"))
print(dlca.available_parameter_sets())  # ['AR5', 'AR6']
```

## Build these docs

The docs tools are in the `docs` dependency group:

```bash
uv run --group docs mkdocs serve
```
