import pandas as pd
from pathlib import Path


from src.loader import load_gti_file
import src.clearsky as cs
from src.estimator import AzimuthEstimator
from src.plotting import save_daily_clearsky_plot, plot_omega_fit

NOMINAL_AZIMUTH_SCHEDULE = [
    # ("fecha desde la que aplica", azimut nominal)
    ("2026-05-21", 0.0),
    ("2026-06-16", 10.0),
    ("2026-07-06", 20.0),
    ("2026-08-24", 30.0),
    ("2026-09-22", 40.0),
    # completar con los cambios reales
]

def get_nominal_azimuth(date):
    date = pd.Timestamp(date)

    nominal = None

    for start_date, value in NOMINAL_AZIMUTH_SCHEDULE:
        if date >= pd.Timestamp(start_date):
            nominal = value
        else:
            break

    return nominal

def main():
    
    latitude = -34.918034
    longitude = -56.166802
    tilt = 35
    tz_est= "America/Montevideo"
    window_minutes =120
    discard = True  # False: sin descarte; True: descarte por 2σ
    max_discard_passes = 3
    
    diagnostics = []
    results = []
    
    candidates = pd.read_csv("outputs/screening/csk_candidates.csv")

    candidate_dates = pd.to_datetime(candidates["date"]).dt.strftime("%Y%m%d")
    
    all_files = list(Path("data/all").glob("*.csv"))
    
    files = [
        f for f in all_files
        if any(date in f.name for date in candidate_dates)
    ]
    
    files = sorted(files)
    
    lookup_dir = Path("OUT") / "lookup_omega_gamma.nc"
    
    for f in files:
        print(f.name)

        df = load_gti_file(f)
        doy = df.index.dayofyear.unique()[0]
        # print("\nPrimeras filas:")
        # print(df.head())
    
        #print(f"\nCantidad de filas: {len(df)}")
        
        msk_clearsky,ghi_csk = cs.get_clear_sky_mask(df, latitude, longitude, tz_est)
        clear_minutes = cs.count_clear_sky_minutes_around_max(df["gti"],
                                                           msk_clearsky,window_minutes)
        
        diagnostics.append({
            "date": df.index[0].date(),
            "clear_minutes": clear_minutes,
            "gti_max_time": df["gti"].idxmax(),
        })
        
        save_daily_clearsky_plot(df, ghi_csk, msk_clearsky)
        
        fit_result = cs.estimate_omega_star(
            df,
            window_minutes,
            longitude,
            discard=discard,
            max_discard_passes=max_discard_passes,
        )
        
        omega_star = fit_result["omega_star"]
        
        estimator = AzimuthEstimator(
            latitude,
            longitude,
            tilt,
            lookup_table=lookup_dir,
        )
        
        azimuth = estimator.estimate(omega_star, doy)
        
        date = df.index[0].date()
        azimuth_nominal = get_nominal_azimuth(date)
        
        plot_omega_fit(
            fit_result,
            date=date,
            azimuth=azimuth,
            azimuth_nominal=azimuth_nominal,
        )
        
        date = df.index[0].date()
        
        azimuth_nominal = get_nominal_azimuth(date)
        
        if azimuth_nominal is not None:
            azimuth_error = (
                (azimuth_nominal - azimuth + 180) % 360
            ) - 180
        
            azimuth_abs_error = abs(azimuth_error)
        else:
            azimuth_error = None
            azimuth_abs_error = None
        
        # estimator.estimate(df)
        print(
            f"{df.index[0].date()} | "
            f"ω* = {omega_star:.3f}° | "
            f"Azimut = {azimuth:.1f}°"
        )
        
        results.append({
            "date": date,
            "doy": doy,
            "omega_star": omega_star,
            "azimuth": azimuth,
            "azimuth_nominal": azimuth_nominal,
            "azimuth_error_deg": azimuth_error,
            "azimuth_abs_error_deg": azimuth_abs_error,
            "discarded_pct": fit_result["discarded_pct"],
            "discard_passes": fit_result["discard_passes"],
            "discard_stop_reason": fit_result["discard_stop_reason"],
        })
    
    
    df_results = pd.DataFrame(results)
    df_diagnostics = pd.DataFrame(diagnostics)
    
    # Guardo salidas
    output_dir = Path("outputs")
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
