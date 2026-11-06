#!/usr/bin/env python3
"""
Genera gráficos diarios para el screening de candidatos a cielo claro.

No estima omega_star ni azimut. La estación se selecciona con --station
(por defecto STATION) y sus particularidades se leen desde src/config.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pvlib


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

# La caché incremental está activa por defecto. --force la ignora.


def parse_args(default_station=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera figuras diarias para selección de días claros."
    )
    parser.add_argument(
        "--station",
        choices=("AZ", "TA"),
        default=default_station or STATION,
        help="Estación a procesar (AZ o TA).",
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
        help="Compatibilidad: la reutilización incremental ya es el modo predeterminado.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recalcula todos los días, ignorando la caché.",
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
        f"{date} | clear around GTI maximum: {clear_minutes:.0f} min | "
        f"GTI maximum: {max_time.strftime('%H:%M')}"
    )
    ax.set_xlabel("Time")
    ax.set_ylabel("Irradiance [W/m²]")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _screening_signature(cfg: dict) -> str:
    """Invalidar caché si cambia el método, config o dependencias principales."""
    source_files = [
        Path(__file__),
        REPO_ROOT / "src" / "clearsky.py",
        REPO_ROOT / "src" / "loader.py",
        REPO_ROOT / "src" / "config.py",
    ]
    metadata = {
        "sources": {
            str(path.relative_to(REPO_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_files
        },
        "config": {
            key: cfg.get(key)
            for key in ("latitude", "longitude", "tz", "altitude", "data_glob", "valid_from")
        },
        "window_minutes": DEFAULT_WINDOW_MINUTES,
        "minimum_clear_minutes": CSK_MIN_MINUTES,
        "pvlib_version": pvlib.__version__,
        "pandas_version": pd.__version__,
    }
    raw = json.dumps(metadata, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _cached_rows(path: Path) -> dict:
    """Caché de diagnósticos, nunca basada solamente en la existencia de un PNG."""
    if not path.is_file():
        return {}
    try:
        previous = pd.read_csv(path, dtype=str, keep_default_na=False)
        mandatory = {
            "source_path", "source_size", "source_mtime_ns",
            "screening_signature", "date", "candidate", "figure",
        }
        if not mandatory.issubset(previous.columns):
            print("[INFO] Resumen anterior sin huella de caché; recálculo inicial.")
            return {}
        if previous["source_path"].duplicated().any():
            print("[WARN] Resumen previo con archivos duplicados; se recalculará.")
            return {}
        return {row["source_path"]: row.to_dict() for _, row in previous.iterrows()}
    except (OSError, ValueError) as exc:
        print(f"[WARN] No se pudo reutilizar el resumen anterior: {exc}")
        return {}


def _date_in_range(date, selected_dates, start_date, end_date) -> bool:
    if selected_dates:
        return date in selected_dates
    return date >= start_date and (end_date is None or date <= end_date)


def _date_from_filename(path: Path):
    """Optimización: evita abrir CSV excluidos por fecha, si el nombre es estándar."""
    found = re.search(r"_DT_(\d{8})T", path.name)
    if not found:
        return None
    try:
        return pd.to_datetime(found.group(1), format="%Y%m%d").date()
    except ValueError:
        return None


def _write_csv_atomically(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def main(default_station=None) -> None:
    args = parse_args(default_station)
    station = args.station
    cfg = get_station_config(station)

    start_value = args.start or START_DATE or cfg["valid_from"]
    end_value = args.end or END_DATE
    start_date = pd.Timestamp(start_value).date()
    end_date = pd.Timestamp(end_value).date() if end_value else None
    selected_dates = {pd.Timestamp(d).date() for d in DATES}

    out_dir = REPO_ROOT / cfg["screening_dir"]
    csk_dir = out_dir / "csk"
    out_dir.mkdir(parents=True, exist_ok=True)
    csk_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(REPO_ROOT.glob(cfg["data_glob"]))
    if not files:
        raise FileNotFoundError(f"No se encontraron CSV: {REPO_ROOT / cfg['data_glob']}")

    signature = _screening_signature(cfg)
    # Una corrida parcial no reemplaza la lista canónica de candidatos.
    partial_run = bool(
        selected_dates or args.start is not None or args.end is not None
        or START_DATE is not None or END_DATE is not None
    )
    canonical_path = out_dir / "screening_summary.csv"
    summary_path = out_dir / (
        "screening_subset_summary.csv" if partial_run else "screening_summary.csv"
    )
    candidates_path = out_dir / (
        "csk_candidates_subset.csv" if partial_run else "csk_candidates.csv"
    )
    previous = {} if args.force else _cached_rows(canonical_path)

    diagnostics = []
    processed = reused = skipped_date = errors = 0
    print(f"Estación: {station} | datos: {cfg['data_glob']}")
    print(f"Período: {start_date} -> {end_date or 'último disponible'}")
    print(f"Caché: {'desactivada (--force)' if args.force else 'incremental'}")

    for file_path in files:
        try:
            named_date = _date_from_filename(file_path)
            if named_date is not None and not _date_in_range(
                named_date, selected_dates, start_date, end_date
            ):
                skipped_date += 1
                continue

            relative = str(file_path.relative_to(REPO_ROOT))
            stat = file_path.stat()
            output_date = named_date
            cached = previous.get(relative)

            # Sólo reutilizar filas verificadas contra el origen, el código y el PNG.
            if cached is not None:
                try:
                    cached_date = pd.Timestamp(cached["date"]).date()
                    cached_figure = out_dir / cached["figure"]
                    cache_valid = (
                        cached["station"] == station
                        and cached["screening_signature"] == signature
                        and int(cached["source_size"]) == stat.st_size
                        and int(cached["source_mtime_ns"]) == stat.st_mtime_ns
                        and cached_figure.is_file()
                        and (named_date is None or named_date == cached_date)
                    )
                    if cache_valid and _date_in_range(
                        cached_date, selected_dates, start_date, end_date
                    ):
                        row = dict(cached)
                        row["candidate"] = str(row["candidate"]).lower() == "true"
                        candidate_plot = csk_dir / cached_figure.name
                        if row["candidate"] and not candidate_plot.is_file():
                            shutil.copy2(cached_figure, candidate_plot)
                        elif not row["candidate"] and candidate_plot.is_file():
                            candidate_plot.unlink()
                        diagnostics.append(row)
                        reused += 1
                        continue
                except (KeyError, TypeError, ValueError):
                    pass  # Dato de caché inválido: calcular de nuevo.

            df = load_gti_file(file_path, station=station)
            if df.empty:
                raise ValueError("Archivo vacío")
            date = df.index[0].date()
            if not _date_in_range(date, selected_dates, start_date, end_date):
                skipped_date += 1
                continue
            if output_date is not None and output_date != date:
                print(f"[WARN] {file_path.name}: fecha del CSV {date} != nombre {output_date}")

            output_path = out_dir / f"{date}.png"
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", RuntimeWarning)
                clear_mask, ghi_csk = cs.get_clear_sky_mask(
                    df, cfg["latitude"], cfg["longitude"], cfg["tz"]
                )
                clear_minutes = cs.count_clear_sky_minutes_around_max(
                    df["gti"], clear_mask, DEFAULT_WINDOW_MINUTES
                )

            warning_text = "; ".join(str(w.message) for w in caught)
            if warning_text:
                print(f"[WARN] {date}: {warning_text}")
            is_candidate = bool(clear_minutes > CSK_MIN_MINUTES)
            mask = _as_boolean_series(clear_mask, df.index)

            save_screening_plot(
                df=df, ghi_csk=ghi_csk, clear_mask=mask,
                output_path=output_path, clear_minutes=clear_minutes,
            )
            candidate_path = csk_dir / output_path.name
            if is_candidate:
                shutil.copy2(output_path, candidate_path)
            elif candidate_path.exists():
                candidate_path.unlink()

            diagnostics.append({
                "station": station,
                "date": str(date),
                "file": file_path.name,
                "source_path": relative,
                "n_points": len(df),
                "n_clear": int(mask.sum()),
                "clear_fraction": float(mask.mean()),
                "clear_minutes_around_max": clear_minutes,
                "candidate": is_candidate,
                "gti_max": float(df["gti"].max()),
                "gti_max_time": str(df["gti"].idxmax()),
                "figure": output_path.name,
                "source_size": stat.st_size,
                "source_mtime_ns": stat.st_mtime_ns,
                "screening_signature": signature,
                "warning_count": len(caught),
                "warning_text": warning_text,
            })
            processed += 1
            print(f"[NEW] {date} | clear={clear_minutes:.0f} min | candidate={is_candidate}")

        except Exception as exc:
            errors += 1
            print(f"[ERROR] {file_path.name}: {exc}")

    if errors:
        raise RuntimeError(
            f"Screening incompleto: {errors} errores. "
            "No se sobrescribieron los CSV de screening; se detiene el pipeline."
        )
    if not diagnostics:
        raise RuntimeError("No se procesó ni reutilizó ningún día dentro del rango.")

    summary = pd.DataFrame(diagnostics).sort_values(["date", "file"])
    summary["candidate"] = summary["candidate"].map(
        lambda value: value if isinstance(value, bool) else str(value).lower() == "true"
    )
    candidates = summary.loc[summary["candidate"]].copy()

    _write_csv_atomically(summary, summary_path)
    _write_csv_atomically(candidates, candidates_path)

    # Eliminar candidatos gráficos obsoletos sólo en corridas completas.
    if not partial_run:
        active_figures = set(candidates["figure"].astype(str))
        for old_figure in csk_dir.glob("*.png"):
            if old_figure.name not in active_figures:
                old_figure.unlink()

    print(f"\nResumen: {summary_path}")
    print(f"Candidatos clear-sky: {candidates_path}")
    print(f"N candidatos: {len(candidates)}")
    if partial_run:
        print("[INFO] Corrida parcial: no se modificaron los CSV canónicos para main.py.")
    print(
        "Finalizado | "
        f"calculados={processed} | reutilizados={reused} | "
        f"fuera_de_rango={skipped_date} | errores={errors}"
    )


if __name__ == "__main__":
    main()
