"""Numerical controls for the independent audit. No production writes."""
import unittest
import numpy as np
from run_diagnostics import fit_audit


class AuditTests(unittest.TestCase):
    def test_asymmetric_sampling_does_not_bias_exact_quadratic(self):
        x = np.linspace(-35, -5, 120)
        y = 1000 - .2 * (x + 10) ** 2
        ids = np.arange(len(x))
        ids = ids[(x < -20) | (x > -16)]
        result = fit_audit(x, y, ids, mode="none")
        self.assertAlmostEqual(result["omega"], -10, places=9)

    def test_affine_hour_angle_translation_preserves_selection(self):
        x = np.linspace(-35, -5, 120)
        y = 1000 - .2 * (x + 10) ** 2 + np.random.default_rng(1729).normal(0, .4, len(x))
        y[30:35] += 25
        a = fit_audit(x, y, np.arange(len(x)))
        b = fit_audit(x + .08, y, np.arange(len(x)))
        np.testing.assert_array_equal(a["keep"], b["keep"])
        self.assertAlmostEqual(b["omega"] - a["omega"], .08, places=9)

    def test_rejection_ledger_and_partition(self):
        x = np.linspace(-30, 5, 120)
        y = 900 - .2 * (x + 8) ** 2 + np.random.default_rng(2026).normal(0, 1, len(x))
        y[50:65] += 40
        r = fit_audit(x, y, np.arange(len(x)))
        self.assertEqual(len(r["keep"]) + len(r["deleted"]), len(x))
        self.assertFalse(set(r["keep"]) & set(r["deleted"]))
        for info in r["deleted"].values():
            self.assertGreater(info["rejection_ratio"], 2)
        self.assertFalse(r["stale_coef"])
        last = r["trace"][-1]
        self.assertLessEqual(abs(last["worst_residual"]), 2 * last["sigma"])
        np.testing.assert_allclose(r["coef"], np.polyfit(x[r["keep"]], y[r["keep"]], 2))


if __name__ == "__main__":
    unittest.main()
