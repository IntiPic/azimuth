"""Validate the two fixed result CSVs and calculate descriptive paper tables.

Shared with generate_figures.py so plots and tables use the same original rows
and definitions. No production modules, raw irradiance, screening or LUT reads.
"""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import platform
from pathlib import Path
import re
import os
import shlex
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "paper" / "outputs"
INPUTS = {
    "AZ": os.environ.get(
        "AZ_RESULTS_CSV",
        "outputs/AZ/results/spa_1s/azimuth_results.csv",
    ),
    "TA": "outputs/TA/results/azimuth_results_20261103_204427.csv",
}
COMMON = ["station", "date", "doy", "tilt", "omega_star", "azimuth",
          "discarded_pct", "discard_passes", "discard_stop_reason"]
AZ_EXTRA = ["azimuth_nominal", "azimuth_error_deg", "azimuth_abs_error_deg"]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate_frame(frame, station):
    """Reject inconsistent data; never drop, impute or round observations."""
    expected = COMMON + (AZ_EXTRA if station == "AZ" else [])
    if len(frame.columns) != len(expected) or set(frame.columns) != set(expected):
        raise ValueError(f"{station}: expected columns {expected}, got {list(frame.columns)}")
    if frame.empty:
        raise ValueError(f"{station}: empty results CSV")
    if frame.isna().any().any() or not frame["station"].eq(station).all():
        raise ValueError(f"{station}: missing values or incorrect station")
    frame = frame.copy()
    dates = frame["date"].astype(str)
    if not dates.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise ValueError(f"{station}: dates must be YYYY-MM-DD calendar dates")
    frame["date"] = pd.to_datetime(dates, format="%Y-%m-%d", errors="raise")
    if frame["date"].duplicated().any():
        raise ValueError(f"{station}: duplicate daily result")
    numeric = [c for c in expected if c not in ("station", "date", "discard_stop_reason")]
    for col in numeric:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
        if not np.isfinite(frame[col]).all():
            raise ValueError(f"{station}: non-finite {col}")
    if not frame["doy"].eq(frame["date"].dt.dayofyear).all():
        raise ValueError(f"{station}: day of year does not match the GTI maximum date")
    if not frame["tilt"].eq(35 if station == "AZ" else 45).all():
        raise ValueError(f"{station}: unexpected tilt")
    for col in ["azimuth", "omega_star"]:
        if not frame[col].between(-180, 180).all():
            raise ValueError(f"{station}: {col} outside the degree convention")
    if not frame["discarded_pct"].between(0, 100).all():
        raise ValueError(f"{station}: invalid discarded percentage")
    passes = frame["discard_passes"]
    if not (passes.ge(0) & passes.eq(np.floor(passes))).all():
        raise ValueError(f"{station}: invalid discard pass count")
    if not frame["discard_stop_reason"].isin(["max_passes_reached", "no_new_outliers"]).all():
        raise ValueError(f"{station}: unexpected discard stop reason")
    if station == "AZ":
        if not frame["azimuth_nominal"].between(-90, 90).all():
            raise ValueError("AZ: nominal azimuth outside LUT range")
        frame["delta_gamma"] = frame["azimuth"] - frame["azimuth_nominal"]
        if not frame["delta_gamma"].abs().lt(180).all():
            raise ValueError("AZ: differences cross the angular branch; review before publication")
        if not np.allclose(frame["azimuth_error_deg"], -frame["delta_gamma"], rtol=0, atol=1e-9):
            raise ValueError("AZ: stored signed differences no longer follow nominal minus estimated")
        if not np.allclose(frame["azimuth_abs_error_deg"], frame["delta_gamma"].abs(), rtol=0, atol=1e-9):
            raise ValueError("AZ: inconsistent stored absolute differences")
    elif frame["azimuth"].max() - frame["azimuth"].min() >= 180:
        raise ValueError("TA: angular span requires reviewing linear descriptive statistics")
    # CSV line identity survives chronological sorting. Header is line 1.
    frame["csv_row"] = np.arange(2, len(frame) + 2)
    frame["date_raw"] = dates
    return frame.sort_values("date").reset_index(drop=True)


