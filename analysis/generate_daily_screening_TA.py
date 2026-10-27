#!/usr/bin/env python3
"""
Genera gráficos diarios para el screening de candidatos a cielo claro.

No estima omega_star ni azimut. La estación se selecciona con STATION y sus
particularidades se leen desde src/config.py.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import get_station_config
from src.loader import load_gti_file
import src.clearsky as cs


# ============================================================
# CONFIGURACIÓN DE LA CORRIDA
# ============================================================

STATION = "TA"

DEFAULT_WINDOW_MINUTES = 120
CSK_MIN_MINUTES = 110

# None -> usa cfg["valid_from"].
START_DATE = None
END_DATE = None

# Fechas específicas a procesar.
# Si queda vacío [], usa START_DATE / END_DATE.
DATES = [
    # "2016-10-01",
]

# True  -> no vuelve a generar figuras existentes.
# False -> regenera las figuras.
SKIP_EXISTING = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera figuras diarias para selección de días claros."
    )
    parser.add_argument(
        "--start",
        default=None,
        help="Fecha inicial YYYY-MM-DD. Sobrescribe START_DATE.",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Fecha final YYYY-MM-DD, inclusive. Sobrescribe END_DATE.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Saltea figuras existentes además del valor de SKIP_EXISTING.",
    )

    # Spyder puede agregar argumentos propios; los ignoramos.
    args, _ = parser.parse_known_args()
    return args


def _as_boolean_series(mask, index: pd.Index) -> pd.Series:
    if isinstance(mask, pd.Series):
        return mask.reindex(index, fill_value=False).astype(bool)

    return pd.Series(mask, index=index, dtype=bool)


def save_screening_plot(
    df: pd.DataFrame,
    ghi_csk,
    clear_mask,
    output_path: Path,
    clear_minutes: float,
) -> None:
    mask = _as_boolean_series(clear_mask, df.index)

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(
        df.index,
        df["gti"],
        linewidth=1.2,
        label="GTI data",
    )

    ax.plot(
        df.index,
        df["ghi"],
        linewidth=1.2,
        label="GHI data",
    )

    if isinstance(ghi_csk, pd.Series):
        ref = ghi_csk.reindex(df.index)
        ax.plot(
            df.index,
            ref,
            linewidth=1.2,
            linestyle="--",
            label="GHI clear-sky",
        )
    else:
        ax.plot(
            df.index,
            ghi_csk,
            linewidth=1.2,
            linestyle="--",
            label="GHI clear-sky",
        )

    if mask.any():
        ax.scatter(
            df.index[mask],
            df.loc[mask, "gti"],
            s=12,
            alpha=0.8,
            color="red",
            label="Clear-sky points",
            zorder=5,
        )

    date = df.index[0].date()
    max_time = df["gti"].idxmax()

    ax.set_title(
        f"{date} | clear alrededor del máximo: {clear_minutes:.0f} min | "
        f"máx GTI: {max_time.strftime('%H:%M')}"
    )
    ax.set_xlabel("Hora")
    ax.set_ylabel("Irradiance [W/m²]")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    cfg = get_station_config(STATION)

    start_value = args.start or START_DATE or cfg["valid_from"]
    end_value = args.end or END_DATE

    start_date = pd.Timestamp(start_value).date()
    end_date = pd.Timestamp(end_value).date() if end_value else None

    selected_dates = {pd.Timestamp(d).date() for d in DATES}
    skip_existing = SKIP_EXISTING or args.skip_existing

    out_dir = REPO_ROOT / cfg["screening_dir"]
    csk_dir = out_dir / "csk"

    out_dir.mkdir(parents=True, exist_ok=True)
    csk_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(REPO_ROOT.glob(cfg["data_glob"]))
    if not files:
        raise FileNotFoundError(
            f"No se encontraron CSV para {STATION} con patrón: "
            f"{REPO_ROOT / cfg['data_glob']}"
        )

    diagnostics = []
    processed = 0
    skipped_existing = 0
    skipped_date = 0
    errors = 0

    print(f"Estación: {STATION}")
    print(f"Datos:    {cfg['data_glob']}")
    print(f"Salida:   {out_dir}")
    print(f"Período:  {start_date} -> {end_date or 'último disponible'}")
    print()

    for file_path in files:
        try:
            df = load_gti_file(file_path, station=STATION)

            if df.empty:
                print(f"[WARN] {file_path.name}: archivo vacío")
                errors += 1
                continue

            date = df.index[0].date()

            if selected_dates:
                if date not in selected_dates:
                    skipped_date += 1
                    continue
            else:
                if date < start_date or (
                    end_date is not None and date > end_date
                ):
                    skipped_date += 1
                    continue

            output_path = out_dir / f"{date}.png"

            if output_path.exists() and skip_existing:
                print(f"[SKIP] {date}: figura ya existente")
                skipped_existing += 1
                continue

            clear_mask, ghi_csk = cs.get_clear_sky_mask(
                df,
                cfg["latitude"],
                cfg["longitude"],
                cfg["tz"],
            )

            clear_minutes = cs.count_clear_sky_minutes_around_max(
                df["gti"],
                clear_mask,
                DEFAULT_WINDOW_MINUTES,
            )

            is_candidate = clear_minutes > CSK_MIN_MINUTES
            mask = _as_boolean_series(clear_mask, df.index)

            save_screening_plot(
                df=df,
                ghi_csk=ghi_csk,
                clear_mask=mask,
                output_path=output_path,
                clear_minutes=clear_minutes,
            )

            if is_candidate:
                candidate_path = csk_dir / output_path.name
                shutil.copy2(output_path, candidate_path)

            diagnostics.append(
                {
                    "station": STATION,
                    "date": date,
                    "file": file_path.name,
                    "source_path": str(file_path.relative_to(REPO_ROOT)),
                    "n_points": len(df),
                    "n_clear": int(mask.sum()),
                    "clear_fraction": float(mask.mean()),
                    "clear_minutes_around_max": clear_minutes,
                    "candidate": is_candidate,
                    "gti_max": float(df["gti"].max()),
                    "gti_max_time": df["gti"].idxmax(),
                    "figure": output_path.name,
                }
            )

            processed += 1
            print(
                f"[OK]   {date} | clear={clear_minutes:.0f} min | "
                f"candidate={is_candidate}"
            )

        except Exception as exc:
            errors += 1
            print(f"[ERROR] {file_path.name}: {exc}")

    if diagnostics:
        summary = pd.DataFrame(diagnostics).sort_values("date")

        summary_path = out_dir / "screening_summary.csv"
        summary.to_csv(summary_path, index=False)

        candidates = summary[summary["candidate"]].copy()
        candidates_path = out_dir / "csk_candidates.csv"
        candidates.to_csv(candidates_path, index=False)

        print(f"\nResumen: {summary_path}")
        print(f"Candidatos clear-sky: {candidates_path}")
        print(f"N candidatos: {len(candidates)}")

    print(
        "\nFinalizado | "
        f"generados={processed} | "
        f"existentes={skipped_existing} | "
        f"fuera_de_rango={skipped_date} | "
        f"errores={errors}"
    )


if __name__ == "__main__":
    main()
