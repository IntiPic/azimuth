"""Procesa TA (2015-09-05 a 2018-10-10) y genera resultados para el paper.

Desde la raiz del repositorio: python scripts/run_ta.py
No requiere auditorias previas ni modifica main.py, AZ o los CSV originales.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.config import get_station_config
from src.loader import load_gti_file
from src.clearsky import (
    get_clear_sky_mask,
    count_clear_sky_minutes_around_max,
    estimate_omega_star,
)
from src.estimator import AzimuthEstimator

# La columna cambio de nombre, pero la inclinacion fisica es 45 grados.
START, END = "2015-09-05", "2018-10-10"
TILT = 45.0
WINDOW_MINUTES = 120
MIN_CLEAR_EXCLUSIVE = 110
MAX_DISCARD_PASSES = 3
DAILY_AZIMUTH_SIGMA = 2.0  # Rechazo iterativo entre dias, como en la tesis.
TRANSITIONS = {"2016-09-27", "2017-05-12"}


def source_settings(raw_date):
    """Canal de GTI y referencia horaria detectada en la auditoria."""
    channel = (
        "GTI30_AV (W/m2)" if raw_date < "2016-09-27"
        else "GTI45_AV (W/m2)"
    )
    source_tz = "UTC" if raw_date <= "2017-05-11" else "Etc/GMT+3"
    return channel, source_tz


def lookup_day(date):
    """Indexar la LUT no bisiesta (2026) por mes/dia."""
    date = pd.Timestamp(date)
    if date.month == 2 and date.day == 29:
        return (59, 60)
    return (pd.Timestamp(2026, date.month, date.day).dayofyear,)


def gamma_from_lut(estimator, omega_star, date):
    days = lookup_day(date)
    if len(days) == 1:
        return float(estimator.estimate(omega_star, days[0], tie_break="last"))
    # Solo el 29/02: interpolacion de las curvas vecinas (como en la auditoria).
    values = estimator.ds.omega_star.sel(doy=list(days)).mean("doy").to_numpy()
    distances = np.abs(values - omega_star)
    idx = len(values) - 1 - np.argmin(distances[::-1])
    return float(estimator.ds.azimuth.values[idx])


def is_uniform(index):
    return len(index) >= 2 and bool(
        ((index[1:] - index[:-1]) == pd.Timedelta(minutes=1)).all()
    )


def raw_file_date(path):
    """Fecha de la primera muestra cruda, antes de aplicar zona horaria."""
    head = pd.read_csv(path, usecols=["Timestamp"], nrows=1)
    if head.empty:
        raise ValueError("archivo_vacio")
    timestamp = pd.to_datetime(head["Timestamp"].iloc[0], errors="coerce")
    if pd.isna(timestamp):
        raise ValueError("timestamp_invalido")
    return timestamp.date().isoformat()


def process_ta():
    cfg = get_station_config("TA")
    lat, lon, tz = cfg["latitude"], cfg["longitude"], cfg["tz"]
    estimator = AzimuthEstimator(
        lat, lon, TILT,
        lookup_table=REPO / cfg["lookup_table"],
        station="TA",
        expected_sha256=cfg.get("lookup_sha256"),
    )
    if estimator.ds.attrs.get("azimuth_convention") != (
        "SWC2021: north=0; east negative; west positive"
    ):
        raise ValueError("La LUT de TA no utiliza la convencion SWC2021")

    files = sorted((REPO / "data/TA").glob("*/DataT/TA_DT_*.csv"))
    if not files:
        raise FileNotFoundError("No se encontraron archivos de TA en data/TA/")

    rows = []
    skipped = Counter()
    for path in files:
        try:
            raw_date = raw_file_date(path)
            if not START <= raw_date <= END:
                continue
            if raw_date in TRANSITIONS:
                skipped["dia_de_transicion"] += 1
                continue

            channel, source_tz = source_settings(raw_date)
            df = load_gti_file(
                path, station="TA", gti_col=channel, source_tz=source_tz
            )
            if df.index.has_duplicates:
                raise ValueError("minutos_duplicados")
            if not is_uniform(df.index):
                raise ValueError("cadencia_irregular")
            if not np.isfinite(df.gti.to_numpy()).any():
                raise ValueError("GTI_sin_datos")

            tmax = df.gti.idxmax()
            date = tmax.date().isoformat()
            if not START <= date <= END:
                raise ValueError("maximo_fuera_del_periodo")

            clear_mask, _ = get_clear_sky_mask(df, lat, lon, tz)
            clear_minutes = int(
                count_clear_sky_minutes_around_max(df.gti, clear_mask, WINDOW_MINUTES)
            )
            if clear_minutes <= MIN_CLEAR_EXCLUSIVE:
                skipped["no_pasa_cielo_claro"] += 1
                continue

            fit = estimate_omega_star(
                df, WINDOW_MINUTES, lon,
                discard=True, max_discard_passes=MAX_DISCARD_PASSES,
                latitude=lat, eot_method="spencer",
            )
            omega = float(fit["omega_star"])
            gamma = gamma_from_lut(estimator, omega, date)
            rows.append({
                "date": date,
                "file": path.name,
                "gti_column": channel,
                "source_tz": source_tz,
                "tilt": TILT,
                "clear_minutes": clear_minutes,
                "omega_star": omega,
                "azimuth": gamma,
                "discarded_pct": fit["discarded_pct"],
                "discard_passes": fit["discard_passes"],
                "discard_stop_reason": fit["discard_stop_reason"],
            })
        except (ValueError, KeyError, IndexError) as exc:
            skipped[str(exc)] += 1

    if not rows:
        raise RuntimeError("No hay estimaciones validas de TA")

    results = pd.DataFrame(rows).sort_values(["date", "file"]).reset_index(drop=True)
    if results.date.duplicated().any():
        raise RuntimeError("Hay dos estimaciones para una misma fecha; revisar archivos")
    results.insert(0, "N", np.arange(1, len(results) + 1))
    return results, skipped


def reject_daily_azimuth_outliers(results, nsigma=DAILY_AZIMUTH_SIGMA):
    """Rechazo simultaneo e iterativo de dias con |gamma - media| > 2 SD.

    Es distinto del rechazo de puntos del ajuste cuadratico de cada dia.
    Conserva las 154 estimaciones originales; solo marca las excluidas.
    """
    result = results.copy()
    gamma = result["azimuth"].to_numpy(dtype=float)
    retained = np.ones(len(result), dtype=bool)
    rejection_iteration = np.zeros(len(result), dtype=int)

    iteration = 0
    while retained.sum() >= 3:
        selected = gamma[retained]
        mean = selected.mean()
        sd = selected.std(ddof=1)
        if not np.isfinite(sd) or sd == 0:
            break

        rejected = retained & (np.abs(gamma - mean) > nsigma * sd)
        if not rejected.any():
            break
        iteration += 1
        rejection_iteration[rejected] = iteration
        retained[rejected] = False
        print(f"Iteracion {iteration}: {rejected.sum()} dias rechazados; "
              f"quedan {retained.sum()}")

    result["retained"] = retained
    result["rejection_iteration"] = rejection_iteration
    # N permanece como indice original; N_retained es consecutivo en el grafico.
    result["N_retained"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result.loc[retained, "N_retained"] = np.arange(1, retained.sum() + 1)
    return result


def summarize(results):
    kept = results.loc[results.retained]
    records = []
    groups = [("Before 2SD", results), ("Total", kept)]
    groups += [(str(year), group) for year, group in kept.groupby(kept.date.str[:4])]
    for label, group in groups:
        if group.empty:
            continue
        records.append({
            "period": label,
            "N": len(group),
            "first": group.date.min(),
            "last": group.date.max(),
            "azimuth_mean": group.azimuth.mean(),
            "azimuth_sd": group.azimuth.std(ddof=1),
            "omega_star_mean": group.omega_star.mean(),
        })
    return pd.DataFrame(records)


def plot_azimuth(results, out):
    """Publicacion: solo dias retenidos, ambos graficos en ingles y PNG."""
    kept = results.loc[results.retained].copy()
    mean = kept.azimuth.mean()
    sd = kept.azimuth.std(ddof=1)
    dates = pd.to_datetime(kept.date)
    for horizontal in ("date", "N"):
        fig, ax = plt.subplots(figsize=(9, 4.6), constrained_layout=True)
        x = dates if horizontal == "date" else kept.N_retained.astype(int)
        ax.scatter(x, kept["azimuth"], s=19, alpha=0.85,
                   color="tab:blue", label="Daily estimates")
        ax.axhline(mean, color="black", linewidth=1.2,
                   label=f"Mean = {mean:.2f}°")
        ax.axhline(mean + sd, color="gray", linestyle="--", linewidth=1,
                   label=f"Mean ± SD (SD = {sd:.2f}°)")
        ax.axhline(mean - sd, color="gray", linestyle="--", linewidth=1)
        ax.set(xlabel="Date" if horizontal == "date" else "Clear day N",
               ylabel="Estimated azimuth γ (°)",
               title=f"TA · β = 45° · {len(kept)} retained clear days")
        if horizontal == "date":
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
            fig.autofmt_xdate()
        else:
            ax.set_xlim(0, len(kept) + 1)
        ax.grid(alpha=0.2)
        ax.legend(fontsize=8)
        fig.savefig(out / f"azimuth_vs_{horizontal}.png",
                    dpi=300, bbox_inches="tight")
        plt.close(fig)


def latex_table(summary, out):
    """Tabla breve de resultados de TA, total y por año."""
    lines = [
        r"\begin{tabular}{lrrr}",
        r"\hline",
        r"Period & $N$ & $\overline{\gamma}$ ($^\circ$) & SD ($^\circ$) \\",
        r"\hline",
    ]
    for row in summary.itertuples():
        if row.period not in {"Total", "2015", "2016", "2017", "2018"}:
            continue
        lines.append(f"{row.period} & {row.N} & {row.azimuth_mean:.2f} & {row.azimuth_sd:.2f} " + r"\\")
    lines.extend([r"\hline", r"\end{tabular}"])
    (out / "TA_summary.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=REPO / "outputs/TA/results/full_period")
    parser.add_argument("--plots-only", action="store_true",
                        help="Reuse azimuth_results.csv without reprocessing TA data")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    if args.plots_only:
        path = out / "azimuth_results.csv"
        if not path.exists():
            raise FileNotFoundError(f"No se encontro {path} para --plots-only")
        results = pd.read_csv(path).sort_values(["date", "file"]).reset_index(drop=True)
        results["N"] = np.arange(1, len(results) + 1)
        skipped = Counter()
    else:
        results, skipped = process_ta()

    results = reject_daily_azimuth_outliers(results)
    summary = summarize(results)
    results.to_csv(out / "azimuth_results.csv", index=False)
    summary.to_csv(out / "summary.csv", index=False)
    latex_table(summary, out)
    plot_azimuth(results, out)

    print("\nTA — Resultados (SWC2021, Oeste positivo):")
    print(summary.round(3).to_string(index=False))
    print("\nArchivos descartados:", dict(skipped))
    print("\nArchivos guardados en:", out)


if __name__ == "__main__":
    main()
