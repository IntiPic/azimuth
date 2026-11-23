#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov 23 11:49:51 2026

@author: inti
"""

"""Carpet plot de GHI de TA. Lee los CSV originales sin modificarlos."""

from pathlib import Path
import argparse

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
import pvlib


# Configuración para Spyder
REPO = Path(__file__).resolve().parents[2]
START = "2016-10-01"
END = "2017-09-30"
MODE = "both"                 # "original", "corrected", "both"
OUTPUT = "outputs/TA/carpet/ghi.png" # Ej.: REPO / "outputs/TA/carpet/ghi.png"
SHOW = True

LATITUDE = -31.74 #TA
LONGITUDE = -55.98
LOCAL_TZ = "America/Montevideo"

GHI_COLUMN = "GHI1_AV (W/m2)"
DARK_LIMIT = 5.0              # W/m²; solo afecta la visualización
COLOR_MAX = 1200.0            # Escala común a ambos paneles
MISSING_COLOR = "#a0a0a0"

TRANSITION = pd.Timestamp("2017-05-12")
AFTER_TRANSITION = pd.Timestamp("2017-05-13")


def load_measurements(repo):
    """Conservar identidad y valores crudos; ordenar al construir la matriz."""
    files = sorted(
        (Path(repo) / "data/TA").glob("*/DataT/TA_DT_*.csv")
    )
    if not files:
        raise FileNotFoundError("No se encontraron CSV de TA.")

    frames = []
    for path in files:
        raw = pd.read_csv(
            path,
            usecols=["Timestamp", GHI_COLUMN],
            dtype=str,
        )

        frame = pd.DataFrame({
            "file": str(path.relative_to(repo)),
            "row_id": np.arange(len(raw)),
            "timestamp_raw": raw["Timestamp"],
            "ghi_raw": raw[GHI_COLUMN],
        })
        frame["timestamp"] = pd.to_datetime(
            frame["timestamp_raw"],
            format="mixed",
            errors="coerce",
        )
        frame["ghi"] = pd.to_numeric(
            frame["ghi_raw"], errors="coerce"
        )
        frame.loc[~np.isfinite(frame["ghi"]), "ghi"] = np.nan
        frames.append(frame)

    data = pd.concat(frames, ignore_index=True)
    invalid = data["timestamp"].isna()
    print(f"Archivos: {len(files)}; filas: {len(data)}")
    print(f"Timestamps no interpretables: {invalid.sum()}")
    return data


def display_times(data, mode):
    """Devolver coordenadas de reloj sin zona, solo para dibujar."""
    raw = data["timestamp"]

    if mode == "original":
        return raw.dt.floor("min")

    # Antes del cambio: timestamps UTC convertidos a hora local.
    times = (
        raw.dt.tz_localize("UTC")
        .dt.tz_convert(LOCAL_TZ)
        .dt.tz_localize(None)
    )

    # Después: timestamps interpretados como UTC−3 fijo.
    after = raw >= AFTER_TRANSITION
    times.loc[after] = (
        raw.loc[after]
        .dt.tz_localize("Etc/GMT+3")  # Nombre IANA para UTC−3.
        .dt.tz_convert(LOCAL_TZ)
        .dt.tz_localize(None)
    )

    transition = (raw >= TRANSITION) & (raw < AFTER_TRANSITION)
    times.loc[transition] = pd.NaT
    print(f"Filas sin asignar durante transición: {transition.sum()}")

    return times.dt.floor("min")


def make_matrix(data, times, days):
    """Matriz [minuto del día, fecha]; sin interpolar faltantes."""
    stop = days[-1] + pd.Timedelta(days=1)
    selected = (
        times.notna()
        & (times >= days[0])
        & (times < stop)
    )
    series = pd.Series(
        data.loc[selected, "ghi"].to_numpy(),
        index=pd.DatetimeIndex(times.loc[selected]),
    )

    duplicates = int(series.index.duplicated().sum())
    print(f"Filas adicionales en minutos repetidos: {duplicates}")

    # Solo para la imagen: promedio de observaciones del mismo minuto.
    # No altera los CSV ni se usa para estimar azimut.
    minute_series = series.groupby(level=0).mean()

    grid = pd.date_range(
        days[0], stop, freq="min", inclusive="left"
    )
    return minute_series.reindex(grid).to_numpy().reshape(
        len(days), 1440
    ).T


def solar_hours(days, mode):
    """Amanecer y atardecer SPA, calculados para cada fecha local."""
    events = pvlib.solarposition.sun_rise_set_transit_spa(
        days.tz_localize(LOCAL_TZ),
        latitude=LATITUDE,
        longitude=LONGITUDE,
        how="numpy",
    )

    # El reloj crudo no tiene zona inequívoca: UTC es su referencia.
    zone = "UTC" if mode == "original" else LOCAL_TZ

    def hours(column):
        clock = events[column].dt.tz_convert(zone)
        return (
            clock.dt.hour
            + clock.dt.minute / 60
            + clock.dt.second / 3600
        ).to_numpy()

    return hours("sunrise"), hours("sunset")


def plot_ghi_carpet(
    repo=REPO,
    start=START,
    end=END,
    mode=MODE,
    output=OUTPUT,
    show=SHOW,
    vmax=COLOR_MAX,
):
    if mode not in {"original", "corrected", "both"}:
        raise ValueError("Modo desconocido.")
    if vmax <= DARK_LIMIT:
        raise ValueError("vmax debe superar DARK_LIMIT.")

    first = pd.Timestamp(start).normalize()
    last = pd.Timestamp(end).normalize()
    if first > last:
        raise ValueError("La fecha inicial supera la final.")

    output = Path(output).expanduser() if output else None
    if output is not None and output.exists():
        raise FileExistsError(f"No se sobrescribe: {output}")

    repo = Path(repo).expanduser().resolve()
    data = load_measurements(repo)
    days = pd.date_range(first, last, freq="D")
    modes = ["original", "corrected"] if mode == "both" else [mode]

    cmap = plt.get_cmap("inferno").copy()
    cmap.set_under("black")
    cmap.set_bad(MISSING_COLOR)

    fig, axes = plt.subplots(
        len(modes), 1,
        figsize=(15, 4.5 * len(modes)),
        sharex=True,
        squeeze=False,
        constrained_layout=True,
    )
    axes = axes[:, 0]

    left = mdates.date2num(first.to_pydatetime())
    right = mdates.date2num(
        (last + pd.Timedelta(days=1)).to_pydatetime()
    )
    centers = mdates.date2num(
        (days + pd.Timedelta(hours=12)).to_pydatetime()
    )

    titles = {
        "original": "Reloj original del CSV · curvas solares en UTC",
        "corrected": (
            "Hora local de Montevideo · hipótesis de corrección UTC/UTC−3"
        ),
    }

    for ax, selected_mode in zip(axes, modes):
        times = display_times(data, selected_mode)
        matrix = make_matrix(data, times, days)

        # Copia visual: valores bajos en negro; NaN permanece faltante.
        display = np.where(matrix <= DARK_LIMIT, -1.0, matrix)

        image = ax.imshow(
            np.ma.masked_invalid(display),
            origin="lower",
            aspect="auto",
            interpolation="nearest",
            extent=(left, right, 0, 24),
            cmap=cmap,
            vmin=0,
            vmax=vmax,
        )

        sunrise, sunset = solar_hours(days, selected_mode)
        ax.plot(
            centers, sunrise, color="cyan",
            linestyle="--",
            linewidth=0.9, label="Amanecer SPA",
        )
        ax.plot(
            centers, sunset, color="lime",
            linestyle="--",
            linewidth=0.9, label="Atardecer SPA",
        )

        ax.set(
            title=titles[selected_mode],
            ylabel="Hora del día",
            ylim=(0, 24),
            yticks=np.arange(0, 25, 3),
        )
        ax.axvline(
            pd.Timestamp("2017-05-12"),
            color="white",
            linestyle="--",
            linewidth=1.2,
            label="Posible cambio horario",
        )
        handles, labels = ax.get_legend_handles_labels()
        handles += [
            Patch(facecolor="black"),
            Patch(facecolor=MISSING_COLOR),
        ]
        labels += [
            f"GHI ≤ {DARK_LIMIT:g} W/m²",
            "Sin dato válido / sin asignación temporal",
        ]
        ax.legend(handles, labels, loc="upper right", fontsize=8)

    axes[-1].xaxis.set_major_locator(
        mdates.MonthLocator(interval=4)
    )
    axes[-1].xaxis.set_major_formatter(
        mdates.DateFormatter("%Y-%m")
    )
    axes[-1].set_xlabel("Fecha")

    fig.colorbar(
        image, ax=list(axes),
        label="GHI medida [W/m²]", extend="max",
    )
    fig.suptitle(f"TA · GHI · {first.date()} a {last.date()}")

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        # Modo exclusivo: también evita sobrescritura al guardar.
        with output.open("xb") as stream:
            fig.savefig(
                stream,
                format=output.suffix.lstrip(".") or "png",
                dpi=180,
            )
        print(f"Figura guardada en: {output}")

    if show:
        plt.show()
    return fig


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--start", default=START)
    parser.add_argument("--end", default=END)
    parser.add_argument(
        "--mode",
        choices=["original", "corrected", "both"],
        default=MODE,
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--vmax", type=float, default=COLOR_MAX)
    parser.add_argument("--no-show", action="store_true")
    args = parser.parse_args(argv)

    return plot_ghi_carpet(
        repo=args.repo,
        start=args.start,
        end=args.end,
        mode=args.mode,
        output=args.output,
        show=SHOW and not args.no_show,
        vmax=args.vmax,
    )


if __name__ == "__main__":
    main()