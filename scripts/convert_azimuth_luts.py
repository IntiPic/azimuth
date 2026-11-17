
"""Convert existing LUTs to the SWC2021 azimuth convention.

East negative, west positive.
Preserves the original LUTs and all omega_star values.

Run:
    python scripts/convert_azimuth_luts.py
"""

from pathlib import Path
from hashlib import sha256

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]

LUTS = {
    "AZ": (
        "lookup_omega_gamma_1s.nc",
        "lookup_omega_gamma_1s_swc2021.nc",
    ),
    "TA": (
        "lookup_omega_gamma.nc",
        "lookup_omega_gamma_swc2021.nc",
    ),
}


def checksum(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    for station, (old_name, new_name) in LUTS.items():
        folder = ROOT / "lookup" / station
        old_path = folder / old_name
        new_path = folder / new_name

        if not old_path.is_file():
            raise FileNotFoundError(old_path)

        if new_path.exists():
            raise FileExistsError(new_path)

        with xr.open_dataset(old_path) as original:
            old = original.load()

        old_values = old["omega_star"].transpose(
            "azimuth", "doy"
        ).to_numpy()

        # Change physical azimuth coordinates, not omega_star.
        converted = old.assign_coords(
            azimuth=-old["azimuth"].to_numpy()
        ).sortby("azimuth")

        new_values = converted["omega_star"].transpose(
            "azimuth", "doy"
        ).to_numpy()

        np.testing.assert_array_equal(
            new_values,
            old_values[::-1, :],
        )

        converted.attrs.update({
            "azimuth_convention": (
                "SWC2021: north=0; east negative; west positive"
            ),
            "converted_from": old_name,
            "source_sha256": checksum(old_path),
            "conversion": "gamma_new = -gamma_old",
        })

        converted.to_netcdf(new_path)

        print(f"\n{station}")
        print(f"New LUT: {new_path}")
        print(f"SHA-256: {checksum(new_path)}")

        # Auxiliary CSV for the publication LUT figure.
        if station == "AZ":
            dates = pd.date_range(
                "2026-01-01", periods=365, freq="D"
            ).strftime("%Y-%m-%d")

            csv_path = folder / "lookup_table_1s_swc2021.csv"

            if csv_path.exists():
                raise FileExistsError(csv_path)

            table = pd.DataFrame(
                new_values,
                index=converted["azimuth"].to_numpy(),
                columns=dates,
            )
            table.index.name = "Azimuth_Superficie"
            table.to_csv(csv_path)

            print(f"CSV: {csv_path}")

    print("\nConversion completed. Original LUTs preserved.")


if __name__ == "__main__":
    main()