def load_results():
    data, provenance = {}, {}
    for station, relative in INPUTS.items():
        path = ROOT / relative
        raw = path.read_bytes()  # The only scientific input read for each station.
        records = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        header = next(csv.reader(io.StringIO(raw.decode("utf-8"))))
        if len(header) != len(set(header)):
            raise ValueError(f"{station}: duplicate column names")
        data[station] = validate_frame(pd.read_csv(io.BytesIO(raw)), station)
        provenance[station] = {
            "path": relative, "absolute_path": str(path), "sha256": sha256(raw),
            "rows": len(records), "columns": header,
            "original_rows": [{"csv_row": i, **row} for i, row in enumerate(records, 2)],
        }
    return data, provenance


def summarize(data):
    az_rows = []
    for nominal, group in data["AZ"].groupby("azimuth_nominal", sort=True):
        delta = group["delta_gamma"]
        az_rows.append({
            "nominal_azimuth_deg": nominal,
            "N": len(group),
            "mean_azimuth_deg": group["azimuth"].mean(),
            "std_azimuth_deg": group["azimuth"].std(ddof=1) if len(group) >= 2 else np.nan,
            "signed_bias_deg": delta.mean(),
            "MAE_deg": delta.abs().mean(),
            "RMSE_deg": np.sqrt(np.mean(delta ** 2)),
        })
    ta = data["TA"]
    return pd.DataFrame(az_rows), pd.DataFrame([{
        "N": len(ta),
        "measurement_start": ta["date"].min().date().isoformat(),
        "measurement_end": ta["date"].max().date().isoformat(),
        "mean_azimuth_deg": ta["azimuth"].mean(),
        "median_azimuth_deg": ta["azimuth"].median(),
        "std_azimuth_deg": ta["azimuth"].std(ddof=1),
        "min_azimuth_deg": ta["azimuth"].min(),
        "max_azimuth_deg": ta["azimuth"].max(),
    }])


def write_tables(directory, summaries):
    """Full precision CSVs; two decimal places in booktabs LaTeX fragments."""
    az, ta = summaries
    products = []
    for name, frame in [("T01_AZ_by_nominal_orientation", az), ("T02_TA_azimuth_estimates", ta)]:
        path = directory / f"{name}.csv"
        with path.open("x", encoding="utf-8", newline="") as stream:
            frame.to_csv(stream, index=False, na_rep="NA")
        products.append(path)

    def number(value):
        return "--" if pd.isna(value) else f"{value:.2f}"

    az_lines = [r"\begin{table}[htbp]", r"\centering", r"\small",
                r"\caption{AZ results by nominal orientation. All angular quantities are in degrees. "
                r"Signed bias is the mean of $\Delta\gamma=\hat{\gamma}-\gamma_{\mathrm{nom}}$. "
                r"SD is the sample standard deviation ($N-1$ denominator); -- denotes $N=1$. "
                r"Nominal orientations are not independent ground truth.}",
                r"\label{tab:az-nominal}", r"\begin{tabular}{rrrrrrr}", r"\toprule",
                r"$\gamma_{\mathrm{nom}}$ & $N$ & Mean $\hat{\gamma}$ & SD & Signed bias & MAE & RMSE \\",
                r"\midrule"]
    for row in az.itertuples(index=False, name=None):
        az_lines.append(" & ".join([f"{row[0]:.0f}", str(row[1])] + [number(v) for v in row[2:]]) + r" \\")
    az_lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    t = ta.iloc[0]
    ta_lines = [r"\begin{table}[htbp]", r"\centering", r"\small",
                r"\caption{Descriptive statistics of the TA azimuth estimates. "
                r"The period spans the first and last retained GTI maximum dates, "
                r"not continuous coverage. SD uses the $N-1$ denominator. "
                r"These statistics are not calibrated uncertainties.}",
                r"\label{tab:ta-descriptive}", r"\begin{tabular}{lr}", r"\toprule",
                r"Statistic & Value \\", r"\midrule", f"$N$ & {int(t['N'])}" + r" \\",
                f"Measurement period & {t['measurement_start']} to {t['measurement_end']}" + r" \\"]
    for label, key in [(r"Mean $\hat{\gamma}$", "mean"), (r"Median $\hat{\gamma}$", "median"),
                       ("Sample SD", "std"), ("Minimum", "min"), ("Maximum", "max")]:
        ta_lines.append(label + r" ($^\circ$) & " + number(t[f"{key}_azimuth_deg"]) + r" \\")
    ta_lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    for name, lines in [("T01_AZ_by_nominal_orientation", az_lines), ("T02_TA_azimuth_estimates", ta_lines)]:
        path = directory / f"{name}.tex"
        with path.open("x", encoding="utf-8") as stream:
            stream.write("\n".join(lines) + "\n")
        products.append(path)
    return products


