import pandas as pd
from pathlib import Path


from src.loader import load_gti_file
from src.clearsky import get_clear_sky_mask,count_clear_sky_minutes_around_max
from src.estimator import AzimuthEstimator
from src.plotting import save_daily_clearsky_plot


def main():
    
    latitude = -34.918034
    longitude = -56.166802
    tilt = 35
    tz_est= "America/Montevideo"
    window_minutes =60
    
    diagnostics = []
    
    files = sorted(Path("data").glob("*.csv"))
    
    for i, f in enumerate(files):
        print(i, f.name)

        df = load_gti_file(f)
    
        # print("\nPrimeras filas:")
        # print(df.head())
    
        #print(f"\nCantidad de filas: {len(df)}")
        
        msk_clearsky,ghi_csk = get_clear_sky_mask(df, latitude, longitude, tz_est)
        clear_minutes = count_clear_sky_minutes_around_max(df["gti"],
                                                           msk_clearsky,window_minutes)
        
        diagnostics.append({
            "date": df.index[0].date(),
            "clear_minutes": clear_minutes,
            "gti_max_time": df["gti"].idxmax(),
        })
        
        save_daily_clearsky_plot(df, ghi_csk, msk_clearsky)
        
        estimator = AzimuthEstimator(latitude,longitude,tilt)
        
        estimator.estimate(df)
    
    df_diagnostics = pd.DataFrame(diagnostics)
    
    return df_diagnostics


if __name__ == "__main__":
    df_diagnostics = main()
    # df, msk_clearsky, ghi_csk = main()
    
    