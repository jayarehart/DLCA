"""MkDocs hook: the API pages document exactly the public names (record 0022).

For each public module, every name in its ``__all__`` must appear on an API
page as a ``::: module.name`` block, or (for the names ``dlca`` re-exports)
be the same object as a name documented in another public module. No
``:::`` block may document a name outside ``__all__``. Every documented name
must have a docstring. Any failure stops the build.

Faults this catches: a public name added to ``__all__`` (and to record 0022)
with no API entry; an API entry left behind for a removed or renamed name; an
entry for an internal name; a public constant or class with no docstring, which
would render as an empty entry.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

from mkdocs.exceptions import PluginError

MODULES = ("dlca", "dlca.inventory", "dlca.climate", "dlca.parameters", "dlca.result")
BLOCK = re.compile(r"^:::\s+(\S+)\s*$", re.MULTILINE)


def _documented(api_dir: Path) -> set[str]:
    found = set()
    for page in sorted(api_dir.glob("*.md")):
        found.update(BLOCK.findall(page.read_text(encoding="utf-8")))
    return found - set(MODULES)  # module-level blocks give the module docstring only


def on_pre_build(config, **kwargs) -> None:
    root = Path(config["config_file_path"]).parent
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    documented = _documented(Path(config["docs_dir"]) / "api")

    public = {}
    for module_name in MODULES:
        module = importlib.import_module(module_name)
        for name in module.__all__:
            public[f"{module_name}.{name}"] = (name, getattr(module, name))

    problems = []
    for path, (name, obj) in sorted(public.items()):
        if path in documented:
            continue
        twins = [
            other
            for other in documented
            if other.rsplit(".", 1)[-1] == name and other in public and public[other][1] is obj
        ]
        if not twins:
            problems.append(f"{path} has no ::: entry on an API page")
    for path in sorted(documented - set(public)):
        problems.append(f"{path} is documented but is not in its module's __all__")

    import griffe

    package = griffe.load("dlca", search_paths=[src], resolve_aliases=True)
    for path in sorted(documented & set(public)):
        obj = package[path.removeprefix("dlca.")]
        if obj.docstring is None or not obj.docstring.value.strip():
            problems.append(f"{path} has no docstring")

    if problems:
        raise PluginError("API reference does not match record 0022:\n  " + "\n  ".join(problems))
