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

def estimate_omega_star(day_df, window_minutes, longitude, discard=True,
                        max_discard_passes=1):
    """Ajusta GTI directamente contra el ángulo horario real en grados.

    Con discard=True realiza hasta max_discard_passes evaluaciones de 2σ
    (residuos en W/m²), con descarte simultáneo y reajuste si elimina puntos.
    Con False usa el ajuste inicial. gti contiene las mediciones originales
    conservadas en W/m² y coef corresponde exactamente a ese conjunto final.

    discard_passes cuenta cada evaluación, incluso si no elimina puntos.
    discard_stop_reason es disabled, no_new_outliers o max_passes_reached.
    Al alcanzar el límite se conserva el último reajuste sin comprobar otra
    vez sus residuos: no se afirma convergencia del descarte.

    n_window cuenta todas las filas de la ventana temporal, antes del filtro
    numérico. n_nonfinite cuenta las excluidas por GTI o ángulo no finitos;
    no se incluyen en n_discarded, que cuenta solo descartes aplicados por 2σ.
    discarded_pct = 100 * n_discarded / n_window acumula todas las pasadas.
    Los arrays de descartes conservan ángulos, timestamps y GTI originales
    de todas las exclusiones por 2σ, en el orden de las filas de entrada.
    """
    if not isinstance(discard, (bool, np.bool_)):
        raise ValueError("discard debe ser True o False.")
    if (isinstance(max_discard_passes, (bool, np.bool_))
            or not isinstance(max_discard_passes, (int, np.integer))
            or max_discard_passes <= 0):
        raise ValueError("max_discard_passes debe ser un entero positivo.")

    gti = day_df.gti
    t_max = gti.idxmax()
    half_window = pd.Timedelta(minutes=window_minutes/2)
    msk_tmax = ((t_max - half_window < gti.index) & 
                (gti.index <= t_max + half_window))
    times = gti.loc[msk_tmax].index
    equation_of_time = pv.solarposition.equation_of_time_spencer71(
        times.dayofyear.to_numpy())

    n_window = len(times)
    hour_angle = pv.solarposition.hour_angle(
        times,
        longitude,
        equation_of_time,
    )
    
    omega = np.asarray(hour_angle)
    y = np.asarray(gti.loc[msk_tmax], dtype=float)
    
    mask = np.isfinite(omega) & np.isfinite(y)
    n_nonfinite = int((~mask).sum())
    
    omega = omega[mask]
    y = y[mask]
    candidate_times = times[mask]
    
    if len(omega) < 6:
        raise ValueError(
            f"Se requieren al menos seis puntos finitos en la ventana; hay {len(omega)}."
        )

    coef, _, rank, _, _ = np.polyfit(omega, y, 2, full=True)
    if rank < 3 or not np.all(np.isfinite(coef)):
        raise ValueError("El ajuste inicial no determina un polinomio cuadrático válido.")

    # Mantener los candidatos originales y una máscara acumulada sin reincorporaciones.
    candidate_omega = omega
    candidate_gti = y
    keep = np.ones(len(omega), dtype=bool)
    discard_passes = 0
    discard_stop_reason = 'disabled'
    if discard:
        discard_stop_reason = 'max_passes_reached'
        for _ in range(max_discard_passes):
            discard_passes += 1
            y_fit = np.polyval(coef, omega)
            residuals = y - y_fit
            sigma = residuals.std(ddof=1)
            if not np.all(np.isfinite(residuals)) or not np.isfinite(sigma):
                raise ValueError(
                    f"Los residuos o sigma de la pasada {discard_passes} no son finitos."
                )
            # Una clasificación simultánea por pasada, sobre los participantes actuales.
            rejected = np.abs(residuals) > 2*sigma
            if not rejected.any():
                discard_stop_reason = 'no_new_outliers'
                break

            keep[np.flatnonzero(keep)[rejected]] = False
            omega = candidate_omega[keep]
            y = candidate_gti[keep]
            if len(omega) < 6:
                raise ValueError(
                    f"La pasada {discard_passes} de 2σ dejó {len(omega)} puntos; "
                    "se requieren al menos seis."
                )
            # Reajuste obligatorio incluso en la última pasada permitida.
            coef, _, rank, _, _ = np.polyfit(omega, y, 2, full=True)
            if rank < 3 or not np.all(np.isfinite(coef)):
                raise ValueError(
                    f"El reajuste de la pasada {discard_passes} no determina "
                    "un polinomio cuadrático válido."
                )

    omega_discarded = candidate_omega[~keep]
    gti_discarded = candidate_gti[~keep]
    n_discarded = int((~keep).sum())

    a, b, c = coef
    if a >= 0:
        raise ValueError("El polinomio final no tiene un máximo: se requiere a < 0.")

    omega_star = -b/(2*a)
    if not np.isfinite(omega_star) or not omega.min() < omega_star < omega.max():
        raise ValueError(
            "El vértice final no es un máximo interior al intervalo de ángulos conservados."
        )
    gti_star = np.polyval(coef, omega_star)
    if not np.isfinite(gti_star):
        raise ValueError("La GTI del máximo final no es finita.")
    
    return {
        'omega': omega,
        'gti': y,
        'coef': coef,
        'discard': discard,
        'max_discard_passes': max_discard_passes,
        'discard_passes': discard_passes,
        'discard_stop_reason': discard_stop_reason,
        'times': candidate_times[keep],
        'times_discarded': candidate_times[~keep],
        'omega_discarded': omega_discarded,
        'gti_discarded': gti_discarded,
        'n_window': n_window,
        'n_nonfinite': n_nonfinite,
        'n_discarded': n_discarded,
        'discarded_pct': 100 * n_discarded / n_window,
        'omega_star': omega_star,
        'gti_star': gti_star,
    }
