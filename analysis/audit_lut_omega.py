#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov  4 16:36:13 2026

@author: inti
"""


from pathlib import Path

import numpy as np
import pandas as pd
import pvlib as pv

from src.config import get_station_config
from src.clearsky import estimate_omega_star
from src.estimator import AzimuthEstimator


ROOT = Path(__file__).resolve().parents[1]
cfg = get_station_config("AZ")

# Geometría exacta de la LUT histórica de AZ.
lat, lon = -34.9181706, -56.1665725
tilt, albedo = 35.0, 0.25
site = pv.location.Location(lat, lon, tz=cfg["tz"])

cases = [
    ("2026-06-15", 0),
    ("2026-06-16", 10),
    ("2026-06-29", 10),
    ("2026-07-01", 10),
    ("2026-08-09", 20),
    ("2026-08-30", 30),
    ("2026-08-31", 30),
]

estimator = AzimuthEstimator(
    cfg["latitude"], cfg["longitude"], cfg["tilt"],
    ROOT / cfg["lookup_table"],
    station="AZ",
    expected_sha256=cfg["lookup_sha256"],
)

rows = []

for day, gamma in cases:
    doy = pd.Timestamp(day).dayofyear

    times = pd.date_range(
        day, periods=1440, freq="1min", tz=cfg["tz"]
    )

    sp = site.get_solarposition(times)
    cs = site.get_clearsky(times)

    airmass = pv.atmosphere.get_relative_airmass(
        sp.zenith
    )

    poa = pv.irradiance.get_total_irradiance(
        surface_tilt=tilt,
        surface_azimuth=gamma % 360,
        solar_zenith=sp.zenith,
        solar_azimuth=sp.azimuth,
        dni=cs.dni,
        ghi=cs.ghi,
        dhi=cs.dhi,
        dni_extra=pv.irradiance.get_extra_radiation(doy),
        airmass=airmass,
        albedo=albedo,
        model="perez-driesse",
    )

    gti = pd.Series(
        np.asarray(poa["poa_global"], dtype=float),
        index=times,
    )

    # Ángulo horario utilizado por el generador de LUT.
    omega_lut = np.asarray(
        pv.solarposition.hour_angle(
            times, lon, sp.equation_of_time
        )
    )

    # 1. Máximo discreto.
    i_max = np.nanargmax(gti.to_numpy())
    omega_discrete = omega_lut[i_max]

    # 2. Ajuste cuadrático con la EOT de la LUT.
    t_max = times[i_max]
    window = (
        (times > t_max - pd.Timedelta(minutes=60))
        & (times <= t_max + pd.Timedelta(minutes=60))
    )

    a, b, c = np.polyfit(
        omega_lut[window],
        gti.to_numpy()[window],
        2,
    )
    omega_quad_lut = -b / (2 * a)

    # 3. Ajuste cuadrático original, con Spencer.
    df = pd.DataFrame({
        "gti": gti,
        "ghi": cs.ghi,
    })

    fit = estimate_omega_star(
        df, 120, lon, discard=False
    )
    omega_quad_spencer = fit["omega_star"]

    # 4. Comparación con la LUT histórica guardada.
    omega_saved = estimator.ds["omega_star"].sel(
        doy=doy
    ).sel(azimuth=gamma, method="nearest").item()

    gamma_recovered = estimator.estimate(
        omega_quad_spencer, doy
    )

    rows.append({
        "date": day,
        "gamma_true": gamma,
        "omega_discrete": omega_discrete,
        "omega_quad_lut": omega_quad_lut,
        "omega_quad_spencer": omega_quad_spencer,
        "delta_operator": omega_quad_lut - omega_discrete,
        "delta_eot": omega_quad_spencer - omega_quad_lut,
        "delta_total": omega_quad_spencer - omega_discrete,
        "delta_saved_lut": omega_discrete - omega_saved,
        "gamma_recovered": gamma_recovered,
        "gamma_error": gamma_recovered - gamma,
    })

results = pd.DataFrame(rows)

print(results.round(4).to_string(index=False))

out_dir = ROOT / "paper" / "outputs" / "publication_v1" / "tables"
out_dir.mkdir(parents=True, exist_ok=True)

results.to_csv(
    out_dir / "lut_operator_comparison.csv",
    index=False,
)
