#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""Seasonal gamma(omega*) figure from the validated 1 s AZ LUT.

From repository root:
    python paper/generate_lut_figure.py

For a CSV-only review:
    python paper/generate_lut_figure.py --csv /path/to/lookup_table_1s.csv

Never regenerates or modifies any LUT.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "lookup" / "AZ" / "lookup_table_1s.csv"
FIG_DIR = ROOT / "paper" / "outputs" / "publication_v1" / "figures"

KEY_DAYS = [
    ("2026-03-21", "March equinox"),
    ("2026-06-21", "June solstice"),
    ("2026-09-21", "September equinox"),
    ("2026-12-21", "December solstice"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output-dir", type=Path, default=FIG_DIR)
    args = parser.parse_args()

    if not args.csv.is_file():
        raise FileNotFoundError(f"Cannot find LUT CSV: {args.csv}")

    lut = pd.read_csv(args.csv, index_col=0)
    gamma = lut.index.to_numpy(dtype=float)

    if len(lut) != 1801 or len(lut.columns) != 365:
        raise ValueError(f"Unexpected LUT shape: {lut.shape}")

    if not np.allclose(np.diff(gamma), 0.1, atol=1e-8):
        raise ValueError("Azimuth coordinate must have steps of 0.1 degree.")

    if not np.isfinite(lut.to_numpy()).all():
        raise ValueError("Non-finite LUT values.")

    if not np.all(np.diff(lut.to_numpy(), axis=0) < 0):
        raise ValueError("Non-monotonic omega*(gamma) found.")

    with plt.rc_context({
        "font.family": "DejaVu Sans",
        "font.size": 9.5,
        "axes.labelsize": 10.5,
        "axes.titlesize": 10.5,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.linewidth": 0.85,
        "savefig.pad_inches": 0.08,
    }):
        fig, ax = plt.subplots(
            figsize=(7.15, 4.55),
            constrained_layout=True
        )

        colors = ("#E69F00", "#0072B2", "#009E73", "#CC79A7")
        dashes = ("-", "--", "-.", ":")

        for (day, label), color, ls in zip(
            KEY_DAYS, colors, dashes
        ):
            if day not in lut.columns:
                raise KeyError(f"Missing LUT date {day}")

            omega_star = lut[day].to_numpy(dtype=float)

            ax.plot(
                omega_star,
                gamma,
                lw=2.15,
                color=color,
                linestyle=ls,
                label=f"{label} ({day})",
            )

        ax.axhline(0, color="0.34", lw=0.85, ls="--", alpha=0.8)
        ax.axvline(0, color="0.34", lw=0.85, ls="--", alpha=0.8)

        ax.set_xlabel(
            r"Hour angle at maximum GTI, $\omega^*$ (°)"
        )
        ax.set_ylabel(
            r"Surface azimuth, $\gamma$ (°)"
        )

        ax.set_xlim(-38, 38)
        ax.set_ylim(-94, 94)

        ax.set_xticks(np.arange(-30, 31, 10))
        ax.set_yticks(np.arange(-90, 91, 30))

        ax.grid(True, color="#E8E8E8", lw=0.7)
        ax.set_axisbelow(True)

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        ax.legend(
            loc="upper right",
            frameon=False,
            labelspacing=0.45,
        )

        args.output_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = args.output_dir / "F_LUT_seasonal_AZ_1s.pdf"
        png_path = args.output_dir / "F_LUT_seasonal_AZ_1s.png"

        fig.savefig(pdf_path, format="pdf", bbox_inches="tight")
        fig.savefig(
            png_path, format="png",
            dpi=300, bbox_inches="tight"
        )

        plt.close(fig)

    print(f"Figure saved: {pdf_path}")
    print(f"Preview saved: {png_path}")


if __name__ == "__main__":
    main()
