import pvlib as pv
import pandas as pd

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