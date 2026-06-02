#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 12 11:47:17 2026

@author: inti
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pvlib as pv
from pathlib import Path
from fun import modelado as md

#%%

lat, lon = -34.9011, -56.1645
tz_est = 'America/Montevideo'
surface_tilt = 35
surface_azimuth = 0

#%%
# Definir la ruta de forma semántica
ruta_base = Path.cwd()
ruta_datos = ruta_base.parent / 'DATOS'
nombre_archivo = "AZ_DT_20260522T235900.csv"
archivo_csv = ruta_datos / nombre_archivo

# Verificar si el archivo existe antes de abrirlo
if archivo_csv.exists():
    df = pd.read_csv(archivo_csv)
    print(f"Archivo cargado exitosamente: {archivo_csv.name}")
else:
    print(f"Error: No se encontró el archivo en {archivo_csv}")

#%%
# assume your original dataframe is `df`
df2 = df[['Timestamp', 'GHI1_AV (W/m2)', 'GTI_AV (W/m2)']].copy()
df2 = df2.rename(columns={'GHI1_AV (W/m2)': 'GHI', 'GTI_AV (W/m2)': 'GTI'})
df2['Timestamp'] = pd.to_datetime(df2['Timestamp'], errors='coerce')
# if timestamps are naive (no tz), localize to Montevideo; if they have tz, convert to Montevideo
if df2['Timestamp'].dt.tz is None:
    df2['Timestamp'] = df2['Timestamp'].dt.tz_localize(tz_est)
else:
    df2['Timestamp'] = df2['Timestamp'].dt.tz_convert(tz_est)
df2 = df2.set_index('Timestamp').sort_index()

#%%
times = df2.index
solpos = pv.solarposition.get_solarposition(df2.index, lat, lon)
hour_angle = pv.solarposition.hour_angle(times, lon, solpos.equation_of_time)

#%%

plt.figure()
plt.plot(hour_angle, df2.GHI, label='GHI')
plt.plot(hour_angle, df2.GTI, label='GTI')
plt.xlabel('Hour Angle'); plt.ylabel('Irradiance (W/m^2')
plt.grid()


#%% 
desfasaje = 19 # En minutos
df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.round('s').dt.tz_localize(tz_est)

df.set_index('Timestamp', inplace=True)
df.index = df.index + pd.Timedelta(minutes=desfasaje)
#%%
solpos = pv.solarposition.get_solarposition(df.index, lat, lon)

airmass = 1/np.cos(np.deg2rad(solpos.apparent_zenith))
TL = pv.clearsky.lookup_linke_turbidity(df.index, lat, lon)
csk = pv.clearsky.ineichen(solpos.apparent_zenith, airmass, TL,
                               altitude=0, dni_extra=1364.0)

df['GHI_csk'] = csk.ghi

#%%

[ghi_esra, dhi_esra, dni_esra] = md.generaComponentesESRA(solpos.elevation,1364,0,TL=2.0)

#%%

GTI_perez= pv.irradiance.get_total_irradiance(surface_tilt, surface_azimuth, solpos.apparent_zenith, 
                                              solpos.azimuth, csk.dni, csk.ghi, csk.dhi
                                              , albedo=0.25, dni_extra = 1364.0, surface_type=None, model='perez-driesse', model_perez='allsitescomposite1990')

GTI_perez_esra= pv.irradiance.get_total_irradiance(surface_tilt, surface_azimuth, solpos.apparent_zenith, 
                                              solpos.azimuth, dni_esra, ghi_esra, dhi_esra
                                              , albedo=0.25, dni_extra = 1364.0, surface_type=None, model='perez-driesse', model_perez='allsitescomposite1990')


df['GTI_csk_ineichen'] = GTI_perez.poa_global
df['GTI_csk_esra'] = GTI_perez_esra.poa_global
df.plot()

#%%
# # 1. Crear una máscara para altura solar positiva
# mask = solpos.elevation > 0

# # 2. Aplicar la máscara a los datos
# # Usamos .loc[mask] para asegurar que los ejes X (tiempo) e Y coincidan
# t_pos = df.index[mask]
# ghi_pos = df.loc[mask, 'GHI']
# ghi_csk_pos = df.loc[mask, 'GHI_csk']
# elev_pos = solpos.loc[mask, 'elevation']

# fig, ax1 = plt.subplots(figsize=(10, 6))

# # Eje Izquierdo: Irradiancia
# ax1.plot(df.index, df['GHI'], color='tab:red', label='GHI Medido', alpha=0.8)
# ax1.plot(df.index, df['GTI'], color='tab:green', label='GTI Medido', alpha=0.8)
# ax1.plot(t_pos, ghi_csk_pos, color='tab:blue', label='GHI Cielo Claro (csk)', linewidth=2)
# ax1.set_xlabel('Tiempo (Hora Local)')
# ax1.set_ylabel('Irradiancia (W/m²)')
# ax1.grid(True, alpha=0.3)
# ax1.legend(loc='upper left')

# # Eje Derecho: Altura Solar (solo positiva)
# ax2 = ax1.twinx() 
# ax2.plot(t_pos, elev_pos, '--', color='black', label='Altura Solar', alpha=0.5)
# ax2.set_ylabel('Altura Solar (grados)', color='black')
# ax2.set_ylim(0, 90) # Fija el mínimo en 0 para detectar el amanecer
# ax2.legend(loc='upper right')

# plt.title('Análisis de Desfasaje Solar al Amanecer')
# plt.show()