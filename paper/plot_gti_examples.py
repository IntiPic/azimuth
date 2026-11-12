"""Figure draft: observed GTI quadratic fits. Does not change the estimator.

Run from the azimuth repository root:
    python paper/plot_gti_examples.py
"""
from pathlib import Path
import sys
import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.loader import load_gti_file
from src.clearsky import estimate_omega_star
DATA = ROOT / "data" / "all"
OUT = ROOT / "paper" / "outputs" / "figures" / "publication_v1"
DATES = ("20260616", "20260701", "20260831")
EXPECTED = (-3.75332853117, -5.70983104090, -15.65700230399)
LONGITUDE = -56.166802  # AZ; consistent with the audited configuration


def main():
    cases = []
    for date_str, expected in zip(DATES, EXPECTED):
        path = DATA / f"AZ_DT_{date_str}T235900.csv"
        if not path.is_file():
            raise FileNotFoundError(path)
        day = load_gti_file(path, station="AZ")
        fit = estimate_omega_star(
            day, window_minutes=120, longitude=LONGITUDE,
            discard=True, max_discard_passes=3,
        )
        # Guard against accidentally plotting a different estimator version.
        np.testing.assert_allclose(fit["omega_star"], expected, atol=1e-8, rtol=0)
        cases.append((path.stem[6:14], fit))

    style = {
        "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 9,
        "xtick.labelsize": 7, "ytick.labelsize": 7,
        "pdf.fonttype": 42,
    }
    with plt.rc_context(style):
        fig, axs = plt.subplots(2, 3, figsize=(7.4, 4.6),
                                sharex="col", height_ratios=(2.2, 1),
                                layout="constrained")
        for col, (date_str, fit) in enumerate(cases):
            ax, axr = axs[:, col]
            omega = np.asarray(fit["omega"])
            gti = np.asarray(fit["gti"])
            coef = fit["coef"]
            xx = np.linspace(min(omega.min(), fit["omega_discarded"].min(initial=np.inf)),
                             max(omega.max(), fit["omega_discarded"].max(initial=-np.inf)), 250)
            ax.scatter(omega, gti, s=9, color="#1f77b4", label="Retained", zorder=3)
            if fit["n_discarded"]:
                ax.scatter(fit["omega_discarded"], fit["gti_discarded"],
                           s=16, marker="x", color="#cf6f29", label="Rejected", zorder=4)
            ax.plot(xx, np.polyval(coef, xx), color="#242424", lw=1.3,
                    label="Quadratic fit")
            ax.axvline(fit["omega_star"], color="#8c3b8d", ls="--", lw=1.0,
                       label=r"$\omega^*$")
            ax.set_title(f"({chr(97 + col)}) {date_str[:4]}-{date_str[4:6]}-{date_str[6:]}")
            if col == 0:
                ax.set_ylabel(r"GTI (W m$^{-2}$)")
            resid = gti - np.polyval(coef, omega)
            axr.scatter(omega, resid, s=9, color="#1f77b4", zorder=3)
            if fit["n_discarded"]:
                dropped_resid = fit["gti_discarded"] - np.polyval(coef, fit["omega_discarded"])
                axr.scatter(fit["omega_discarded"], dropped_resid,
                            s=16, marker="x", color="#cf6f29", zorder=4)
            axr.axhline(0, color="0.4", lw=.8)
            axr.axvline(fit["omega_star"], color="#8c3b8d", ls="--", lw=1)
            axr.set_xlabel(r"Hour angle, $\omega$ (°)")
            if col == 0:
                axr.set_ylabel(r"Residual (W m$^{-2}$)")
            for axis in (ax, axr):
                axis.grid(alpha=.15)
        handles, labels = axs[0, 0].get_legend_handles_labels()
        fig.legend(handles, labels, ncol=4, loc="outside upper center", fontsize=7,
                   frameon=False)
        OUT.mkdir(parents=True, exist_ok=True)
        for suffix in ("pdf", "png"):
            fig.savefig(OUT / f"F04_GTI_fits_AZ.{suffix}",
                        dpi=300, bbox_inches="tight")
        plt.close(fig)
        for date, fit in cases:
            print(f"{date}: omega*={fit['omega_star']:.6f} deg; "
                  f"n_discarded={fit['n_discarded']}")


if __name__ == "__main__":
    main()
