#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build annual omega* <-> surface-azimuth LUT for one station.

Station geometry and output path are read from src/config.py.
The LUT is built on a fixed non-leap reference year (2026).
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pvlib as pv
import pytz
import xarray as xr

from src.config import get_station_config


# ============================================================
# CONFIGURACIÓN DE LA CORRIDA
# ============================================================

STATION = "TA"

ALBEDO = 0.20
AZIMUTH_MIN = -90.0
AZIMUTH_MAX = 90.0
AZIMUTH_STEP = 0.1

REFERENCE_YEAR = None  # None -> usa cfg["lookup_reference_year"] o 2026
SAVE_DAILY_FIGURES = True


# ============================================================
# CONFIGURACIÓN DE ESTACIÓN Y RUTAS
# ============================================================

REPO_ROOT = Path(__file__).resolve().parent
cfg = get_station_config(STATION)

if REFERENCE_YEAR is None:
    REFERENCE_YEAR = cfg.get("lookup_reference_year", 2026)

lat = cfg["latitude"]
lon = cfg["longitude"]
surface_tilt = cfg["tilt"]
tz_est = pytz.timezone(cfg["tz"])

lookup_path = REPO_ROOT / cfg["lookup_table"]
lookup_path.parent.mkdir(parents=True, exist_ok=True)

out_dir = lookup_path.parent
fig_dir = REPO_ROOT / "FIG" / STATION / "omega_gamma"
fig_dir.mkdir(parents=True, exist_ok=True)

site = pv.location.Location(
    latitude=lat,
    longitude=lon,
    tz=tz_est,
)

azimuths = np.arange(
    AZIMUTH_MIN,
    AZIMUTH_MAX + AZIMUTH_STEP / 2,
    AZIMUTH_STEP,
)

dias_del_anio = pd.date_range(
    start=f"{REFERENCE_YEAR}-01-01",
    end=f"{REFERENCE_YEAR}-12-31",
    freq="D",
    tz=tz_est,
)

if len(dias_del_anio) != 365:
    raise ValueError(
        f"REFERENCE_YEAR={REFERENCE_YEAR} debe ser no bisiesto."
    )

omega_ast_anual = np.zeros(
    (len(dias_del_anio), len(azimuths))
)


# ============================================================
# GENERACIÓN DE LA LUT
# ============================================================

plt.rcParams.update({"font.size": 16})

print(f"Estación:       {STATION}")
print(f"Lat/Lon:        {lat}, {lon}")
print(f"Tilt:           {surface_tilt:.1f}°")
print(f"Reference year: {REFERENCE_YEAR}")
print(f"LUT output:     {lookup_path}")
print()

for idx_dia, dia in enumerate(dias_del_anio):

    times = pd.date_range(
        start=dia,
        end=dia + pd.Timedelta(hours=23, minutes=59),
        freq="1min",
        tz=site.tz,
    )
    doy = dia.dayofyear

    solar_position = site.get_solarposition(times=times)
    clearsky = site.get_clearsky(times)

    hour_angle = pv.solarposition.hour_angle(
        times,
        lon,
        solar_position.equation_of_time,
    )

    solar_zenith = solar_position.zenith.values
    solar_azimuth = solar_position.azimuth.values

    dni = clearsky.dni.values
    ghi = clearsky.ghi.values
    dhi = clearsky.dhi.values

    airmass = pv.atmosphere.get_relative_airmass(
        solar_zenith
    )
    dni_extra = pv.irradiance.get_extra_radiation(doy)

    sz_matrix = solar_zenith[:, np.newaxis]
    sa_matrix = solar_azimuth[:, np.newaxis]
    az_matrix = azimuths[np.newaxis, :]

    poa_components = pv.irradiance.get_total_irradiance(
        surface_tilt=surface_tilt,
        surface_azimuth=az_matrix,
        solar_zenith=sz_matrix,
        solar_azimuth=sa_matrix,
        dni=dni[:, np.newaxis],
        ghi=ghi[:, np.newaxis],
        dhi=dhi[:, np.newaxis],
        airmass=airmass[:, np.newaxis],
        albedo=ALBEDO,
        dni_extra=dni_extra,
        model="perez-driesse",
    )

    gti_matrix = np.squeeze(
        poa_components["poa_global"]
    )

    idx_max_gti = np.argmax(gti_matrix, axis=0)

    omega_ast_del_dia = hour_angle.values[
        idx_max_gti
    ]

    omega_ast_anual[idx_dia, :] = (
        omega_ast_del_dia
    )

    if SAVE_DAILY_FIGURES:
        fig, ax = plt.subplots(figsize=(8, 6))

        ax.plot(
            omega_ast_del_dia,
            azimuths,
            color="darkblue",
            linewidth=2,
        )

        ax.set_title(
            f"{STATION} | gamma vs omega* | DOY {doy}",
            fontsize=12,
            fontweight="bold",
        )
        ax.set_xlabel(
            "Hour angle (omega* [deg])",
            fontsize=10,
        )
        ax.set_ylabel(
            "Surface azimuth (gamma [deg])",
            fontsize=10,
        )
        ax.grid(True, linestyle="--", alpha=0.6)

        nombre_grafico = (
            f"gamma_omega_ast_{doy:03d}_"
            f"{dia.strftime('%d-%m-%Y')}.png"
        )

        fig.savefig(
            fig_dir / nombre_grafico,
            dpi=150,
            bbox_inches="tight",
        )
        plt.close(fig)

    if doy == 1 or doy % 25 == 0 or doy == 365:
        print(f"[{STATION}] DOY {doy:03d}/365")


