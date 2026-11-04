"""Generate F01-F03, T01-T02 and a provenance manifest from fixed CSVs."""

import os
from pathlib import Path
import tempfile

# Keep Matplotlib's cache outside the scientific data/output directories.
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "azimuth-paper-mpl"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from generate_tables import (
    arguments, load_results, prepare_run, summarize, write_manifest, write_tables,
)
from paper_style import BLUE, ORANGE, ORIENTATIONS, paper_context


def time_series(data):
    fig, axes = plt.subplots(2, 1, figsize=(7.1, 4.8), layout="constrained")
    for panel, (station, frame), ax in zip("ab", data.items(), axes):
        # Markers only: there is no interpolation across unobserved dates.
        ax.scatter(frame["date"], frame["azimuth"], s=27, color=BLUE,
                   edgecolor="white", linewidth=0.4, zorder=3, label=r"Estimated $\hat{\gamma}$")
        if station == "AZ":
            ax.scatter(frame["date"], frame["azimuth_nominal"], s=49, marker="D",
                       facecolors="none", edgecolors=ORANGE, linewidth=1.0, zorder=4,
                       label=r"Nominal $\gamma_{\mathrm{nom}}$")
            ax.legend(loc="upper left", bbox_to_anchor=(0.17, 1.02), ncol=2,
                      handletextpad=0.4, columnspacing=1.2)
            ax.set_ylim(-4, 44)
            ax.set_yticks([0, 10, 20, 30, 40])
        else:
            ax.set_ylim(-17.1, -10.6)
            ax.set_yticks([-16, -14, -12])
        ax.text(0.01, 0.96, f"({panel}) {station}   $N={len(frame)}$", transform=ax.transAxes,
                ha="left", va="top", fontsize=9)
        ax.set_ylabel(r"Azimuth, $\gamma$ ($^\circ$)")
        ax.set_xlabel("Date of GTI maximum (America/Montevideo)")
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%Y"))
        ax.margins(x=0.04)
        ax.grid(axis="y", color="0.90", linewidth=0.5)
        ax.set_axisbelow(True)
    return fig


def estimated_vs_nominal(az):
    fig, ax = plt.subplots(figsize=(3.5, 3.5), layout="constrained")
    ax.plot([-5, 40], [-5, 40], color="0.45", linestyle="--", linewidth=0.9, zorder=1)
    for nominal, group in az.groupby("azimuth_nominal", sort=True):
        color, marker = ORIENTATIONS[nominal]
        ax.scatter(group["azimuth_nominal"], group["azimuth"], s=33,
                   color=color, marker=marker, edgecolor="white", linewidth=0.4,
                   zorder=3, label=rf"{nominal:.0f}$^\circ$")
    ax.set(xlim=(-5, 40), ylim=(-5, 40), xticks=[0, 10, 20, 30, 40], yticks=[0, 10, 20, 30, 40])
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel(r"Nominal azimuth, $\gamma_{\mathrm{nom}}$ ($^\circ$)")
    ax.set_ylabel(r"Estimated azimuth, $\hat{\gamma}$ ($^\circ$)")
    ax.legend(title=r"Nominal $\gamma_{\mathrm{nom}}$", loc="upper left", title_fontsize=8,
              labelspacing=0.35, handletextpad=0.3)
    ax.text(0.97, 0.04, f"AZ   $N={len(az)}$", transform=ax.transAxes, ha="right", va="bottom")
    return fig


def differences(az, summary):
    fig, ax = plt.subplots(figsize=(3.5, 3.5), layout="constrained")
    ax.axhline(0, color="0.45", linestyle="--", linewidth=0.9, zorder=1)
    ticks, labels = [], []
    for position, row in enumerate(summary.itertuples(index=False)):
        nominal = row.nominal_azimuth_deg
        group = az.loc[az["azimuth_nominal"].eq(nominal)]
        color, marker = ORIENTATIONS[nominal]
        # Deterministic offsets reveal all daily points; they have no angular meaning.
        offsets = np.linspace(-0.17, 0.03, len(group)) if len(group) > 1 else np.array([0.0])
        ax.scatter(position + offsets, group["delta_gamma"], color=color, marker=marker,
                   s=33, edgecolor="white", linewidth=0.4, zorder=3)
        if row.N >= 2:
            ax.errorbar(position + 0.22, row.signed_bias_deg, yerr=row.std_azimuth_deg,
                        fmt="_", color="0.15", markersize=9, capsize=3,
                        linewidth=1.1, zorder=4)
        ticks.append(position)
        labels.append(rf"{nominal:.0f}$^\circ$" + f"\n$N={row.N}$")
    ax.set_xticks(ticks, labels)
    ax.set(xlim=(-0.5, 3.55), ylim=(-3.2, 8.5))
    ax.set_yticks([-2, 0, 2, 4, 6, 8])
    ax.set_xlabel(r"Nominal azimuth, $\gamma_{\mathrm{nom}}$")
    ax.set_ylabel(r"$\Delta\gamma=\hat{\gamma}-\gamma_{\mathrm{nom}}$ ($^\circ$)")
    handle = ax.errorbar([], [], yerr=[], fmt="_", color="0.15", markersize=9,
                         capsize=3, linewidth=1.1)
    ax.legend([handle], [r"Mean $\pm$ sample SD ($N\geq2$)"], loc="upper left",
              fontsize=7.5, handletextpad=0.5)
    return fig


def save_figure(fig, directory, stem):
    products = []
    for suffix in ["pdf", "png"]:
        path = directory / f"{stem}.{suffix}"
        with path.open("xb") as stream:
            fig.savefig(stream, format=suffix, dpi=300)
        products.append(path)
    plt.close(fig)
    return products


def main():
    args = arguments(__doc__)
    data, provenance = load_results()
    summaries = summarize(data)
    run_dir, table_dir, figure_dir = prepare_run(args.run_id, with_figures=True)
    products = write_tables(table_dir, summaries)
    with paper_context():
        products += save_figure(time_series(data), figure_dir, "F01_azimuth_over_time")
        products += save_figure(estimated_vs_nominal(data["AZ"]), figure_dir, "F02_estimated_vs_nominal_AZ")
        products += save_figure(differences(data["AZ"], summaries[0]), figure_dir, "F03_differences_by_nominal_AZ")
    details = {
        "F01": "all 7 AZ and 29 TA rows; marker-only; nominal markers only on AZ observed dates; different panel y ranges",
        "F02": "7 AZ estimates from SPA EOT and 1-second LUT; identity line; equal axis limits",
        "F03": "all 7 daily signed differences; small deterministic horizontal offsets; summary mean and sample SD only for N>=2, taken directly from T01",
        "F03_summary_groups": [float(v) for v in summaries[0].loc[summaries[0]["N"].ge(2), "nominal_azimuth_deg"]],
        "PNG_dpi": 300,
        "PDF": "vector paths and embedded TrueType fonts; no rasterized artists",
    }
    manifest = write_manifest(run_dir, provenance, products, summaries, details)
    print(f"Validated AZ=7, TA=29.\nFigures: {figure_dir}\nTables: {table_dir}\nManifest: {manifest}")
    print(summaries[0].to_string(index=False))
    print(summaries[1].to_string(index=False))


if __name__ == "__main__":
    main()
