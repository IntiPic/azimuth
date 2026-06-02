#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May 15 15:51:03 2026

Determine GTI for a range of surface azimuths and build the 

@author: inti
"""
import numpy as np
import pandas as pd
import pvlib as pv
import pytz
import matplotlib.pyplot as plt
from pathlib import Path

#%%
script_dir = Path.cwd()
fig_dir = script_dir.parent / 'FIG'
out_dir = script_dir.parent / 'OUT'
fig_dir.mkdir(parents=True, exist_ok=True)
out_dir.mkdir(parents=True, exist_ok=True)
    
#%%

# 1. Configuración de ubicación y parámetros
lat = -34.9181706
lon = -56.1665725
tz_est = pytz.timezone("America/Montevideo")
site = pv.location.Location(lat, lon, tz=tz_est)

surface_tilt = 35
albedo = 0.25
azimuths = np.arange(-90, 91, 0.1)  # Vector de azimuts (Muestras: 1810)

# Definir el rango para todo el año 2026
dias_del_anio = pd.date_range(start='2026-01-01', end='2026-12-31', freq='D', tz=tz_est)

# Matriz para almacenar resultados: filas (días del año), columnas (azimuts)
omega_ast_anual = np.zeros((len(dias_del_anio), len(azimuths)))

# 2. Bucle anual (365 iteraciones en lugar de 365 x 1810)
for idx_dia, dia in enumerate(dias_del_anio):

    # Generar rango de tiempo de alta resolución para el día actual
    times = pd.date_range(start=dia, end=dia + pd.Timedelta(hours=23, minutes=59), freq='1min', tz=site.tz)
    doy = dia.dayofyear

    # Cálculos astronómicos del día
    solar_position = site.get_solarposition(times=times)
    clearsky = site.get_clearsky(times)
    hour_angle = pv.solarposition.hour_angle(times, lon, solar_position.equation_of_time)

    solar_zenith = solar_position.zenith.values
    solar_azimuth = solar_position.azimuth.values
    dni = clearsky.dni.values
    ghi = clearsky.ghi.values
    dhi = clearsky.dhi.values

    airmass = pv.atmosphere.get_relative_airmass(solar_zenith)
    dni_extra = pv.irradiance.get_extra_radiation(doy)

    # --- TRUCO DE VECTORIZACIÓN (Broadcasting) ---
    # Convertimos los vectores en matrices para evaluar todos los azimuts a la vez
    # Dimensiones deseadas: (Número de minutos del día, Número de azimuts)
    sz_matrix = solar_zenith[:, np.newaxis]
    sa_matrix = solar_azimuth[:, np.newaxis]
    az_matrix = azimuths[np.newaxis, :]

    # Evaluamos Perez-Driesse de forma matricial
    poa_components = pv.irradiance.get_total_irradiance(
        surface_tilt=surface_tilt,
        surface_azimuth=az_matrix, # Entrada matricial
        solar_zenith=sz_matrix,
        solar_azimuth=sa_matrix,
        dni=dni[:, np.newaxis],
        ghi=ghi[:, np.newaxis],
        dhi=dhi[:, np.newaxis],
        airmass=airmass[:, np.newaxis],
        albedo=albedo,
        dni_extra=dni_extra,
        model='perez-driesse'
    )

    # 1. Extraer la matriz del diccionario usando corchetes
    gti_matrix = poa_components['poa_global']

    # 2. Eliminar dimensiones de tamaño 1 sobrantes (ej: pasar de (1, 1440, 1810) a (1440, 1810))
    gti_matrix = np.squeeze(gti_matrix)

    # 3. Encontrar el índice temporal (eje de los minutos del día, axis=0) del máximo de GTI
    idx_max_gti = np.argmax(gti_matrix, axis=0)

    omega_ast_del_dia = hour_angle.values[idx_max_gti]
    omega_ast_anual[idx_dia, :] = omega_ast_del_dia

    # --- GENERACIÓN Y GUARDADO DEL GRÁFICO DIARIO ---
    # Creamos una nueva figura en segundo plano
    fig, ax = plt.subplots(figsize=(8, 6))

    # Graficamos Omega* en el eje X y el Azimut en el eje Y
    ax.plot(omega_ast_del_dia, azimuths, color='darkblue', linewidth=2)

    # Configuración de etiquetas y formato técnico
    ax.set_title(f'Function $\gamma$ vs $\omega^*$ - Day {doy}', fontsize=12, fontweight='bold')
    ax.set_xlabel('Hour angle ($\omega^*$ degrees)', fontsize=10)
    ax.set_ylabel('Surface azimuth ($\gamma^\circ$)', fontsize=10)
    ax.grid(True, linestyle='--', alpha=0.6)

    # Definir el nombre del archivo usando el formato dd-mm-yyyy o el número de día del año (doy)
    nombre_grafico = f'gamma_omega_ast_{doy:03d}_{dia.strftime("%d-%m-%Y")}.png'
    
    # Unes la ruta usando el operador '/' de pathlib
    ruta_figura = fig_dir / nombre_grafico

    # Guardar la imagen en Drive con buena resolución (dpi=150 es ideal para documentación)
    plt.savefig(ruta_figura, dpi=150, bbox_inches='tight')
    plt.close(fig)
    

#%% Creación del dataframe final de azimuths vs omega_ast para cada dia del año
# Conversión a DataFrame para análisis posterior
matriz_omegas = omega_ast_anual.T
nombres_columnas_dias = dias_del_anio.strftime('%Y-%m-%d')
df_resultado = pd.DataFrame(matriz_omegas, index=azimuths, columns=nombres_columnas_dias)
df_resultado.index.name = 'Azimuth_Superficie'


# Guadar salidas
df_resultado.to_csv(out_dir / 'matriz_omega_gamma_anual.csv', index=False)
#%% 
# --- CÓDIGO AL FINAL DE LA RUTINA: PLOT COMPARATIVO MULTI-DÍA ---

# 1. Definimos los 4 días clave que queremos comparar (Solsticios y Equinoccios de 2026)
dias_clave = ['2026-03-21', '2026-06-21', '2026-09-21', '2026-12-21']
nombres_grafico = ['Equinoccio de Otoño', 'Solsticio de Invierno', 'Equinoccio de Primavera', 'Solsticio de Verano']
colores = ['#e67e22', '#2980b9', '#27ae60', '#c0392b'] # Colores asociados a las estaciones

# 2. Extraemos el vector de Azimut que está en la primera columna
eje_y_azimut = df_resultado.index

# 3. Inicializamos la figura de Matplotlib
fig, ax = plt.subplots(figsize=(10, 8))

# 4. Graficamos la curva de cada uno de los 4 días seleccionados
for dia, etiqueta, color in zip(dias_clave, nombres_grafico, colores):
    if dia in df_resultado.columns:
        # X: Ángulo horario de ese día en particular, Y: Vector de Azimuts fijo
        ax.plot(df_resultado[dia], eje_y_azimut, label=f'{etiqueta} ({dia})', color=color, linewidth=2.5)
    else:
        print(f"Advertencia: La columna {dia} no se encuentra en el DataFrame.")

# 5. Formato estético y técnico del gráfico
ax.set_title('Comparativa Estacional: Función de Transferencia Azimut vs $\omega^*$', fontsize=14, fontweight='bold', pad=15)
ax.set_xlabel('Ángulo Horario de Máxima Irradiancia Global Inclinada ($\omega^*$ [rad])', fontsize=11)
ax.set_ylabel('Azimut de la Superficie del Captador ($^\circ$)', fontsize=11)

# Añadimos líneas de referencia en los ejes cero para evaluar asimetrías
ax.axvline(0, color='black', linestyle=':', alpha=0.4)
ax.axhline(0, color='black', linestyle=':', alpha=0.4)

# Configuración de la grilla y la leyenda
ax.grid(True, linestyle='--', alpha=0.5)
ax.legend(loc='best', fontsize=10, frameon=True, facecolor='white', edgecolor='none')

# # 6. Guardar la gráfica comparativa final en tu carpeta FIG del Drive
ruta_grafica_final = fig_dir/ 'comparativa_funciones_anual.png'
plt.savefig(ruta_grafica_final, dpi=200, bbox_inches='tight')

# Mostramos el gráfico en pantalla en Colab
plt.show()

