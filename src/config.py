# src/config.py

STATIONS = {
    "AZ": {
        "latitude": -34.918034,
        "longitude": -56.166802,
        "tilt": 35.0,
        "source_tz": "America/Montevideo",
        "tz": "America/Montevideo",
        "ghi_col": "GHI1_AV (W/m2)",
        "gti_col": "GTI_AV (W/m2)",
        "data_glob": "data/all/*.csv",
        "valid_from": "2026-05-21",
        "lookup_table": "lookup/AZ/lookup_omega_gamma_1s.nc",
        "eot_method": "spa",
        "lookup_sha256": "3b2c2f84d4cc342f190a988a8328d153f954f5a3835aef3260f0dc319c489fcf",
        "lookup_reference_year": 2026,
        "screening_dir": "outputs/AZ/screening",
        "results_dir": "outputs/AZ/results/spa_1s",
        "daily_plots_dir": "outputs/AZ/daily_plots/spa_1s",
        "fit_plots_dir": "outputs/AZ/gti_fit_plots/spa_1s",
        "nominal_azimuth_schedule": [
            ("2026-05-21", 0.0),
            ("2026-06-16", 10.0),
            ("2026-07-06", 20.0),
            ("2026-08-24", 30.0),
            ("2026-09-22", 40.0),
        ],
    },
    "TA": {
        "latitude": -31.74,
        "longitude": -55.98,
        "tilt": 45.0,
        "source_tz": "UTC",
        "tz": "America/Montevideo",
        "ghi_col": "GHI1_AV (W/m2)",
        "gti_col": "GTI45_AV (W/m2)",
        "data_glob": "data/TA/*/DataT/TA_DT_*.csv",
        "valid_from": "2016-09-28",
        "lookup_table": "lookup/TA/lookup_omega_gamma.nc",
        "lookup_sha256": "ec5bb65579cfe03644d6bddc4209d008243dbb48c3b0c631e3a0e26c859f03e8",
        "lookup_reference_year": 2026,
        "screening_dir": "outputs/TA/screening",
        "results_dir": "outputs/TA/results",
        "daily_plots_dir": "outputs/TA/daily_plots",
        "fit_plots_dir": "outputs/TA/gti_fit_plots",
        "nominal_azimuth_schedule": None,
    },
}


def get_station_config(station):
    try:
        return STATIONS[station]
    except KeyError as exc:
        valid = ", ".join(sorted(STATIONS))
        raise ValueError(
            f"Estación desconocida: {station!r}. Opciones: {valid}"
        ) from exc
