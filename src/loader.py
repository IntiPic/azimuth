# src/loader.py

import pandas as pd

from src.config import get_station_config


def load_gti_file(filepath, station="AZ", tz_est=None, *, gti_col=None,
                  source_tz=None):
    """Load one file; explicit channel/clock overrides support audited periods.

    Defaults preserve the historical station configuration. Overrides do not
    infer a clock or inclination from irradiance or silently rename channels.
    """
    cfg = get_station_config(station)
    gti_col = gti_col or cfg["gti_col"]
    source_tz = source_tz or cfg["source_tz"]
    #tz = tz_est or cfg["tz"]

    df = pd.read_csv(filepath)

    required = [
        "Timestamp",
        cfg["ghi_col"],
        gti_col,
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(
            f"{filepath}: faltan columnas requeridas para {station}: {missing}"
        )

    df = df[required].rename(
        columns={
            "Timestamp": "timestamp",
            cfg["ghi_col"]: "ghi",
            gti_col: "gti",
        }
    )

    df["ghi"] = pd.to_numeric(df["ghi"], errors="coerce")
    df["gti"] = pd.to_numeric(df["gti"], errors="coerce")

    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.floor("min")
    df["timestamp"] = (
        df["timestamp"]
        .dt.tz_localize(source_tz)
        .dt.tz_convert(cfg["tz"])
    )

    df = df.set_index("timestamp").sort_index()

    return df
