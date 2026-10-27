import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import get_station_config
from src.loader import load_gti_file
import src.clearsky as cs
from src.estimator import AzimuthEstimator
from src.plotting import save_daily_clearsky_plot, plot_omega_fit


# ============================================================
# CONFIGURACIÓN DE LA CORRIDA
# ============================================================

STATION = "TA"

WINDOW_MINUTES = 120
DISCARD = True
MAX_DISCARD_PASSES = 3


def get_nominal_azimuth(date, schedule):
    """Devuelve el azimut nominal vigente en una fecha, si existe."""
    if not schedule:
        return None

    date = pd.Timestamp(date)
    nominal = None

    for start_date, value in schedule:
        if date >= pd.Timestamp(start_date):
            nominal = value
        else:
            break

    return nominal


def main():
    cfg = get_station_config(STATION)

    latitude = cfg["latitude"]
    longitude = cfg["longitude"]
    tilt = cfg["tilt"]
    tz_est = cfg["tz"]
    nominal_schedule = cfg.get("nominal_azimuth_schedule")

    diagnostics = []
    results = []

    candidates_path = REPO_ROOT / cfg["screening_dir"] / "csk_candidates.csv"
    if not candidates_path.exists():
        raise FileNotFoundError(
            f"No existe {candidates_path}. "
            f"Corré primero analysis/generate_daily_screening.py "
            f"con STATION={STATION!r}."
        )

    candidates = pd.read_csv(candidates_path)
    if candidates.empty:
        raise RuntimeError(
            f"{candidates_path} no contiene candidatos clear-sky."
        )

    if "file" not in candidates.columns:
        raise ValueError(
            f"{candidates_path} no contiene la columna 'file'."
        )

    candidate_names = set(candidates["file"].astype(str))

    all_files = sorted(REPO_ROOT.glob(cfg["data_glob"]))
    files = [f for f in all_files if f.name in candidate_names]

    found_names = {f.name for f in files}
    missing_names = sorted(candidate_names - found_names)
    if missing_names:
        print(
            f"[WARN] {len(missing_names)} candidatos no tienen CSV disponible."
        )
        for name in missing_names[:10]:
            print(f"       {name}")
        if len(missing_names) > 10:
            print("       ...")

    if not files:
        raise FileNotFoundError(
            f"No se encontraron archivos candidatos para {STATION}."
        )

    lookup_dir = REPO_ROOT / cfg["lookup_table"]

    print(f"Estación: {STATION}")
    print(f"Tilt:     {tilt:.1f}°")
    print(f"Casos:    {len(files)}")
    print()

    for f in files:
        print(f.name)

        df = load_gti_file(f, station=STATION)

        gti_max_time = df["gti"].idxmax()
        
        date = gti_max_time.date()
        doy = gti_max_time.dayofyear

        msk_clearsky, ghi_csk = cs.get_clear_sky_mask(
            df,
            latitude,
            longitude,
            tz_est,
        )

        clear_minutes = cs.count_clear_sky_minutes_around_max(
            df["gti"],
            msk_clearsky,
            WINDOW_MINUTES,
        )

        diagnostics.append(
            {
                "station": STATION,
                "date": date,
                "file": f.name,
                "clear_minutes": clear_minutes,
                "gti_max_time": gti_max_time,
            }
        )

        save_daily_clearsky_plot(df, ghi_csk, msk_clearsky)

        fit_result = cs.estimate_omega_star(
            df,
            WINDOW_MINUTES,
            longitude,
            discard=DISCARD,
            max_discard_passes=MAX_DISCARD_PASSES,
        )

        omega_star = fit_result["omega_star"]

        estimator = AzimuthEstimator(
            latitude,
            longitude,
            tilt,
            lookup_table=lookup_dir,
        )
        
        lookup_year = cfg.get("lookup_reference_year", 2026)

        lookup_date = pd.Timestamp(
            year=lookup_year,
            month=date.month,
            day=date.day,
        )
        
        lookup_doy = lookup_date.dayofyear

        azimuth = estimator.estimate(omega_star, lookup_doy)

        azimuth_nominal = get_nominal_azimuth(
            date,
            nominal_schedule,
        )

        plot_omega_fit(
            fit_result,
            date=date,
            azimuth=azimuth,
            azimuth_nominal=azimuth_nominal,
        )

        print(
            f"{date} | "
            f"ω* = {omega_star:.3f}° | "
            f"Azimut = {azimuth:.1f}°"
        )

        result = {
            "station": STATION,
            "date": date,
            "doy": doy,
            "tilt": tilt,
            "omega_star": omega_star,
            "azimuth": azimuth,
            "discarded_pct": fit_result["discarded_pct"],
            "discard_passes": fit_result["discard_passes"],
            "discard_stop_reason": fit_result["discard_stop_reason"],
        }

        # AZ tiene referencia nominal; TA no.
        if azimuth_nominal is not None:
            azimuth_error = (
                (azimuth_nominal - azimuth + 180) % 360
            ) - 180

            result.update(
                {
                    "azimuth_nominal": azimuth_nominal,
                    "azimuth_error_deg": azimuth_error,
                    "azimuth_abs_error_deg": abs(azimuth_error),
                }
            )

        results.append(result)

    df_results = pd.DataFrame(results)
    df_diagnostics = pd.DataFrame(diagnostics)

    output_dir = REPO_ROOT / cfg["results_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")

    results_path = output_dir / f"azimuth_results_{timestamp}.csv"
    diagnostics_path = output_dir / f"azimuth_diagnostics_{timestamp}.csv"

    df_results.to_csv(results_path, index=False)
    df_diagnostics.to_csv(diagnostics_path, index=False)

    print(f"\nResultados guardados en: {results_path}")
    print(f"Diagnóstico guardado en: {diagnostics_path}")

    return df_results, df_diagnostics


if __name__ == "__main__":
    df_results, df_diagnostics = main()

    print("\nResultados:")
    print(df_results)
