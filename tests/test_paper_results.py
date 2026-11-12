"""Presentation checks on the fixed validated rows; no estimator execution."""

import math
from pathlib import Path
import statistics
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "paper"))
from generate_figures import differences, estimated_vs_nominal, time_series
from generate_tables import load_results, summarize, validate_frame, write_tables
from paper_style import paper_context
from src.config import get_station_config
import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


class PaperResultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.provenance = load_results()
        cls.summaries = summarize(cls.data)

    def test_counts_dates_and_traceability(self):
        self.assertGreater(len(self.data["AZ"]), 0)
        self.assertEqual(len(self.data["TA"]), 29)
        self.assertEqual(
            len(self.data["AZ"]),
            len(self.provenance["AZ"]["original_rows"])
        )
        self.assertEqual(self.data["TA"]["date_raw"].iloc[0], "2016-10-02")
        self.assertEqual(self.data["TA"]["date_raw"].iloc[-1], "2017-05-07")
        for station, frame in self.data.items():
            self.assertEqual(set(frame["csv_row"]), set(range(2, len(frame) + 2)))
            self.assertEqual(len(self.provenance[station]["sha256"]), 64)
        schedule = [
            (pd.Timestamp(start), float(az))
            for start, az in get_station_config("AZ")["nominal_azimuth_schedule"]
        ]
        schedule.sort()
        
        for row in self.data["AZ"].itertuples(index=False):
            expected = [
                az for start, az in schedule
                if row.date >= start
            ]
            self.assertTrue(expected)
            self.assertAlmostEqual(row.azimuth_nominal, expected[-1])

    def test_independent_statistics_and_sign(self):
        for row in self.summaries[0].itertuples(index=False):
            values = self.data["AZ"].loc[
                self.data["AZ"]["azimuth_nominal"].eq(row.nominal_azimuth_deg), "azimuth"
            ].tolist()
            delta = [v - row.nominal_azimuth_deg for v in values]
            self.assertEqual(row.N, len(values))
            self.assertAlmostEqual(row.mean_azimuth_deg, statistics.mean(values), places=12)
            self.assertAlmostEqual(row.signed_bias_deg, statistics.mean(delta), places=12)
            self.assertAlmostEqual(row.MAE_deg, statistics.mean(map(abs, delta)), places=12)
            self.assertAlmostEqual(row.RMSE_deg, math.sqrt(statistics.mean(d*d for d in delta)), places=12)
            if len(values) == 1:
                self.assertTrue(math.isnan(row.std_azimuth_deg))
            else:
                self.assertAlmostEqual(row.std_azimuth_deg, statistics.stdev(values), places=12)
                self.assertAlmostEqual(row.std_azimuth_deg, statistics.stdev(delta), places=12)
                np.testing.assert_allclose(
                    self.data["AZ"]["azimuth_error_deg"],
                    -self.data["AZ"]["delta_gamma"],
                    rtol=0,
                    atol=1e-9,
                )
        ta = self.data["TA"]["azimuth"].tolist()
        row = self.summaries[1].iloc[0]
        for field, value in [("mean", statistics.mean(ta)), ("median", statistics.median(ta)),
                             ("std", statistics.stdev(ta)), ("min", min(ta)), ("max", max(ta))]:
            self.assertAlmostEqual(row[f"{field}_azimuth_deg"], value, places=12)

    def test_invalid_inputs_fail_instead_of_dropping_rows(self):
        raw = pd.DataFrame(self.provenance["AZ"]["original_rows"]).drop(columns="csv_row").astype(object)
        invalid = [
            raw.iloc[0:0],
            raw.drop(columns="azimuth"),
            raw.rename(columns={"date": "screening_date"}),
        ]
        for field, value in [("station", "TA"), ("azimuth", np.nan), ("azimuth", np.inf),
                             ("doy", 1), ("date", "2026/06/15"), ("azimuth_nominal", 100),
                             ("tilt", 45), ("azimuth_error_deg", -0.2), ("discarded_pct", 101)]:
            bad = raw.copy()
            bad.loc[0, field] = value
            invalid.append(bad)
        duplicate = raw.copy()
        duplicate.loc[1, "date"] = duplicate.loc[0, "date"]
        invalid.append(duplicate)
        for bad in invalid:
            with self.subTest(columns=list(bad.columns), rows=len(bad)):
                with self.assertRaises(ValueError):
                    validate_frame(bad, "AZ")

    def test_table_files_preserve_values_and_booktabs(self):
        with tempfile.TemporaryDirectory(prefix="azimuth-paper-test-") as directory:
            products = write_tables(Path(directory), self.summaries)
            for path, expected in zip(products[:2], self.summaries):
                actual = pd.read_csv(path)
                pd.testing.assert_frame_equal(actual, expected, check_exact=False, atol=1e-12, rtol=0)
            for path in products[2:]:
                text = path.read_text()
                for command in [r"\toprule", r"\midrule", r"\bottomrule"]:
                    self.assertIn(command, text)
            with self.assertRaises(FileExistsError):
                write_tables(Path(directory), self.summaries)

    def test_figure_points_and_sd_match_original_data_and_tables(self):
        with paper_context():
            f1 = time_series(self.data)
            for ax, station in zip(f1.axes, ["AZ", "TA"]):
                self.assertEqual(len(ax.lines), 0)  # No false time continuity.
                np.testing.assert_allclose(ax.collections[0].get_offsets()[:, 0], mdates.date2num(self.data[station]["date"]))
                np.testing.assert_allclose(ax.collections[0].get_offsets()[:, 1], self.data[station]["azimuth"])
            np.testing.assert_allclose(f1.axes[0].collections[1].get_offsets()[:, 1], self.data["AZ"]["azimuth_nominal"])
            self.assertEqual(len(f1.axes[1].collections), 1)
            f2 = estimated_vs_nominal(self.data["AZ"])
            plotted = np.concatenate([artist.get_offsets() for artist in f2.axes[0].collections])
            np.testing.assert_allclose(plotted, self.data["AZ"][["azimuth_nominal", "azimuth"]])
            self.assertEqual(f2.axes[0].get_xlim(), f2.axes[0].get_ylim())
            self.assertEqual(f2.axes[0].get_aspect(), 1.0)
            f3 = differences(self.data["AZ"], self.summaries[0])
            scatters = [a for a in f3.axes[0].collections if hasattr(a, "get_sizes")]
            np.testing.assert_allclose(np.concatenate([a.get_offsets()[:, 1] for a in scatters]), self.data["AZ"]["delta_gamma"])
            # Two real summaries; the third container is only the empty legend handle.
            groups = self.summaries[0].loc[self.summaries[0]["N"].ge(2)]
            errorbars = f3.axes[0].containers[:len(groups)]
            self.assertEqual(len(errorbars), len(groups))
            for bar, row in zip(errorbars, groups.itertuples(index=False)):
                self.assertAlmostEqual(bar.lines[0].get_ydata()[0], row.signed_bias_deg)
                segment = bar.lines[2][0].get_segments()[0]
                np.testing.assert_allclose(segment[:, 1], [row.signed_bias_deg-row.std_azimuth_deg,
                                                           row.signed_bias_deg+row.std_azimuth_deg])
            for fig in [f1, f2, f3]:
                plt.close(fig)

    def test_style_ignores_inherited_state_and_restores_it(self):
        with mpl.rc_context({"font.size": 31, "axes.grid": True, "text.usetex": True}):
            with paper_context():
                self.assertEqual(mpl.rcParams["font.size"], 9)
                self.assertFalse(mpl.rcParams["axes.grid"])
                self.assertFalse(mpl.rcParams["text.usetex"])
            self.assertEqual(mpl.rcParams["font.size"], 31)
            self.assertTrue(mpl.rcParams["text.usetex"])


if __name__ == "__main__":
    unittest.main()
