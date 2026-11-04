
"""Inversión de LUT con verificación de identidad de la tabla histórica."""
from hashlib import sha256
from pathlib import Path
import numpy as np
import xarray as xr


class AzimuthEstimator:
    def __init__(self, latitude, longitude, tilt, lookup_table, *,
                 station=None, expected_sha256=None):
        self.latitude = latitude
        self.longitude = longitude
        self.tilt = tilt
        self.station = station
        self.lookup_table = Path(lookup_table).expanduser().resolve()

        if not self.lookup_table.is_file():
            raise FileNotFoundError(f"LUT inexistente: {self.lookup_table}")

        hasher = sha256()
        with self.lookup_table.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                hasher.update(chunk)

        self.lookup_sha256 = hasher.hexdigest()

        if expected_sha256 is not None and self.lookup_sha256 != expected_sha256:
            raise ValueError(
                f"LUT distinta de la auditada para {station or 'estación'}: "
                f"{self.lookup_table}\n"
                f"SHA-256 esperado: {expected_sha256}\n"
                f"SHA-256 obtenido: {self.lookup_sha256}"
            )

        ds = xr.load_dataset(self.lookup_table)
        try:
            if "omega_star" not in ds:
                raise ValueError("La LUT no contiene 'omega_star'.")

            if not {"azimuth", "doy"}.issubset(ds["omega_star"].dims):
                raise ValueError(
                    "'omega_star' debe tener dimensiones 'azimuth' y 'doy'."
                )

            attr_station = ds.attrs.get("station")
            if station is not None and attr_station is not None:
                if str(attr_station).upper() != str(station).upper():
                    raise ValueError(
                        f"LUT de {attr_station}, pero se solicitó {station}."
                    )

            attr_tilt = ds.attrs.get("tilt", ds.attrs.get("surface_tilt"))
            if attr_tilt is not None and not np.isclose(
                float(attr_tilt), float(tilt), atol=0.01, rtol=0
            ):
                raise ValueError(
                    f"LUT con tilt={attr_tilt}°, pero la estación usa {tilt}°."
                )

            for key, target in (
                ("latitude", latitude),
                ("longitude", longitude),
            ):
                if key in ds.attrs and not np.isclose(
                    float(ds.attrs[key]), float(target), atol=0.01, rtol=0
                ):
                    raise ValueError(
                        f"LUT con {key}={ds.attrs[key]}, "
                        f"pero la estación usa {target}."
                    )

        except Exception:
            ds.close()
            raise

        self.ds = ds

    def estimate(self, omega_star, doy):
        if not np.isfinite(omega_star):
            raise ValueError(f"omega_star no finito: {omega_star}")

        if doy not in self.ds["doy"].values:
            raise ValueError(
                f"DOY {doy} no disponible en {self.lookup_table}"
            )

        curve = self.ds["omega_star"].sel(doy=doy)
        values = np.asarray(curve.data)

        if not np.isfinite(values).all():
            raise ValueError(
                f"LUT contiene valores no finitos para DOY {doy}"
            )

        # Se conserva la regla histórica: primer índice del mínimo.
        idx = np.argmin(np.abs(values - omega_star))

        return curve.azimuth[idx].item()
