#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jun 14 21:04:40 2026

@author: inti
"""
# main.py
from src.data_loader import cargar_y_limpiar_datos

# Configuración global del experimento (Metadatos del sitio)
RUTAS = {
    "datos": "./DATOS"
}

METADATOS = {
    "lat": -34.9011,
    "lon": -56.1645,
    "tz": "America/Montevideo",
    "tilt": 35
}

def pipeline_procesamiento():
    print("=== Iniciando Pipeline de Estimación Azimutal ===")
    
    # 1. Llamada a la función que acabamos de aislar
    df_completo = cargar_y_limpiar_datos(RUTAS["datos"], METADATOS["tz"])
    
    # --- Verificaciones breves de control de calidad ---
    print("\n=== Verificación de integridad de los datos ===")
    print(f"Estructura del DataFrame resultante (Filas, Columnas): {df_completo.shape}")
    print("\nTipos de datos asignados por columna (Deben ser float64):")
    print(df_completo.dtypes)
    
    print("\nMuestra de los primeros 5 registros cargados:")
    print(df_completo.head())
    
    print("\nCantidad de valores nulos (NaN) detectados tras la limpieza de 'OverRange':")
    print(df_completo.isna().sum())

if __name__ == "__main__":
    pipeline_procesamiento()# main.py