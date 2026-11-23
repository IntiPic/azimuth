#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov 23 12:09:32 2026

@author: inti
"""


from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pvlib

# --------------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------------

REPO = Path(__file__).resolve().parents[2]

START = "2015-09-05"
END = "2018-10-10"

LAT = -31.74
LON = -55.98
TZ = "America/Montevideo"
ALTITUDE = 0  # Ajustar si se dispone de la altitud de TA

GAMMA = 14.0  # SWC2021: positivo hacia el Oeste
AZ_PVLIB = (-GAMMA) % 360

BETAS = np.arange(20, 56, 5)
ALBEDO = 0.20

SAMPLE_STEP = 10  # Un dato cada 10 minutos

GHI_COL = "GHI1_AV (W/m2)"
GTI_COLS = ["GTI30_AV (W/m2)", "GTI45_AV (W/m2)"]

SWITCH = pd.Timestamp("2017-05-12")
AFTER = pd.Timestamp("2017-05-13")


# --------------------------------------------------
# CARGA Y CORRECCIÓN HORARIA
# --------------------------------------------------

def load_data():

    files = sorted(
        (REPO / "data/TA").glob("*/DataT/TA_DT_*.csv")
    )

    frames = []

    for file in files:

        columns = pd.read_csv(file, nrows=0).columns

        if GHI_COL not in columns:
            continue

        gti_cols = [c for c in GTI_COLS if c in columns]

        if len(gti_cols) != 1:
            continue

        gti_col = gti_cols[0]

        df = pd.read_csv(
            file, usecols=["Timestamp", GHI_COL, gti_col]
        ).iloc[::SAMPLE_STEP].copy()

        raw = pd.to_datetime(
            df["Timestamp"],
            format="mixed",
            errors="coerce",
        )

        # Excluir el día de transición.
        valid = raw.notna() & (
            (raw < SWITCH) | (raw >= AFTER)
        )

        df = df.loc[valid]
        raw = raw.loc[valid]

        # Hasta 11/05/2017: timestamps expresados en UTC.
        local = (
            raw.dt.tz_localize("UTC")
            .dt.tz_convert(TZ)
        )

        # Desde 13/05/2017: timestamps expresados en UTC-3.
        later = raw >= AFTER
        local.loc[later] = (
            raw.loc[later]
            .dt.tz_localize("Etc/GMT+3")
            .dt.tz_convert(TZ)
        )

        frames.append(pd.DataFrame({
            "time": pd.DatetimeIndex(local),
            "ghi": pd.to_numeric(
                df[GHI_COL], errors="coerce"
            ).to_numpy(),
            "gti": pd.to_numeric(
                df[gti_col], errors="coerce"
            ).to_numpy(),
            "channel": gti_col,
        }))

    if not frames:
        raise RuntimeError("No se encontraron datos compatibles.")

    data = pd.concat(frames, ignore_index=True)

    start = pd.Timestamp(START)
    end = pd.Timestamp(END) + pd.Timedelta(days=1)

    dates = data["time"].dt.tz_localize(None)
    data = data.loc[(dates >= start) & (dates < end)]

    duplicates = data.duplicated(["time", "channel"]).sum()
    print(f"Duplicados en el muestreo: {duplicates}")

    data = data.drop_duplicates(["time", "channel"])
    data = data.dropna(subset=["ghi", "gti"])

    return data.sort_values("time").reset_index(drop=True)


# --------------------------------------------------
# FILTRO DE CONDICIONES DESPEJADAS
# --------------------------------------------------

def select_clear_samples(data):

    times = pd.DatetimeIndex(data["time"])

    loc = pvlib.location.Location(
        latitude=LAT,
        longitude=LON,
        tz=TZ,
        altitude=ALTITUDE,
    )

    solar = loc.get_solarposition(times)

    clearsky = loc.get_clearsky(
        times,
        model="ineichen",
        solar_position=solar,
    )

    ghi = data["ghi"].to_numpy()
    gti = data["gti"].to_numpy()
    ghi_cs = clearsky["ghi"].to_numpy()

    ratio = np.divide(
        ghi, ghi_cs,
        out=np.full(len(ghi), np.nan),
        where=ghi_cs > 0,
    )

    # Filtro aproximado de cielo claro:
    mask = (
        (ghi_cs > 300)
        & (ratio >= 0.85)
        & (ratio <= 1.15)
        & (gti > 50)
        & (solar["apparent_zenith"].to_numpy() < 75)
        & np.isfinite(ghi)
        & np.isfinite(gti)
    )

    print(f"Muestras iniciales: {len(data)}")
    print(f"Muestras seleccionadas: {mask.sum()}")

    return (
        data.loc[mask].reset_index(drop=True),
        solar.iloc[np.flatnonzero(mask)].reset_index(drop=True),
    )


# --------------------------------------------------
# TRANSPOSICIÓN Y COMPARACIÓN
# --------------------------------------------------

def calculate_results(data, solar):

    times = pd.DatetimeIndex(data["time"])
    ghi = data["ghi"].to_numpy()
    observed = data["gti"].to_numpy()

    # Estimación de DNI y DHI a partir de GHI.
    erbs = pvlib.irradiance.erbs(
        ghi,
        solar["zenith"].to_numpy(),
        times.dayofyear,
    )

    dni = np.asarray(erbs["dni"])
    dhi = np.asarray(erbs["dhi"])

    dni_extra = pvlib.irradiance.get_extra_radiation(times)

    airmass = pvlib.atmosphere.get_relative_airmass(
        solar["apparent_zenith"].to_numpy()
    )

    records = []

    for beta in BETAS:

        poa = pvlib.irradiance.get_total_irradiance(
            surface_tilt=float(beta),
            surface_azimuth=AZ_PVLIB,
            solar_zenith=solar["apparent_zenith"].to_numpy(),
            solar_azimuth=solar["azimuth"].to_numpy(),
            dni=dni,
            ghi=ghi,
            dhi=dhi,
            dni_extra=dni_extra,
            airmass=airmass,
            albedo=ALBEDO,
            model="perez-driesse",
        )

        predicted = np.asarray(poa["poa_global"])

        # Comparar por separado los dos canales.
        for channel in GTI_COLS:

            group = (
                (data["channel"].to_numpy() == channel)
                & np.isfinite(predicted)
                & (predicted > 0)
            )

            obs = observed[group]
            pred = predicted[group]

            if len(obs) < 20:
                continue

            # Error absoluto sin calibrar amplitud.
            rmsd = np.sqrt(np.mean((obs - pred) ** 2))

            # Factor multiplicativo óptimo por canal.
            # Permite evaluar la forma temporal de GTI,
            # reduciendo el efecto de un sesgo de calibración.
            gain = np.dot(obs, pred) / np.dot(pred, pred)

            rmsd_scaled = np.sqrt(
                np.mean((obs - gain * pred) ** 2)
            )

            records.append({
                "channel": channel,
                "beta": beta,
                "N": len(obs),
                "gain": gain,
                "nRMSD_raw": 100 * rmsd / np.mean(obs),
                "nRMSD_scaled": (
                    100 * rmsd_scaled / np.mean(obs)
                ),
            })

    return pd.DataFrame(records)


# --------------------------------------------------
# RESULTADOS Y GRÁFICO
# --------------------------------------------------

def show_results(results):

    fig, ax = plt.subplots(figsize=(9, 5))

    for channel in GTI_COLS:

        subset = results[results["channel"] == channel]

        if subset.empty:
            continue

        best = subset.loc[
            subset["nRMSD_scaled"].idxmin()
        ]

        print(f"\n{channel}")
        print(
            subset[
                ["beta", "N", "gain",
                 "nRMSD_raw", "nRMSD_scaled"]
            ].round(3).to_string(index=False)
        )
        print(f"Mejor beta explorado: {best['beta']:.1f}°")

        ax.plot(
            subset["beta"],
            subset["nRMSD_scaled"],
            "o-",
            label=channel,
        )

    ax.axvline(30, color="gray", linestyle=":", alpha=0.7)
    ax.axvline(45, color="gray", linestyle="--", alpha=0.7)

    ax.set(
        xlabel="Inclinación supuesta, beta [°]",
        ylabel="nRMSD [%] (con factor de escala)",
        title="TA: contraste de inclinación con GTI medida",
    )
    ax.grid(alpha=0.3)
    ax.legend()

    plt.tight_layout()
    output = REPO / "outputs/TA/tilt_check.png"
    output.parent.mkdir(parents=True, exist_ok=True)

    fig.savefig(output, dpi=200, bbox_inches="tight")
    print(f"Gráfico guardado en: {output}")
    plt.show()


if __name__ == "__main__":

    data = load_data()
    data, solar = select_clear_samples(data)
    results = calculate_results(data, solar)
    show_results(results)