def prepare_run(run_id, with_figures=False):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", run_id):
        raise ValueError("Invalid publication run ID")

    if OUTPUT.is_symlink():
        raise ValueError("Output directory cannot be a symlink")

    run_dir = OUTPUT / run_id

    # Nunca sobrescribir una corrida existente.
    run_dir.mkdir(parents=True, exist_ok=False)

    table_dir = run_dir / "tables"
    figure_dir = run_dir / "figures"

    table_dir.mkdir()
    if with_figures:
        figure_dir.mkdir()

    return run_dir, table_dir, figure_dir


def write_manifest(run_dir, provenance, products, summaries, details=None):
    def git(*args):
        result = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
        return result.stdout.rstrip() if result.returncode == 0 else None

    import matplotlib
    paper = ROOT / "paper"
    code = sorted(paper.glob("*.py")) + [paper / "README.md"]
    tests = ROOT / "tests" / "test_paper_results.py"
    if tests.exists():
        code.append(tests)
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "command": shlex.join([sys.executable, *sys.argv]),
        "working_directory": str(Path.cwd()),
        "git_commit": git("rev-parse", "HEAD"),
        "git_status": git("status", "--short", "--untracked-files=all"),
        "tracked_diff_sha256": sha256((git("diff", "HEAD", "--binary") or "").encode()),
        "code_sha256": {str(p.relative_to(ROOT)): sha256(p.read_bytes()) for p in code},
        "versions": {"python": sys.version, "numpy": np.__version__, "pandas": pd.__version__,
                     "matplotlib": matplotlib.__version__, "platform": platform.platform()},
        "inputs": provenance,
        "definitions": {
            "delta_gamma": "estimated minus nominal; direct difference in degrees; no wrapping needed for these rows",
            "standard_deviation": "sample SD, ddof=1; not calculated for N=1",
            "dispersion": "descriptive across retained days; not calibrated uncertainty or standard error",
            "date": "CSV date is the local GTI maximum calendar date (America/Montevideo), per main.py and src/config.py; no time-of-day present",
            "period": "first to last retained date, not continuous measurement coverage",
            "nominal": "AZ CSV nominal values only; not independent ground truth; TA has no nominal",
            "source_error": "input azimuth_error_deg has the opposite sign and is checked but not used to calculate metrics",
            "angular_convention": "unchanged from input CSVs; no origin or sign conversion",
        },
        "summaries": {"T01": json.loads(summaries[0].to_json(orient="records", double_precision=15)),
                      "T02": json.loads(summaries[1].to_json(orient="records", double_precision=15))},
        "products": {str(p.relative_to(ROOT)): sha256(p.read_bytes()) for p in products},
        "plot_details": details,
    }
    path = run_dir / "manifest.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return path


def arguments(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--run-id",
        default="current",
        help="Output directory identifier",
    )
    return parser.parse_args()


def main():
    args = arguments(__doc__)
    data, provenance = load_results()
    summaries = summarize(data)
    run_dir, table_dir, _ = prepare_run(args.run_id)
    products = write_tables(table_dir, summaries)
    manifest = write_manifest(run_dir, provenance, products, summaries)
    print(f"Validated AZ={len(data['AZ'])}, TA={len(data['TA'])}. Tables: {table_dir}\nManifest: {manifest}")


if __name__ == "__main__":
    main()
