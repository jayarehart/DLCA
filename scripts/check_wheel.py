"""Check that a built DLCA wheel holds the packaged data files.

Usage:
    python scripts/check_wheel.py dist/dlca-*.whl [--version 1.0.0]

The list of required files is written out here by hand, not read from
``src/dlca/data``. That way a file that is deleted from the source tree, or
left out of the build, makes this check fail instead of shrinking the list.
When you add a packaged data file, add it here too.

With ``--version``, the check also requires the wheel's metadata to report
that version (the release workflow passes the tag without its leading "v").

Exits 0 when everything is present and 1 otherwise, listing what is missing.
It uses only the standard library, so it runs with any Python.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from email.parser import Parser
from pathlib import PurePosixPath

# Files the package reads at run time. Paths are inside the wheel.
REQUIRED_FILES = (
    # Input JSON Schemas
    "dlca/data/building_inventory.schema.json",
    "dlca/data/building_totals.schema.json",
    # Climate parameter sets
    "dlca/data/climate_parameters/ar5.json",
    "dlca/data/climate_parameters/ar6.json",
    # eGRID2023 grid factors
    "dlca/data/egrid2023_rev2_state.csv",
    "dlca/data/egrid2023_rev2_subregion.csv",
    # Cambium 2024 grid factors and their notice
    "dlca/data/cambium2024_gea_aer_gen_c.csv",
    "dlca/data/cambium2024_gea_historical.csv",
    "dlca/data/CAMBIUM_NOTICE.md",
    # Code entry points
    "dlca/__init__.py",
    "dlca/inventory/__init__.py",
)


def check(wheel: str, version: str | None = None) -> list[str]:
    """Return a list of problems with ``wheel``; empty if it passes."""
    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())
        problems = [f"missing: {name}" for name in REQUIRED_FILES if name not in names]

        dist_info = sorted(
            {
                PurePosixPath(n).parts[0]
                for n in names
                if PurePosixPath(n).parts[0].endswith(".dist-info")
            }
        )
        if len(dist_info) != 1:
            problems.append(f"expected one .dist-info directory, found {dist_info}")
            return problems
        info = dist_info[0]
        for name in ("METADATA", "RECORD", "WHEEL", "licenses/LICENSE"):
            if f"{info}/{name}" not in names:
                problems.append(f"missing: {info}/{name}")

        if version is not None and f"{info}/METADATA" in names:
            meta = Parser().parsestr(zf.read(f"{info}/METADATA").decode("utf-8"))
            if meta["Version"] != version:
                problems.append(f"version is {meta['Version']!r}, expected {version!r}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("wheel", help="path to the built .whl file")
    parser.add_argument("--version", help="version the wheel metadata must report")
    args = parser.parse_args(argv)

    problems = check(args.wheel, args.version)
    if problems:
        print(f"FAIL {args.wheel}")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(f"OK   {args.wheel}: all {len(REQUIRED_FILES)} required files present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
