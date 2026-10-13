import pandas as pd
from pathlib import Path


from src.loader import load_gti_file
import src.clearsky as cs
from src.estimator import AzimuthEstimator
from src.plotting import save_daily_clearsky_plot, plot_omega_fit


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
    
    files = sorted(Path("data/csk").glob("*.csv"))
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
            df, window_minutes, longitude, discard=discard,
            max_discard_passes=max_discard_passes
        )
        plot_omega_fit(fit_result, date=df.index[0].date())
        
        omega_star=fit_result["omega_star"]
        
        estimator = AzimuthEstimator(
            latitude,longitude,tilt,lookup_table=lookup_dir
        )
        
        azimuth = estimator.estimate(omega_star,doy)
        
        # estimator.estimate(df)
        print(
            f"{df.index[0].date()} | "
            f"ω* = {omega_star:.3f}° | "
            f"Azimut = {azimuth:.1f}°"
        )
        
        results.append({
            "date": df.index[0].date(),
            "doy": doy,
            "omega_star": omega_star,
            "azimuth": azimuth,
            "discarded_pct": fit_result["discarded_pct"],
            "discard_passes": fit_result["discard_passes"],
            "discard_stop_reason": fit_result["discard_stop_reason"],
        })
    
    df_results = pd.DataFrame(results)
    df_diagnostics = pd.DataFrame(diagnostics)
    
    return df_results, df_diagnostics


if __name__ == "__main__":
    df_results, df_diagnostics = main()

    print("\nResultados:")
    print(df_results)
