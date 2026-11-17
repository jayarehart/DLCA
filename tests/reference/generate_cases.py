"""Generate the reference cases from the Cooper et al. (2020) spreadsheet.

The spreadsheet is the *temporal climate impacts* workbook (version 5,
01/10/2020, CC-BY) by Sam Cooper et al., published as supplementary file
``mmc2.xlsx`` to Cooper et al. (2020), Biomass and Bioenergy 142, 105778,
https://doi.org/10.1016/j.biombioe.2020.105778. See ``README.md`` in this
folder for the full citation, attribution and column provenance.

**One correction is applied by default (DLCA, not the original authors).**
In version 5, the AGTP of CO2 (``intro!E50``) multiplies the third CO2 pool
(``life3_CO2``) by ``p_1`` instead of ``p_3``. The script finds every formula
with that slip (only ``intro!E50`` in version 5; it stops if it finds any other
cell or none, or if any other ``p_i``/``life<j>_CO2`` pair with i != j is left
in any formula, in either order) and changes ``p_1*life3_CO2`` to ``p_3*life3_CO2``. Pass
``--no-agtp-fix`` to generate from the uncorrected workbook.

For each case this script:

1. copies the workbook into a fresh temporary directory and applies the
   correction;
2. writes the case's inflows into the green input cells of the
   ``inventory_and_effects`` sheet (columns B-G, years 0-500) and the
   ``fossil_CH4`` flag (``intro!C31``) with openpyxl, keeping every formula;
3. recalculates the workbook headlessly with LibreOffice
   (``soffice --headless --calc --convert-to xlsx``);
4. reads the recalculated values (openpyxl, ``data_only=True``) and writes
   ``cases/<case>/inputs.csv``, ``settings.csv`` and ``expected.csv``.

It checks that the workbook is the expected one before using it, and that the
recalculation really ran (a CO2-only pulse must give year-100 integrated
radiative forcing equal to AGWP_100(CO2) = 9.17109e-14 W yr m-2, and every
case's cumulative net emissions must match its inputs). With the correction,
it also checks that the recalculated AGTP_100(CO2) equals the spreadsheet's
own year-100 temperature change for a 1 kg CO2 pulse.

``--save-corrected PATH`` also writes the corrected workbook, recalculated with
its original shipped inputs, to PATH. openpyxl drops the charts on the
``graphs`` sheet and the data-validation drop-downs from that copy.

Dependencies (none are runtime dependencies of ``dlca``):

- Python >= 3.11 and openpyxl (tested with 3.1);
- LibreOffice >= 7 with ``soffice`` on PATH or given by ``--soffice``.

This script is not run in CI. Treat the workbook as untrusted input: run it
with ``python -I`` so no local modules are imported, for example::

    uv run --no-project --with openpyxl python -I \\
        tests/reference/generate_cases.py /path/to/mmc2.xlsx

The output is deterministic: running it twice gives byte-identical CSVs.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import openpyxl

INV_SHEET = "inventory_and_effects"
EQ_SHEET = "equivalency_metrics"
FIRST_ROW = 7  # year 0
LAST_ROW = 507  # year 500
YEARS = range(0, 501)

# Input columns on the inventory sheet (all are green input cells).
INPUT_COLS = {
    "CO2_flux": "B",
    "CH4_flux": "C",
    "N2O_flux": "D",  # gas1 = Nitrous Oxide
    "gas2_flux": "E",  # Sulphate (example); always 0 here
    "gas3_flux": "F",  # CFC-11; always 0 here
    "other_forcing_W": "G",  # additional heat flow; always 0 here
}
# Header in row 6 that each input column must carry (guards against layout changes).
INPUT_HEADERS = {
    "B": "CO2_flux",
    "C": "CH4_flux",
    "D": "Gas1_flux",
    "E": "Gas2_flux",
    "F": "Gas3_flux",
    "G": "Other_forcing",
}

# expected.csv column -> (sheet, column letter, row-6 header in the workbook).
OUTPUT_COLS = [
    ("CO2_mass", INV_SHEET, "J", "CO2"),
    ("CH4_mass", INV_SHEET, "K", "CH4"),
    ("N2O_mass", INV_SHEET, "L", "gas1"),
    ("CO2_mass0", INV_SHEET, "AX", "CO2_mass0"),
    ("CO2_mass1", INV_SHEET, "AY", "CO2_mass1"),
    ("CO2_mass2", INV_SHEET, "AZ", "CO2_mass2"),
    ("CO2_mass3", INV_SHEET, "BA", "CO2_mass3"),
    ("CH4_to_CO2", INV_SHEET, "BB", "CH4_to_CO2"),
    ("CO2_radfor", INV_SHEET, "O", "CO2_radfor"),
    ("CH4_radfor", INV_SHEET, "P", "CH4_radfor"),
    ("N2O_radfor", INV_SHEET, "Q", "gas1_radfor"),
    ("CO2_IRF", INV_SHEET, "U", "CO2_IRF"),
    ("CH4_IRF", INV_SHEET, "V", "CH4_IRF"),
    ("N2O_IRF", INV_SHEET, "W", "gas1_IRF"),
    ("IRF_all", INV_SHEET, "H", "Integrated_rad_forcing"),
    ("CO2_temp", INV_SHEET, "AA", "CO2_temp"),
    ("CH4_temp", INV_SHEET, "AB", "CH4_temp"),
    ("N2O_temp", INV_SHEET, "AC", "gas1_temp"),
    ("temp_change", INV_SHEET, "I", "Temp_change"),
    ("CO2_net", INV_SHEET, "AG", "CO2_net"),
    ("CH4_net", INV_SHEET, "AH", "CH4_net"),
    ("N2O_net", INV_SHEET, "AI", "gas1_net"),
    ("GWP_static_CO2e", EQ_SHEET, "E", None),
    ("GTP_static_CO2e", EQ_SHEET, "F", None),
    ("IRF_over_AGWP_CO2", EQ_SHEET, "I", None),
    ("temp_over_AGTP_CO2", EQ_SHEET, "J", None),
    ("GWP_sliding_CO2e", EQ_SHEET, "K", None),
    ("GTP_sliding_CO2e", EQ_SHEET, "L", None),
]

# Start of the row-8 formula for each equivalency_metrics column read.
_ROW = "inventory[[#This Row],"
EQ_FORMULAS = {
    "E": f"={_ROW}[CO2_net]]+{_ROW}[CH4_net]]*GWP_CH4+{_ROW}[gas1_net]]*GWP_gas1",
    "F": f"={_ROW}[CO2_net]]+{_ROW}[CH4_net]]*GTP_CH4+{_ROW}[gas1_net]]*GTP_gas1",
    "I": "=B8/AGWP_CO2",
    "J": "=C8/AGTP_CO2",
    "K": f"=K7+({_ROW}[CO2_flux]]*Z8+{_ROW}[CH4_flux]]*AA8+{_ROW}[Gas1_flux]]*AB8",
    "L": f"=L7+({_ROW}[CO2_flux]]*AE8+{_ROW}[CH4_flux]]*AF8+{_ROW}[Gas1_flux]]*AG8",
}

AGWP100_CO2 = 9.171093415657962e-14  # intro!D50 as shipped (W yr m-2 kg-1)

# The AGTP correction: the cells version 5 has the slip in, and the pattern.
AGTP_SLIP = re.compile(r"p_1(\s*\*\s*life3_CO2)")
AGTP_SLIP_CELLS = ["intro!E50"]
# Any CO2 pool fraction p_i next to a lifetime life<j>_CO2 with i != j, in either
# order. After the correction there must be none left anywhere.
POOL_PAIR = re.compile(r"p_(\d)\s*\*\s*life(\d)_CO2|life(\d)_CO2\s*\*\s*p_(\d)")


def _pool_mismatches(text: str) -> list[str]:
    out = []
    for m in POOL_PAIR.finditer(text):
        i, j = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        if i != j:
            out.append(m.group(0))
    return out


def _pulse(year, kg):
    return {year: kg}


def _spread(first, last, kg_per_year):
    return {y: kg_per_year for y in range(first, last + 1)}


def _add(*dicts):
    out = {}
    for d in dicts:
        for y, v in d.items():
            out[y] = out.get(y, 0.0) + v
    return out


# Each case: per-gas {year: kg} inflows and the fossil_CH4 flag.
CASES = {
    "co2_pulse": {"fossil_CH4": False, "CO2_flux": _pulse(0, 1.0)},
    "ch4_pulse_biogenic": {"fossil_CH4": False, "CH4_flux": _pulse(0, 1.0)},
    "ch4_pulse_fossil": {"fossil_CH4": True, "CH4_flux": _pulse(0, 1.0)},
    "n2o_pulse": {"fossil_CH4": False, "N2O_flux": _pulse(0, 1.0)},
    "building_lifecycle": {
        "fossil_CH4": False,
        # A-stage pulse at year 0, B-stage every year 1-60, C-stage pulse at year 60.
        "CO2_flux": _add(_pulse(0, 1000.0), _spread(1, 60, 10.0), _pulse(60, 200.0)),
        "CH4_flux": _add(_pulse(0, 2.0), _spread(1, 60, 0.05), _pulse(60, 1.0)),
        "N2O_flux": _add(_pulse(0, 0.1), _spread(1, 60, 0.002), _pulse(60, 0.02)),
    },
    "negative_uptake": {"fossil_CH4": False, "CO2_flux": _spread(1, 40, -25.0)},
    "late_pulse": {"fossil_CH4": False, "CO2_flux": _pulse(250, 1.0)},
}


def fmt(x) -> str:
    """Shortest round-trip text for a number (deterministic, exact)."""
    if isinstance(x, bool):
        return "TRUE" if x else "FALSE"
    if isinstance(x, str):
        return x
    if isinstance(x, int):
        return str(x)
    x = float(x)
    if not math.isfinite(x):
        raise ValueError(f"non-finite value {x!r}")
    if x == 0:
        return "0.0"
    return repr(x)


def check_workbook(path: Path) -> None:
    wb = openpyxl.load_workbook(path, data_only=True)
    if "intro" not in wb.sheetnames or INV_SHEET not in wb.sheetnames:
        sys.exit(f"{path}: not the Cooper et al. workbook (missing sheets)")
    agwp = wb["intro"]["D50"].value
    if not isinstance(agwp, float) or abs(agwp / AGWP100_CO2 - 1) > 1e-12:
        sys.exit(f"{path}: intro!D50 = {agwp!r}, expected AGWP_100(CO2) = {AGWP100_CO2}")
    if "version 5" not in str(wb["intro"]["A58"].value):
        sys.exit(f"{path}: intro!A58 does not say version 5")
    ws = wb[INV_SHEET]
    for col, hdr in INPUT_HEADERS.items():
        if ws[f"{col}6"].value != hdr:
            sys.exit(f"{path}: {INV_SHEET}!{col}6 is {ws[f'{col}6'].value!r}, expected {hdr!r}")
    for _, sheet, col, hdr in OUTPUT_COLS:
        if hdr is not None and wb[sheet][f"{col}6"].value != hdr:
            sys.exit(f"{path}: {sheet}!{col}6 is {wb[sheet][f'{col}6'].value!r}, expected {hdr!r}")
    # equivalency_metrics headers are formulas, so check each column's row-8 formula.
    wf = openpyxl.load_workbook(path)[EQ_SHEET]
    for col, prefix in EQ_FORMULAS.items():
        f = str(wf[f"{col}8"].value)
        if not f.startswith(prefix):
            sys.exit(f"{path}: {EQ_SHEET}!{col}8 is {f[:60]!r}, expected it to start {prefix!r}")
    if wb["intro"]["H26"].value != 100:
        sys.exit(f"{path}: time horizon intro!H26 is not 100")


def apply_agtp_fix(src: Path, dst: Path) -> list[str]:
    """Change p_1*life3_CO2 to p_3*life3_CO2 in every formula; return the cells."""
    from openpyxl.worksheet.formula import ArrayFormula

    wb = openpyxl.load_workbook(src)
    patched = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                text = v.text if isinstance(v, ArrayFormula) else v
                if isinstance(text, str) and text.startswith("=") and AGTP_SLIP.search(text):
                    new = AGTP_SLIP.sub(r"p_3\1", text)
                    if isinstance(v, ArrayFormula):
                        v.text = new
                    else:
                        cell.value = new
                    patched.append(f"{ws.title}!{cell.coordinate}")
    if patched != AGTP_SLIP_CELLS:
        sys.exit(f"AGTP slip found in {patched}, expected exactly {AGTP_SLIP_CELLS}; stopping")
    left = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                text = v.text if isinstance(v, ArrayFormula) else v
                if isinstance(text, str) and text.startswith("=") and _pool_mismatches(text):
                    left.append(f"{ws.title}!{cell.coordinate}: {_pool_mismatches(text)}")
    if left:
        sys.exit(f"other CO2 pool/lifetime mismatches found, not corrected: {left}; stopping")
    wb.save(dst)
    return patched


def read_summary(path: Path) -> dict[str, float]:
    ws = openpyxl.load_workbook(path, data_only=True)["intro"]
    return {"AGWP100_CO2": ws["D50"].value, "AGTP100_CO2": ws["E50"].value}


def case_inputs(spec: dict) -> dict[str, list[float]]:
    cols = {}
    for name in INPUT_COLS:
        flows = spec.get(name, {})
        cols[name] = [float(flows.get(y, 0.0)) for y in YEARS]
    return cols


def write_case_workbook(src: Path, dst: Path, spec: dict) -> None:
    wb = openpyxl.load_workbook(src)  # keep formulas
    ws = wb[INV_SHEET]
    for name, col in INPUT_COLS.items():
        values = case_inputs(spec)[name]
        for i, y in enumerate(YEARS):
            ws[f"{col}{FIRST_ROW + i}"].value = values[i]
            assert ws[f"A{FIRST_ROW + i}"].value == y
    wb["intro"]["C31"].value = bool(spec["fossil_CH4"])
    wb.save(dst)


def recalc(soffice: str, files: list[Path], outdir: Path, profile: Path) -> None:
    cmd = [
        soffice,
        f"-env:UserInstallation={profile.as_uri()}",
        "--headless",
        "--calc",
        "--convert-to",
        "xlsx",
        "--outdir",
        str(outdir),
        *map(str, files),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=600)
    for f in files:
        if not (outdir / f.name).exists():
            sys.exit(f"LibreOffice did not produce {outdir / f.name}")


def read_results(path: Path) -> dict[str, list[float]]:
    wb = openpyxl.load_workbook(path, data_only=True)
    out = {}
    for name, sheet, col, _ in OUTPUT_COLS:
        ws = wb[sheet]
        vals = []
        for r in range(FIRST_ROW, LAST_ROW + 1):
            v = ws[f"{col}{r}"].value
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                sys.exit(f"{path}: {sheet}!{col}{r} = {v!r} is not a number")
            vals.append(float(v))
        out[name] = vals
    return out


def check_results(case: str, inputs: dict, results: dict, summary: dict, fixed: bool) -> None:
    # Recalculation really ran: cumulative net emissions match the inputs.
    for gas in ("CO2", "CH4", "N2O"):
        total = math.fsum(inputs[f"{gas}_flux"])
        got = results[f"{gas}_net"][-1]
        if abs(got - total) > 1e-9 * max(1.0, abs(total)):
            sys.exit(f"{case}: {gas}_net[500] = {got}, inputs sum to {total}; stale recalculation?")
    if case == "co2_pulse":
        irf100 = results["IRF_all"][100]
        if abs(irf100 / AGWP100_CO2 - 1) > 1e-9:
            sys.exit(f"co2_pulse: IRF[100] = {irf100}, expected AGWP_100(CO2) = {AGWP100_CO2}")
        if any(results["CH4_mass"]) or any(results["N2O_mass"]):
            sys.exit("co2_pulse: CH4 or N2O mass is non-zero; inputs were not applied")
        print(f"positive control: co2_pulse IRF[100] = {irf100:.6g} W yr m-2", file=sys.stderr)
        # Independent check of the AGTP correction: AGTP_100(CO2) is, by definition,
        # the temperature change 100 years after a 1 kg CO2 pulse.
        agtp, dt100 = summary["AGTP100_CO2"], results["CO2_temp"][100]
        print(f"AGTP_100(CO2) = {agtp!r} K/kg; co2_pulse dT[100] = {dt100!r} K", file=sys.stderr)
        if fixed and abs(agtp / dt100 - 1) > 1e-9:
            sys.exit("co2_pulse: corrected AGTP_100(CO2) does not match dT[100]")


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for row in rows:
            w.writerow([fmt(v) for v in row])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("workbook", type=Path, help="path to the Cooper et al. mmc2.xlsx")
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "cases",
        help="output folder (default: cases/ next to this script)",
    )
    ap.add_argument("--soffice", default=shutil.which("soffice") or "soffice")
    ap.add_argument("--keep", action="store_true", help="keep the temporary directory")
    ap.add_argument(
        "--no-agtp-fix",
        action="store_true",
        help="do not apply the AGTP p_1->p_3 correction (for checks only)",
    )
    ap.add_argument(
        "--save-corrected",
        type=Path,
        help="also save the corrected workbook, recalculated with its shipped inputs",
    )
    args = ap.parse_args(argv)

    tmp = Path(tempfile.mkdtemp(prefix="dlca-cooper-"))
    try:
        src = tmp / "source.xlsx"
        shutil.copyfile(args.workbook, src)
        check_workbook(src)

        indir, outdir = tmp / "in", tmp / "out"
        indir.mkdir()
        outdir.mkdir()
        files = []
        fixed = not args.no_agtp_fix
        if fixed:
            base = indir / "corrected.xlsx"
            cells = apply_agtp_fix(src, base)
            print(f"applied AGTP p_1->p_3 correction to {', '.join(cells)}", file=sys.stderr)
            files.append(base)
        else:
            if args.save_corrected:
                sys.exit("--save-corrected needs the correction; drop --no-agtp-fix")
            base = src
            print("WARNING: AGTP correction NOT applied (--no-agtp-fix)", file=sys.stderr)
        for case, spec in CASES.items():
            f = indir / f"{case}.xlsx"
            write_case_workbook(base, f, spec)
            files.append(f)
        recalc(args.soffice, files, outdir, tmp / "lo-profile")

        for case, spec in CASES.items():
            inputs = case_inputs(spec)
            results = read_results(outdir / f"{case}.xlsx")
            summary = read_summary(outdir / f"{case}.xlsx")
            check_results(case, inputs, results, summary, fixed)

            d = args.out / case
            d.mkdir(parents=True, exist_ok=True)
            in_cols = ["CO2_flux", "CH4_flux", "N2O_flux"]
            write_csv(
                d / "inputs.csv",
                ["year", *in_cols],
                [[y, *(inputs[c][i] for c in in_cols)] for i, y in enumerate(YEARS)],
            )
            write_csv(
                d / "settings.csv",
                ["name", "value"],
                [["fossil_CH4", bool(spec["fossil_CH4"])], ["time_horizon", 100]],
            )
            names = [c[0] for c in OUTPUT_COLS]
            write_csv(
                d / "expected.csv",
                ["year", *names],
                [[y, *(results[n][i] for n in names)] for i, y in enumerate(YEARS)],
            )
            print(f"wrote {d}", file=sys.stderr)
        if args.save_corrected:
            shutil.copyfile(outdir / "corrected.xlsx", args.save_corrected)
            print(f"saved corrected workbook to {args.save_corrected}", file=sys.stderr)
    finally:
        if args.keep:
            print(f"kept {tmp}", file=sys.stderr)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
