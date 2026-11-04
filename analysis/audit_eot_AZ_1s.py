#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Read-only audit of AZ 1-second LUT provenance and Spencer-vs-SPA EOT.

Run from the azimuth repository root:
    python -m analysis.audit_eot_AZ_1s

Does not change the estimator, LUT, screening or historical results.
Only writes publication metadata and an audit CSV under paper/.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib as pv
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import get_station_config
from src.clearsky import estimate_omega_star
from src.loader import load_gti_file


STATION = "AZ"

LUT_PATH = ROOT / "lookup" / "AZ" / "lookup_omega_gamma_1s.nc"
CSV_PATH = ROOT / "lookup" / "AZ" / "lookup_table_1s.csv"

METADATA_PATH = (
    ROOT / "paper" / "metadata" / "lut_AZ_1s.json"
)

OUTPUT_PATH = (
    ROOT / "paper" / "outputs" / "publication_v1"
    / "tables" / "EOT_AZ_1s_diagnostic.csv"
)

CASES = [
    ("2026-06-15", "AZ_DT_20260615T235900.csv", -0.106430),
    ("2026-06-16", "AZ_DT_20260616T235900.csv", -3.753329),
    ("2026-06-29", "AZ_DT_20260629T235900.csv", -3.363238),
    ("2026-07-01", "AZ_DT_20260701T235900.csv", -5.709831),
    ("2026-08-09", "AZ_DT_20260809T235900.csv", -9.757618),
    ("2026-08-30", "AZ_DT_20260830T235900.csv", -14.333946),
    ("2026-08-31", "AZ_DT_20260831T235900.csv", -15.657002),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def inverse_lut(
    ds: xr.Dataset,
    omega_star: float,
    doy: int,
) -> float:

    curve = ds["omega_star"].sel(doy=doy)

    ix = int(
        np.argmin(
            np.abs(curve.to_numpy() - omega_star)
        )
    )

    return float(ds["azimuth"].to_numpy()[ix])


def main() -> None:

    cfg = get_station_config(STATION)

    if not LUT_PATH.is_file():
        raise FileNotFoundError(
            f"Expected untouched 1 s LUT: {LUT_PATH}"
        )

    digest = sha256(LUT_PATH)

    with xr.open_dataset(LUT_PATH) as ds:

        if tuple(ds["omega_star"].dims) != ("azimuth", "doy"):
            raise ValueError(
                "Unexpected LUT dimension names/order"
            )

        az = ds["azimuth"].to_numpy()
        doy = ds["doy"].to_numpy()
        val = ds["omega_star"].to_numpy()

        if (
            val.shape != (1801, 365)
            or not np.array_equal(doy, np.arange(1, 366))
        ):
            raise ValueError(
                f"Unexpected LUT data shape {val.shape}"
            )

        if not np.allclose(
            np.diff(az), 0.1, rtol=0, atol=1e-8
        ):
            raise ValueError("Unexpected azimuth grid")

        if (
            not np.isfinite(val).all()
            or not (np.diff(val, axis=0) < 0).all()
        ):
            raise ValueError(
                "1 s LUT is not finite and strictly monotone"
            )

        if str(
            ds.attrs.get("station", "")
        ).upper() != STATION:
            raise ValueError(
                "Wrong station in LUT metadata"
            )

        if not np.isclose(
            float(ds.attrs.get("surface_tilt")),
            cfg["tilt"],
            atol=1e-6,
        ):
            raise ValueError(
                "Wrong surface tilt in LUT metadata"
            )

        for key in ("latitude", "longitude"):
            if not np.isclose(
                float(ds.attrs.get(key)),
                cfg[key],
                atol=0.001,
                rtol=0,
            ):
                raise ValueError(f"{key} mismatch")

        if int(
            ds.attrs.get("temporal_resolution_seconds", -1)
        ) != 1:
            print(
                "[WARN] temporal_resolution_seconds=1 "
                "missing from NetCDF metadata; "
                "verify generator."
            )

        # Compare NetCDF with CSV, if available.
        if CSV_PATH.is_file():
            table = pd.read_csv(
                CSV_PATH, index_col=0
            )

            np.testing.assert_allclose(
                table.index.to_numpy(dtype=float),
                az,
                atol=1e-8,
                rtol=0,
            )

            np.testing.assert_allclose(
                table.to_numpy(dtype=float),
                val,
                atol=1e-10,
                rtol=0,
            )

        metadata = {
            "station": STATION,
            "path": str(LUT_PATH.relative_to(ROOT)),
            "sha256": digest,
            "size_bytes": LUT_PATH.stat().st_size,
            "shape": list(val.shape),
            "azimuth_step_deg": 0.1,
            "temporal_resolution_s": (
                int(ds.attrs["temporal_resolution_seconds"])
                if "temporal_resolution_seconds" in ds.attrs
                else "not documented"
            ),
            "reference_year": int(
                ds.attrs.get("reference_year", 2026)
            ),
            "generator": "lookup_table_configurable.py",
            "attrs": {
                str(k): str(v)
                for k, v in ds.attrs.items()
            },
        }

        METADATA_PATH.parent.mkdir(
            parents=True, exist_ok=True
        )

        if METADATA_PATH.exists():
            prior = json.loads(
                METADATA_PATH.read_text(encoding="utf-8")
            )

            if prior.get("sha256") != digest:
                raise ValueError(
                    "Existing manifest has another LUT SHA-256; "
                    "review manually"
                )

        METADATA_PATH.write_text(
            json.dumps(
                metadata,
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

        print(f"LUT SHA-256: {digest}")
        print(
            f"Manifest: {METADATA_PATH.relative_to(ROOT)}"
        )

        rows = []

        for date_text, filename, reference_omega in CASES:

            file_path = (
                ROOT / "data" / "all" / filename
            )

            if not file_path.is_file():
                raise FileNotFoundError(file_path)

            df = load_gti_file(
                file_path, station=STATION
            )

            # Existing production fit: Spencer EOT.
            fit = estimate_omega_star(
                df,
                120,
                cfg["longitude"],
                discard=True,
                max_discard_passes=3,
            )

            omega_spencer = float(fit["omega_star"])

            if abs(
                omega_spencer - reference_omega
            ) > 0.0001:
                raise AssertionError(
                    f"{date_text}: baseline changed: "
                    f"{omega_spencer} vs {reference_omega}"
                )

            # Refit using EXACTLY the same retained samples.
            # The rejection algorithm is NOT repeated with SPA.

            times_kept = fit["times"]
            gti_kept = np.asarray(
                fit["gti"], dtype=float
            )

            sp = pv.solarposition.get_solarposition(
                times_kept,
                latitude=cfg["latitude"],
                longitude=cfg["longitude"],
                method="nrel_numpy",
            )

            eot_spa = sp[
                "equation_of_time"
            ].to_numpy(dtype=float)

            eot_spencer = np.asarray(
                pv.solarposition.equation_of_time_spencer71(
                    times_kept.dayofyear.to_numpy()
                ),
                dtype=float,
            )

            omega_spa_axis = np.asarray(
                pv.solarposition.hour_angle(
                    times_kept,
                    cfg["longitude"],
                    eot_spa,
                ),
                dtype=float,
            )

            coeff = np.polyfit(
                omega_spa_axis,
                gti_kept,
                2,
            )

            if coeff[0] >= 0:
                raise ValueError(
                    f"Non-concave parabola: {date_text}"
                )

            omega_spa = float(
                -coeff[1] / (2 * coeff[0])
            )

            lut_doy = (
                pd.Timestamp(date_text)
                .replace(year=2026)
                .dayofyear
            )

            gamma_spencer = inverse_lut(
                ds, omega_spencer, lut_doy
            )

            gamma_spa = inverse_lut(
                ds, omega_spa, lut_doy
            )

            rows.append({
                "date": date_text,
                "n_fit_samples": len(times_kept),
                "omega_spencer_deg": omega_spencer,
                "omega_spa_deg": omega_spa,
                "delta_omega_deg": (
                    omega_spa - omega_spencer
                ),
                "mean_delta_eot_min": float(
                    np.mean(eot_spa - eot_spencer)
                ),
                "gamma_spencer_deg": gamma_spencer,
                "gamma_spa_deg": gamma_spa,
                "delta_gamma_deg": (
                    gamma_spa - gamma_spencer
                ),
            })

    result = pd.DataFrame(rows)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print(
        "\n" + result.round(4).to_string(index=False)
    )

    print(
        f"\nEOT audit saved: "
        f"{OUTPUT_PATH.relative_to(ROOT)}"
    )

    print(
        "No production code, screening or LUT was modified."
    )


if __name__ == "__main__":
    main()
