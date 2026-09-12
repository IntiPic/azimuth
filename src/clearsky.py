import pvlib as pv
import pandas as pd
import numpy as np

def get_clear_sky_mask(df,latitude,longitude,tz_est,altitude=None):
    """
    Devuelve una máscara booleana indicando
    los minutos considerados de cielo claro.
    """
    
    times = df.index
    loc = pv.location.Location(latitude, longitude, tz_est, altitude)
    df_csk = loc.get_clearsky(times)
    
    msk_csk = pv.clearsky.detect_clearsky(df['ghi'], df_csk['ghi'])
                                          

    return msk_csk, df_csk["ghi"]



def count_clear_sky_minutes_around_max(gti,clear_mask,window_minutes=60):
      
    t_max = gti.idxmax()
    half_window = pd.Timedelta(minutes=window_minutes/2)
    msk_tmax = ((t_max - half_window < gti.index) & 
                (gti.index <= t_max + half_window))
    
    count = clear_mask[msk_tmax].sum()
    
    
    return count

def estimate_omega_star(day_df, window_minutes, longitude):
    
    gti = day_df.gti
    equation_of_time = pv.solarposition.equation_of_time_spencer71(gti.index.day_of_year.unique())
    t_max = gti.idxmax()
    half_window = pd.Timedelta(minutes=window_minutes/2)
    msk_tmax = ((t_max - half_window < gti.index) & 
                (gti.index <= t_max + half_window))
    times = gti.loc[msk_tmax].index
    hour_angle = pv.solarposition.hour_angle(times, longitude, equation_of_time)
    
    omega = np.asarray(hour_angle)
    y = np.asarray(gti.loc[msk_tmax])
    
    mask = np.isfinite(omega) & np.isfinite(y)
    
    omega = omega[mask]
    y = y[mask]
    
    while True:
        coef = np.polyfit(omega, y, 2)
        y_fit = np.polyval(coef, omega)
        residuals = y - y_fit
        sigma = residuals.std(ddof=1)
        worst = np.argmax(np.abs(residuals))
        if np.abs(residuals[worst]) <= 2*sigma:
            break
    
        omega = np.delete(omega, worst)
        y = np.delete(y, worst)
    
        if len(omega) < 6:
            break
    a, b, c = coef

    omega_star = -b/(2*a)
    gti_star = np.polyval(coef, omega_star)
    
    return {
        'omega': omega,
        'gti': y,
        'coef': coef,
        'omega_star': omega_star,
        'gti_star': gti_star,
    }