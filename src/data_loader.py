#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jun 14 21:03:48 2026

@author: inti
"""
# src/data_loader.py
import pandas as pd
from pathlib import Path

def cargar_y_limpiar_datos(ruta_datos: str, tz_est: str) -> pd.DataFrame:
    """
    Recorre la carpeta de datos, carga todos los archivos CSV, realiza un control
    de calidad inicial (coerción de strings espurios a NaN) y unifica el índice temporal.
    
    Parameters:
        ruta_datos (str): Trayectoria a la carpeta 'DATOS'.
        tz_est (str): Identificador de zona horaria (ej. 'America/Montevideo').
        
    Returns:
        pd.DataFrame: Dataframe unificado, indexado cronológicamente y con zona horaria local.
    """
    data_dir = Path(ruta_datos)
    archivos_csv = sorted(data_dir.glob('*.csv'))
    
    if not archivos_csv:
        raise FileNotFoundError(f"No se encontraron archivos CSV en la ruta especificada: {data_dir.resolve()}")
        
    columnas_requeridas = ['Timestamp', 'GHI1_AV (W/m2)', 'GTI_AV (W/m2)']
    dataframes_validos = []
    
    for archivo in archivos_csv:
        try:
            df = pd.read_csv(archivo)
            
            # Validación estricta de estructura
            if not all(col in df.columns for col in columnas_requeridas):
                print(f"[WARNING] Archivo omitido por falta de columnas estructurales: {archivo.name}")
                continue
                
            # Extraer y renombrar columnas
            df_temp = df[columnas_requeridas].copy()
            df_temp = df_temp.rename(columns={'GHI1_AV (W/m2)': 'GHI', 'GTI_AV (W/m2)': 'GTI'})
            
            # --- SANITIZACIÓN: Control de calidad inicial (Evita errores de texto/OverRange) ---
            df_temp['GHI'] = pd.to_numeric(df_temp['GHI'], errors='coerce')
            df_temp['GTI'] = pd.to_numeric(df_temp['GTI'], errors='coerce')
            
            # Manejo estricto de marcas de tiempo
            df_temp['Timestamp'] = pd.to_datetime(df_temp['Timestamp'], errors='coerce')
            df_temp = df_temp.dropna(subset=['Timestamp'])
            
            # Localización / Conversión de zona horaria local
            if df_temp['Timestamp'].dt.tz is None:
                df_temp['Timestamp'] = df_temp['Timestamp'].dt.tz_localize(tz_est)
            else:
                df_temp['Timestamp'] = df_temp['Timestamp'].dt.tz_convert(tz_est)
                
            dataframes_validos.append(df_temp)
            print(f"[INFO] Archivo cargado con éxito: {archivo.name} ({len(df_temp)} registros)")
            
        except Exception as e:
            print(f"[ERROR] No se pudo procesar el archivo {archivo.name}. Motivo: {e}")
            
    if not dataframes_validos:
        raise ValueError("Ningún archivo CSV pudo ser procesado o parseado correctamente.")
        
    # Concatenar todos los archivos en un único set de datos continuo
    df_unificado = pd.concat(dataframes_validos, axis=0)
    
    # Reindexar y ordenar cronológicamente para evitar problemas si los archivos vinieran desordenados
    df_unificado = df_unificado.set_index('Timestamp').sort_index()
    
    return df_unificado