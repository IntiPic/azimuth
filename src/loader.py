# src/loader.py

import pandas as pd


def load_gti_file(filepath,tz_est="America/Montevideo"):

    df = pd.read_csv(filepath)

    # Seleccionar columnas relevantes
    df = df[["Timestamp","GHI1_AV (W/m2)","GTI_AV (W/m2)"]]

    # Renombrar
    df = df.rename(columns={"Timestamp": "timestamp",
            "GHI1_AV (W/m2)": "ghi",
            "GTI_AV (W/m2)": "gti"})

    # Convertir timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.floor("min")

    # Asignar zona horaria
    df["timestamp"] = (df["timestamp"].dt.tz_localize(tz_est))

    # Pasar a índice
    df = df.set_index("timestamp")

    return df


