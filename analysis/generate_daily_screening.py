#!/usr/bin/env python3
"""
Genera gráficos diarios para el screening visual de candidatos a cielo claro.

Este script NO estima omega_star ni azimut. Su única función es:
1) cargar cada CSV diario;
2) calcular la máscara clear-sky usando la lógica existente del proyecto;
3) generar una figura por día para inspección visual;
4) guardar un resumen diagnóstico simple.

Ejemplo:
    python analysis/generate_daily_screening.py

Por defecto:
    datos:   data/all/
    figuras: outputs/screening/
    inicio:  2026-05-21

Para saltear figuras ya existentes:
    python analysis/generate_daily_screening.py --skip-existing
"""

from __future__ import annotations

import shutil
import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


# Permite ejecutar el script directamente desde analysis/ sin instalar el paquete.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.loader import load_gti_file
import src.clearsky as cs


DEFAULT_LATITUDE = -34.918034
DEFAULT_LONGITUDE = -56.166802
DEFAULT_TZ = "America/Montevideo"
DEFAULT_WINDOW_MINUTES = 120
DEFAULT_START_DATE = "2026-05-21"

CSK_MIN_MINUTES = 110 #Limite de minutos claros para seleccionar el día
# ============================================================
# CONFIGURACIÓN DE LA CORRIDA
# ============================================================

START_DATE = "2026-05-21"
END_DATE = None

# Fechas específicas a procesar.
# Si queda vacío [], usa START_DATE / END_DATE.
DATES = [
    # "2026-06-15",
    # "2026-07-01",
    # "2026-08-09",
]

# True  -> no vuelve a generar figuras existentes
# False -> regenera las figuras
SKIP_EXISTING = False



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera figuras diarias para selección visual de días claros."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / "data" / "all",
        help="Carpeta con los CSV diarios (default: data/all).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "screening",
        help="Carpeta de salida para las figuras (default: outputs/screening).",
    )
    parser.add_argument(
        "--start",
        default=DEFAULT_START_DATE,
        help=f"Fecha inicial YYYY-MM-DD (default: {DEFAULT_START_DATE}).",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Fecha final YYYY-MM-DD, inclusive. Si se omite, procesa hasta el último día disponible.",
    )
    parser.add_argument(
        "--latitude",
        type=float,
        default=DEFAULT_LATITUDE,
        help=f"Latitud de la estación (default: {DEFAULT_LATITUDE}).",
    )
    parser.add_argument(
        "--longitude",
        type=float,
        default=DEFAULT_LONGITUDE,
        help=f"Longitud de la estación (default: {DEFAULT_LONGITUDE}).",
    )
    parser.add_argument(
        "--tz",
        default=DEFAULT_TZ,
        help=f"Zona horaria (default: {DEFAULT_TZ}).",
    )
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=DEFAULT_WINDOW_MINUTES,
        help=f"Ventana alrededor del máximo para diagnóstico (default: {DEFAULT_WINDOW_MINUTES} min).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Saltea figuras que ya existen. Por defecto se regeneran todas.",
    )
    return parser.parse_args()


def _as_boolean_series(mask, index: pd.Index) -> pd.Series:
    """Normaliza la máscara clear-sky a una Serie booleana alineada con df."""
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
    """Guarda una figura simple para inspección visual del día."""
        
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
    
    # Referencia teórica de cielo claro para GHI
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

    start_date = pd.Timestamp(START_DATE).date()
    end_date = pd.Timestamp(END_DATE).date() if END_DATE else None
    
    selected_dates = {
        pd.Timestamp(d).date()
        for d in DATES
    }

    if not args.data_dir.exists():
        raise FileNotFoundError(
            f"No existe la carpeta de datos: {args.data_dir}\n"
            "Usá --data-dir para indicar la ubicación correcta."
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    
    csk_dir = args.out_dir / "csk"
    csk_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(args.data_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No se encontraron CSV en {args.data_dir}")

    diagnostics = []
    processed = 0
    skipped_existing = 0
    skipped_date = 0
    errors = 0

    print(f"Datos:   {args.data_dir}")
    print(f"Salida:  {args.out_dir}")
    print(f"Período: {start_date} -> {end_date or 'último disponible'}")
    print()

    for file_path in files:
        try:
            df = load_gti_file(file_path)

            if df.empty:
                print(f"[WARN] {file_path.name}: archivo vacío")
                errors += 1
                continue

            date = df.index[0].date()

            if selected_dates:
                # Modo: fechas específicas
                if date not in selected_dates:
                    skipped_date += 1
                    continue
            else:
                # Modo: rango de fechas
                if date < start_date or (end_date is not None and date > end_date):
                    skipped_date += 1
                    continue

            output_path = args.out_dir / f"{date}.png"

            if output_path.exists() and SKIP_EXISTING:
                print(f"[SKIP] {date}: figura ya existente")
                skipped_existing += 1
                continue

            clear_mask, ghi_csk = cs.get_clear_sky_mask(
                df,
                args.latitude,
                args.longitude,
                args.tz,
            )

            clear_minutes = cs.count_clear_sky_minutes_around_max(
                df["gti"],
                clear_mask,
                args.window_minutes,
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
                    "date": date,
                    "file": file_path.name,
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
            print(f"[OK]   {date} -> {output_path.name}")

        except Exception as exc:
            errors += 1
            print(f"[ERROR] {file_path.name}: {exc}")

    if diagnostics:
        summary = pd.DataFrame(diagnostics).sort_values("date")
    
        summary_path = args.out_dir / "screening_summary.csv"
        summary.to_csv(summary_path, index=False)
    
        candidates = summary[summary["candidate"]].copy()
    
        candidates_path = args.out_dir / "csk_candidates.csv"
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