# ============================================================
# NETCDF
# ============================================================

ds = xr.Dataset(
    data_vars={
        "omega_star": (
            ("azimuth", "doy"),
            omega_ast_anual.T,
        )
    },
    coords={
        "azimuth": azimuths,
        "doy": np.arange(1, 366),
    },
)

ds.attrs["station"] = STATION
ds.attrs["surface_tilt"] = float(surface_tilt)
ds.attrs["albedo"] = float(ALBEDO)
ds.attrs["model"] = "Perez-Driesse"
ds.attrs["latitude"] = float(lat)
ds.attrs["longitude"] = float(lon)
ds.attrs["timezone"] = cfg["tz"]
ds.attrs["reference_year"] = int(REFERENCE_YEAR)
ds.attrs["azimuth_min"] = float(AZIMUTH_MIN)
ds.attrs["azimuth_max"] = float(AZIMUTH_MAX)
ds.attrs["azimuth_step"] = float(AZIMUTH_STEP)

ds.to_netcdf(lookup_path)

print(f"\nLUT NetCDF guardada en: {lookup_path}")


# ============================================================
# CSV AUXILIAR
# ============================================================

matriz_omegas = omega_ast_anual.T
nombres_columnas_dias = (
    dias_del_anio.strftime("%Y-%m-%d")
)

df_resultado = pd.DataFrame(
    matriz_omegas,
    index=azimuths,
    columns=nombres_columnas_dias,
)
df_resultado.index.name = "Azimuth_Superficie"

csv_path = out_dir / "lookup_table.csv"
df_resultado.to_csv(csv_path, index=True)

print(f"LUT CSV guardada en:    {csv_path}")


# ============================================================
# PLOT COMPARATIVO ESTACIONAL
# ============================================================

dias_clave = [
    f"{REFERENCE_YEAR}-03-21",
    f"{REFERENCE_YEAR}-06-21",
    f"{REFERENCE_YEAR}-09-21",
    f"{REFERENCE_YEAR}-12-21",
]

nombres_grafico = [
    "Equinoccio de Otoño",
    "Solsticio de Invierno",
    "Equinoccio de Primavera",
    "Solsticio de Verano",
]

colores = [
    "#e67e22",
    "#2980b9",
    "#27ae60",
    "#c0392b",
]

eje_y_azimut = df_resultado.index

fig, ax = plt.subplots(figsize=(10, 8))

for dia, etiqueta, color in zip(
    dias_clave,
    nombres_grafico,
    colores,
):
    ax.plot(
        df_resultado[dia],
        eje_y_azimut,
        label=f"{etiqueta} ({dia})",
        color=color,
        linewidth=2.5,
    )

ax.set_title(
    f"{STATION} | Función Azimut vs omega*",
    fontsize=14,
    fontweight="bold",
    pad=15,
)
ax.set_xlabel(
    "Hour angle of maximum GTI (omega* [deg])",
    fontsize=11,
)
ax.set_ylabel(
    "Surface azimuth (gamma [deg])",
    fontsize=11,
)

ax.axvline(0, color="black", linestyle=":", alpha=0.4)
ax.axhline(0, color="black", linestyle=":", alpha=0.4)

ax.grid(True, linestyle="--", alpha=0.5)
ax.legend(
    loc="best",
    fontsize=10,
    frameon=True,
    facecolor="white",
    edgecolor="none",
)

summary_figure = (
    fig_dir / "comparativa_funciones_anual.png"
)

fig.savefig(
    summary_figure,
    dpi=200,
    bbox_inches="tight",
)

plt.show()

print(f"Figura comparativa:     {summary_figure}")
