"""SWC2021 publication regression against preserved historical results/LUT.

Measured rows are compared with measured rows. Invalid LUT controls are copies
used only for validation tests; no estimator or screening is executed.
"""
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "paper"))
from convert_ta_results import TA_SOURCE, TA_DERIVED, converted_bytes
from generate_tables import load_results, summarize, validate_frame, prepare_run
from generate_lut_figure import DEFAULT_NETCDF, KEY_DAYS, load_lut, plot_lut, validate_lut
from paper_style import ORIENTATIONS, paper_context
import matplotlib.pyplot as plt


class SWC2021RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.provenance = load_results()
        fixture = ROOT / "tests/fixtures/AZ_legacy_14.csv"
        cls.legacy = pd.read_csv(fixture)
        metadata = json.loads(fixture.with_suffix(".json").read_text())
        assert hashlib.sha256(fixture.read_bytes()).hexdigest() == metadata["source_csv_sha256"]

    def test_az_conversion_preserves_omega_screening_and_case_identity(self):
        old = validate_frame(self.legacy, "AZ")
        new = self.data["AZ"]
        self.assertEqual(len(new), 14)
        self.assertEqual(new.azimuth_nominal.value_counts().to_dict(),
                         {0: 1, -10: 3, -20: 1, -30: 5, -40: 3, -50: 1})
        flipped = ["azimuth", "azimuth_nominal", "azimuth_error_deg", "delta_gamma"]
        np.testing.assert_array_equal(new[flipped], -old[flipped])
        pd.testing.assert_frame_equal(new.drop(columns=flipped), old.drop(columns=flipped),
                                      check_exact=True)
        np.testing.assert_array_equal(new.omega_star, old.omega_star)

    def test_az_mae_rmse_invariant_and_bias_reversed(self):
        old = validate_frame(self.legacy, "AZ")
        before = summarize({"AZ": old, "TA": self.data["TA"]})[0].set_index("nominal_azimuth_deg")
        after = summarize(self.data)[0].set_index("nominal_azimuth_deg")
        for nominal, row in after.iterrows():
            legacy = before.loc[-nominal]
            for field in ["N", "MAE_deg", "RMSE_deg", "std_azimuth_deg"]:
                np.testing.assert_allclose(row[field], legacy[field], rtol=0, atol=1e-12, equal_nan=True)
            self.assertAlmostEqual(row.signed_bias_deg, -legacy.signed_bias_deg, places=12)
        # Also test aggregate accuracy and signed bias over all 14 retained days.
        delta, previous = self.data["AZ"].delta_gamma, old.delta_gamma
        self.assertAlmostEqual(delta.abs().mean(), previous.abs().mean(), places=12)
        self.assertAlmostEqual(np.sqrt((delta**2).mean()), np.sqrt((previous**2).mean()), places=12)
        self.assertAlmostEqual(delta.mean(), -previous.mean(), places=12)

    def test_ta_derivative_preserves_all_other_fields_verbatim(self):
        source = (ROOT / TA_SOURCE).read_bytes()
        target = (ROOT / TA_DERIVED).read_bytes()
        self.assertEqual(target, converted_bytes(source))
        old = list(csv.DictReader(io.StringIO(source.decode())))
        new = list(csv.DictReader(io.StringIO(target.decode())))
        self.assertEqual(len(old), 29)
        self.assertEqual(len(new), 29)
        for before, after in zip(old, new):
            self.assertEqual(float(after.pop("azimuth")), -float(before.pop("azimuth")))
            self.assertEqual(after, before)  # Includes raw omega_star and all metadata.
        self.assertEqual(self.provenance["TA"]["derivation"]["source_sha256"],
                         hashlib.sha256(source).hexdigest())

    def test_distinct_style_for_all_swc2021_orientations(self):
        self.assertEqual(set(ORIENTATIONS), {0, -10, -20, -30, -40, -50, -60})
        self.assertEqual(len({c for c, _ in ORIENTATIONS.values()}), 7)
        self.assertEqual(len({m for _, m in ORIENTATIONS.values()}), 7)

    def test_lut_native_values_increasing_and_omega_unchanged(self):
        lut, provenance = load_lut()
        self.assertEqual(provenance["path"], str(DEFAULT_NETCDF.relative_to(ROOT)))
        self.assertEqual(provenance["sha256"], hashlib.sha256(DEFAULT_NETCDF.read_bytes()).hexdigest())
        self.assertTrue((np.diff(lut.to_numpy(), axis=0) > 0).all())
        with xr.open_dataset(DEFAULT_NETCDF, engine="netcdf4") as new:
            np.testing.assert_array_equal(lut.to_numpy(), new.omega_star.transpose("azimuth", "doy"))
            np.testing.assert_array_equal(lut.index, new.azimuth)
        old_path = DEFAULT_NETCDF.with_name(provenance["attrs"]["converted_from"])
        self.assertEqual(hashlib.sha256(old_path.read_bytes()).hexdigest(), provenance["attrs"]["source_sha256"])
        with xr.open_dataset(old_path, engine="netcdf4") as old:
            np.testing.assert_array_equal(lut.to_numpy(), old.omega_star.transpose("azimuth", "doy").values[::-1])
            np.testing.assert_array_equal(lut.index, -old.azimuth.values[::-1])
        with paper_context():
            fig = plot_lut(lut)
            for line, (day, _) in zip(fig.axes[0].lines, KEY_DAYS):
                np.testing.assert_array_equal(line.get_xdata(), lut[day])
                np.testing.assert_array_equal(line.get_ydata(), lut.index)
                self.assertTrue((np.diff(line.get_xdata()) > 0).all())
            plt.close(fig)

    def test_lut_rejects_decreasing_flat_or_nonfinite_controls(self):
        lut, _ = load_lut()
        bad = lut.copy()
        bad.iloc[1, 0] = bad.iloc[0, 0]
        nonfinite = lut.copy()
        nonfinite.iloc[0, 0] = np.nan
        for control in [-lut, bad, nonfinite]:
            with self.assertRaises(ValueError):
                validate_lut(control)

    def test_existing_publication_run_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("generate_tables.OUTPUT", Path(directory)):
                run, _, _ = prepare_run("new_swc2021", with_figures=True)
                sentinel = run / "untouched.txt"
                sentinel.write_text("historical output")
                with self.assertRaises(FileExistsError):
                    prepare_run("new_swc2021", with_figures=True)
                self.assertEqual(sentinel.read_text(), "historical output")


if __name__ == "__main__":
    unittest.main()
