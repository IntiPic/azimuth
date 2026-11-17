#!/usr/bin/env python3
"""Plot the versioned SWC2021 AZ NetCDF, without regenerating any LUT.

Standalone usage (requires a new output directory):
    python paper/generate_lut_figure.py --output-dir paper/outputs/NEW_RUN/figures
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "azimuth-paper-mpl"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NETCDF = ROOT / "lookup" / "AZ" / "lookup_omega_gamma_1s_swc2021.nc"
KEY_DAYS = [
    ("2026-03-21", "March equinox"),
    ("2026-06-21", "June solstice"),
    ("2026-09-21", "September equinox"),
    ("2026-12-21", "December solstice"),
]


def validate_lut(lut):
    if lut.shape != (1801, 365):
        raise ValueError(f"Unexpected LUT shape: {lut.shape}")
    gamma = lut.index.to_numpy(dtype=float)
    if (not np.allclose(np.diff(gamma), 0.1, rtol=0, atol=1e-8)
            or not np.allclose(gamma[[0, -1]], [-90, 90], rtol=0, atol=1e-8)):
        raise ValueError("Azimuth coordinate must span -90 to 90 with steps of 0.1 degree.")
    if not np.isfinite(lut.to_numpy()).all():
        raise ValueError("Non-finite LUT values.")
    if not np.all(np.diff(lut.to_numpy(), axis=0) > 0):
        raise ValueError("SWC2021 omega*(gamma) must be strictly increasing for every day.")


def load_lut(path=DEFAULT_NETCDF):
    """Read coordinates and omega* directly from the NetCDF; never flip omega*."""
    path = Path(path).resolve()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with xr.open_dataset(path, engine="netcdf4") as ds:
        attrs = {k: v.item() if isinstance(v, np.generic) else v for k, v in ds.attrs.items()}
        if (attrs.get("station") != "AZ" or attrs.get("reference_year") != 2026
                or attrs.get("temporal_resolution_seconds") != 1
                or attrs.get("azimuth_convention") != "SWC2021: north=0; east negative; west positive"):
            raise ValueError("Expected the AZ 2026 1-second SWC2021 LUT metadata.")
        if not np.array_equal(ds["doy"].values, np.arange(1, 366)):
            raise ValueError("Expected ordered day-of-year coordinates 1..365.")
        dates = (pd.Timestamp(year=attrs["reference_year"], month=1, day=1)
                 + pd.to_timedelta(ds["doy"].values - 1, unit="D"))
        lut = pd.DataFrame(ds["omega_star"].transpose("azimuth", "doy").values.copy(),
                           index=ds["azimuth"].values.copy(), columns=dates.strftime("%Y-%m-%d"))
    validate_lut(lut)
    provenance = {
        "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "absolute_path": str(path), "sha256": digest, "size_bytes": path.stat().st_size,
        "format": "NetCDF", "engine": "netcdf4", "variable": "omega_star",
        "dimensions": ["azimuth", "doy"], "shape": list(lut.shape), "attrs": attrs,
        "minimum_omega_increment_deg": float(np.diff(lut.to_numpy(), axis=0).min()),
        "transformation": "none; native azimuth coordinates and omega_star values",
    }
    return lut, provenance


def plot_lut(lut):
    validate_lut(lut)
    fig, ax = plt.subplots(figsize=(7.15, 4.55), layout="constrained")
    colors = ("#E69F00", "#0072B2", "#009E73", "#CC79A7")
    for (day, label), color, ls in zip(KEY_DAYS, colors, ("-", "--", "-.", ":")):
        ax.plot(lut[day].to_numpy(dtype=float), lut.index.to_numpy(dtype=float),
                lw=2.15, color=color, linestyle=ls, label=f"{label} ({day})")
    ax.axhline(0, color="0.34", lw=0.85, ls="--", alpha=0.8)
    ax.axvline(0, color="0.34", lw=0.85, ls="--", alpha=0.8)
    ax.set_xlabel(r"Hour angle at maximum GTI, $\omega^*$ (°)")
    ax.set_ylabel(r"Surface azimuth, $\gamma$ (°)")
    ax.set(xlim=(-38, 38), ylim=(-94, 94),
           xticks=np.arange(-30, 31, 10), yticks=np.arange(-90, 91, 30))
    ax.grid(True, color="#E8E8E8", lw=0.7)
    ax.set_axisbelow(True)
    # Increasing SWC2021 curves occupy the upper-right quadrant.
    ax.legend(loc="upper left", frameon=False, labelspacing=0.45)
    return fig


def main(argv=None):
    from paper_style import paper_context

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netcdf", type=Path, default=DEFAULT_NETCDF)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    lut, provenance = load_lut(args.netcdf)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    products = []
    with paper_context():
        fig = plot_lut(lut)
        for suffix in ("pdf", "png"):
            path = args.output_dir / f"F_LUT_seasonal_AZ_1s.{suffix}"
            with path.open("xb") as stream:
                fig.savefig(stream, format=suffix, dpi=300)
            products.append(path)
        plt.close(fig)
    import json
    with (args.output_dir / "lut_manifest.json").open("x") as stream:
        json.dump(provenance, stream, indent=2)
        stream.write("\n")
    for path in products:
        print(f"Figure saved: {path}")
    return products


if __name__ == "__main__":
    main()
