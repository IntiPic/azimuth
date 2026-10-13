#!/usr/bin/env python3
"""Read-only audit of azimuth inputs; all experimental choices stay here.

Run from the repository root: python analysis/azimuth_diagnostics/run_diagnostics.py
Or pass --repo PATH --out NEW_DIRECTORY. Existing output directories are refused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "azimuth-audit-mpl"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pvlib as pv
import scipy
import xarray as xr

DATES = ["2026-07-01", "2026-08-22", "2026-08-31"]
LAT, LON, TZ = -34.918034, -56.166802, "America/Montevideo"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fit_audit(x, y, ids, threshold=2., mode="iterative", degree=2):
    """Reproduce production single-worst deletion, including its <6 early exit.

    ids are stable zero-based source row positions. The ledger includes every
    residual used for every decision, including the final stopping iteration.
    """
    keep = np.asarray(ids, dtype=int).copy()
    initial = keep.copy()
    trace, residual_history, deleted = [], [], {}
    iteration = 0
    coef_ids = keep.copy()
    while len(keep) > degree:
        coef_ids = keep.copy()
        coef = np.polyfit(x[keep], y[keep], degree)
        res = y[keep] - np.polyval(coef, x[keep])
        sigma = res.std(ddof=1)
        worst = int(np.argmax(np.abs(res)))
        reject = mode != "none" and np.abs(res[worst]) > threshold * sigma
        ws = float(-coef[1] / (2 * coef[0])) if degree == 2 else float("nan")
        doomed = (keep[np.abs(res) > threshold * sigma] if mode == "one_pass"
                  else keep[[worst]]) if reject else np.array([], dtype=int)
        trace.append(dict(iteration=iteration, n=len(keep), sigma=sigma,
                          omega_star=ws, worst_row=int(keep[worst]),
                          worst_residual=res[worst], threshold=threshold,
                          n_deleted=len(doomed)))
        for row, residual in zip(keep, res):
            residual_history.append(dict(iteration=iteration, row_id=int(row),
                                         residual=float(residual), sigma=float(sigma),
                                         limit=float(threshold * sigma),
                                         rejected=bool(row in doomed)))
        if not reject:
            break
        for row in doomed:
            j = np.flatnonzero(keep == row)[0]
            deleted[int(row)] = dict(rejection_iteration=iteration,
                                    rejection_residual=float(res[j]),
                                    rejection_sigma=float(sigma),
                                    rejection_ratio=float(abs(res[j]) / sigma))
        keep = keep[~np.isin(keep, doomed)]
        iteration += 1
        if len(keep) < 6:
            break
        if mode == "one_pass":
            coef_ids = keep.copy()
            coef = np.polyfit(x[keep], y[keep], degree)
            break
    else:
        raise ValueError("Insufficient finite data for polynomial fit")
    if degree == 2:
        omega = float(-coef[1] / (2 * coef[0]))
    else:
        roots = np.roots(np.polyder(coef))
        maxima = [float(r.real) for r in roots if abs(r.imag) < 1e-8
                  and x[initial].min() <= r.real <= x[initial].max()
                  and np.polyval(np.polyder(coef, 2), r.real) < 0]
        omega = max(maxima, key=lambda v: np.polyval(coef, v)) if maxima else float("nan")
    return dict(keep=keep, coef_ids=coef_ids, coef=coef, omega=omega,
                trace=trace, residual_history=residual_history, deleted=deleted,
                stale_coef=not np.array_equal(keep, coef_ids))


def scenario(df, x, name, center, width=120, threshold=2., mode="iterative",
             finite=True, extra_mask=None, bounds="right", degree=2):
    y = df.gti.to_numpy()
    delta = (df.index - center).total_seconds().to_numpy() / 60
    if width is None:
        mask = np.ones(len(df), dtype=bool)
    else:
        mask = ((delta > -width / 2) if bounds == "right" else (delta >= -width / 2)) & (delta <= width / 2)
    selected = mask.copy()
    if finite:
        mask &= np.isfinite(x) & np.isfinite(y)
    if extra_mask is not None:
        mask &= extra_mask
    if not np.all(np.isfinite(x[mask]) & np.isfinite(y[mask])):
        raise ValueError("Nonfinite ablation cannot be fit without inventing a replacement")
    r = fit_audit(x, y, np.flatnonzero(mask), threshold, mode, degree)
    k, w = r["keep"], r["omega"]
    r["x"] = x
    r["selected"] = selected
    r["eligible"] = mask
    r["summary"] = dict(scenario=name, center=str(center), window_minutes=width,
                        threshold=threshold, mode=mode, degree=degree,
                        n_window=int(selected.sum()), n_eligible=int(mask.sum()),
                        n_used=len(k), n_rejected=len(r["deleted"]), omega_star=w,
                        left_count=int((x[k] < w).sum()), right_count=int((x[k] > w).sum()),
                        left_extent_deg=float(w - x[k].min()),
                        right_extent_deg=float(x[k].max() - w),
                        vertex_inside=bool(x[k].min() <= w <= x[k].max()),
                        curvature_at_vertex=float(np.polyval(np.polyder(r["coef"], 2), w)),
                        rmse_used=float(np.sqrt(np.mean((y[k] - np.polyval(r["coef"], x[k])) ** 2))),
                        stale_coefficients=r["stale_coef"], coefficients=r["coef"].tolist())
    return r


def intervals(points, reason):
    ids = points.loc[points.reason == reason, "row_id"].to_numpy()
    groups = np.split(ids, np.flatnonzero(np.diff(ids) != 1) + 1)
    result = []
    for g in groups:
        if not len(g):
            continue
        p = points.iloc[g]
        result.append(dict(reason=reason, first_row=int(g[0]), last_row=int(g[-1]),
                           start=p.timestamp.iloc[0], end=p.timestamp.iloc[-1], n=len(g),
                           residual_mean=float(p.residual_initial.mean())))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    out = args.out or repo / "analysis/azimuth_diagnostics/runs" / pd.Timestamp.now().strftime("%Y%m%dT%H%M%S")
    out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(repo))
    from src.loader import load_gti_file
    from src.clearsky import estimate_omega_star, get_clear_sky_mask

    tracked = subprocess.check_output(["git", "-C", str(repo), "ls-files", "-z"]).decode().split("\0")
    source_hashes = {p: sha(repo / p) for p in tracked if p and (repo / p).is_file()}
    manifest = dict(repo=str(repo), commit=subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"]).decode().strip(),
        git_status_before=subprocess.check_output(["git", "-C", str(repo), "status", "--short"]).decode(),
        python=sys.version, platform=platform.platform(),
        versions={m.__name__: m.__version__ for m in [np, pd, pv, scipy, matplotlib, xr]},
        location=dict(latitude=LAT, longitude=LON, timezone=TZ),
        source_hashes=source_hashes, input_hashes={}, script_sha256=sha(__file__),
        commands=sys.argv, references=[
            "https://pvlib-python.readthedocs.io/en/stable/_modules/pvlib/solarposition.html",
            "https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.solarposition.hour_angle.html"])
    all_summaries, daily, geometry_rows = [], [], []
    ds = xr.load_dataset(repo / "OUT/lookup_omega_gamma.nc")
    for date in DATES:
        dest = out / date
        dest.mkdir()
        path = next((repo / "data/csk").glob("*" + date.replace("-", "") + "*.csv"))
        raw = pd.read_csv(path)
        df = load_gti_file(path)
        manifest["input_hashes"][str(path.relative_to(repo))] = sha(path)
        all_path = repo / "data/all" / path.name
        same_all = all_path.exists() and sha(all_path) == sha(path)
        eot = pv.solarposition.equation_of_time_spencer71(df.index.dayofyear.unique())
        x = np.asarray(pv.solarposition.hour_angle(df.index, LON, eot))
        y = df.gti.to_numpy()
        center = df.gti.idxmax()
        base = scenario(df, x, "baseline", center)
        prod = estimate_omega_star(df, 120, LON)
        np.testing.assert_allclose(base["coef"], prod["coef"], rtol=1e-12, atol=1e-10)
        np.testing.assert_array_equal(x[base["keep"]], prod["omega"])
        np.testing.assert_array_equal(y[base["keep"]], prod["gti"])
        np.testing.assert_allclose(base["omega"], prod["omega_star"], atol=1e-10)
        clear, ghi_clear = get_clear_sky_mask(df, LAT, LON, TZ)
        vertex_time = df.index[0] + pd.Timedelta(minutes=(base["omega"] - x[0]) * 4)
        solar_noon = df.index[0] + pd.Timedelta(minutes=-x[0] * 4)
        cases = [base]
        for k in [1.5, 2.5, 3., 4.]:
            cases.append(scenario(df, x, f"sigma_{k:g}", center, threshold=k))
        cases.append(scenario(df, x, "no_rejection", center, mode="none"))
        cases.append(scenario(df, x, "one_pass_2sigma", center, mode="one_pass"))
        cases.append(scenario(df, x, "finite_filter_off", center, finite=False))
        cases.append(scenario(df, x, "both_endpoints_included", center, bounds="both"))
        cases.append(scenario(df, x, "clear_mask_applied_EXPERIMENT", center, extra_mask=np.asarray(clear)))
        for width in [60, 90, 150, 180, 240]:
            for mode in ["iterative", "none"]:
                cases.append(scenario(df, x, f"window_{width}_{mode}", center, width, mode=mode))
        for minutes in [-30, -15, 15, 30, 45, 60]:
            for mode in ["iterative", "none"]:
                cases.append(scenario(df, x, f"center_shift_{minutes:+d}_{mode}",
                                      center + pd.Timedelta(minutes=minutes), mode=mode))
        smooth = df.gti.rolling("15min", center=True, min_periods=15).median().idxmax()
        for label, c in [("baseline_vertex", vertex_time), ("rolling_median15", smooth), ("solar_noon", solar_noon)]:
            for mode in ["iterative", "none"]:
                cases.append(scenario(df, x, f"center_{label}_{mode}", c, mode=mode))
        # Fully removing the temporal criterion intentionally fits night and day:
        # retain this as an ablation, never a scientifically recommended estimate.
        cases.append(scenario(df, x, "window_off_all_day_none", center, width=None, mode="none"))
        cases.append(scenario(df, x, "window_off_all_day_iterative", center, width=None))
        cases.append(scenario(df, x, "window_off_positive_gti_none", center, width=None,
                              mode="none", extra_mask=y > 0))
        for degree in [3, 4]:
            cases.append(scenario(df, x, f"degree_{degree}_same_baseline_points", center,
                                  mode="none", degree=degree, extra_mask=np.isin(np.arange(len(df)), base["keep"])))
            cases.append(scenario(df, x, f"degree_{degree}_all_window", center, mode="none", degree=degree))
        pos = pv.solarposition.get_solarposition(df.index, LAT, LON)
        xspa = np.asarray(pv.solarposition.hour_angle(df.index, LON, pos.equation_of_time))
        cases.append(scenario(df, xspa, "hour_angle_SPA", center))
        # Fractional timestamps: the data logger stores a sub-second offset.
        precise = df.copy()
        precise.index = pd.DatetimeIndex(pd.to_datetime(raw.Timestamp)).tz_localize(TZ)
        xp = np.asarray(pv.solarposition.hour_angle(precise.index, LON, eot))
        cases.append(scenario(precise, xp, "timestamps_unfloored", precise.gti.idxmax()))
        cases.append(scenario(precise, xp, "timestamps_unfloored_same_points", precise.gti.idxmax(),
                              width=None, mode="none", extra_mask=np.isin(np.arange(len(df)), base["keep"])))
        # Fit on exactly symmetric support around baseline vertex, without extrapolation.
        radius = min(base["omega"] - x[base["keep"]].min(), x[base["keep"]].max() - base["omega"])
        cases.append(scenario(df, x, "symmetric_common_support", vertex_time, width=radius * 8))
        for case in cases:
            s = case["summary"]
            s.update(date=date, delta_omega=s["omega_star"] - base["omega"],
                     delta_minutes=4 * (s["omega_star"] - base["omega"]))
            all_summaries.append(s)
        selection, curves = [], []
        for case in cases:
            label = case["summary"]["scenario"]
            reason = np.where(case["selected"], "used", "outside_window").astype(object)
            reason[case["selected"] & ~case["eligible"]] = "finite_or_experimental_extra_mask"
            reason[list(case["deleted"])] = "residual_rejection"
            selection.append(pd.DataFrame(dict(scenario=label, row_id=np.arange(len(df)), reason=reason,
                used=np.isin(np.arange(len(df)), case["keep"]), omega_deg=case["x"])))
            xx = np.linspace(case["x"][case["eligible"]].min(), case["x"][case["eligible"]].max(), 300)
            curves.append(pd.DataFrame(dict(scenario=label, omega_deg=xx,
                                          fitted_gti=np.polyval(case["coef"], xx))))
        pd.concat(selection).to_csv(dest / "scenario_point_selection.csv", index=False)
        pd.concat(curves).to_csv(dest / "scenario_curves.csv", index=False)
        points = pd.DataFrame(dict(row_id=np.arange(len(df)), csv_line=np.arange(len(df)) + 2,
            timestamp_raw=raw.Timestamp, timestamp=df.index.astype(str), gti=y, ghi=df.ghi.to_numpy(),
            omega_deg=x, hour_angle_spa=xspa, clearsky_diagnostic=np.asarray(clear),
            in_window=base["selected"], finite=np.isfinite(x) & np.isfinite(y)))
        points["reason"] = np.where(base["selected"], "used", "outside_window")
        points.loc[base["selected"] & ~base["eligible"], "reason"] = "nonfinite"
        points["used_in_fit"] = np.isin(points.row_id, base["keep"])
        initial_coef = np.polyfit(x[base["eligible"]], y[base["eligible"]], 2)
        points["residual_initial"] = y - np.polyval(initial_coef, x)
        points["residual_final"] = y - np.polyval(base["coef"], x)
        for row, info in base["deleted"].items():
            points.loc[row, "reason"] = "iterative_2sigma"
            for key, val in info.items():
                points.loc[row, key] = val
        points.to_csv(dest / "points.csv", index=False)
        points[points.reason == "iterative_2sigma"].to_csv(dest / "rejected_points.csv", index=False)
        pd.DataFrame(base["trace"]).to_csv(dest / "iterations.csv", index=False)
        pd.DataFrame(base["residual_history"]).to_csv(dest / "residuals_each_iteration.csv", index=False)
        pd.DataFrame(intervals(points, "iterative_2sigma")).to_csv(dest / "rejected_intervals.csv", index=False)
        # Leave-one-out influence on the original window, before clipping.
        eligible = np.flatnonzero(base["eligible"])
        no_clip = next(c for c in cases if c["summary"]["scenario"] == "no_rejection")
        loo = []
        for i in eligible:
            k = eligible[eligible != i]
            c = np.polyfit(x[k], y[k], 2)
            loo.append(dict(row_id=i, timestamp=str(df.index[i]),
                            omega_star=-c[1] / (2 * c[0]), delta_omega=-c[1] / (2 * c[0]) - no_clip["omega"]))
        pd.DataFrame(loo).to_csv(dest / "leave_one_out.csv", index=False)
        # Symmetry of observations: compare interpolated raw measurements at ±offset.
        offsets = np.arange(1, 61, dtype=float)
        minute_axis = (df.index - vertex_time).total_seconds().to_numpy() / 60
        paired = pd.DataFrame(dict(offset_min=offsets,
            left_gti=np.interp(-offsets, minute_axis, y), right_gti=np.interp(offsets, minute_axis, y),
            left_ghi=np.interp(-offsets, minute_axis, df.ghi), right_ghi=np.interp(offsets, minute_axis, df.ghi)))
        paired["right_minus_left_gti"] = paired.right_gti - paired.left_gti
        paired["right_minus_left_ghi"] = paired.right_ghi - paired.left_ghi
        paired.to_csv(dest / "raw_symmetry_pairs.csv", index=False)
        curvature = []
        for side in ["left", "right"]:
            k = base["keep"][(x[base["keep"]] < base["omega"]) if side == "left" else (x[base["keep"]] > base["omega"])]
            curvature.append(dict(side=side, mean_residual=float(np.mean(points.residual_final.iloc[k])), n=len(k)))
        gcoef = np.polyfit(x[base["eligible"]], df.ghi.to_numpy()[base["eligible"]], 2)
        ghi_res = df.ghi.to_numpy() - np.polyval(gcoef, x)
        points["ghi_residual_own_quadratic_all_window"] = ghi_res
        points.to_csv(dest / "points.csv", index=False)
        points[points.reason == "iterative_2sigma"].to_csv(dest / "rejected_points.csv", index=False)
        cadence = (df.index[1:] - df.index[:-1]).total_seconds() / 60
        day = dict(date=date, input_rows=len(df), all_copy_identical=same_all,
                   max_time=str(center), max_gti=float(df.gti.max()), vertex_time=str(vertex_time),
                   raw_peak_to_vertex_min=(vertex_time - center).total_seconds() / 60,
                   median15_peak=str(smooth), duplicates=int(df.index.duplicated().sum()),
                   cadence_min=float(np.min(cadence)), cadence_max=float(np.max(cadence)),
                   nonfinite_total=int((~points.finite).sum()),
                   initial_sigma=float(base["trace"][0]["sigma"]), final_sigma=float(base["trace"][-1]["sigma"]),
                   clear_in_window=int(np.asarray(clear)[base["selected"]].sum()),
                   clear_used=int(np.asarray(clear)[base["keep"]].sum()),
                   clear_rejected=int(np.asarray(clear)[list(base["deleted"])].sum()),
                   symmetry_gti_mae_60min=float(paired.right_minus_left_gti.abs().mean()),
                   gti_ghi_detrended_correlation=float(np.corrcoef(points.residual_initial[base["eligible"]], ghi_res[base["eligible"]])[0,1]),
                   residual_sides=curvature, production_exact_match=True,
                   eot_spencer_min=float(eot[0]),
                   spa_minus_spencer_window_min_deg=float((xspa-x)[base["selected"]].min()),
                   spa_minus_spencer_window_max_deg=float((xspa-x)[base["selected"]].max()),
                   baseline=base["summary"])
        # Controlled geometry: clean modeled POA with lookup metadata. These are
        # synthetic controls, NOT reconstructed measured irradiance or azimuth truth.
        curve = ds.omega_star.sel(doy=df.index.dayofyear[0])
        estimated_gamma = float(curve.azimuth[np.argmin(abs(curve.values - base["omega"]))])
        loc = pv.location.Location(float(ds.attrs["latitude"]), float(ds.attrs["longitude"]), TZ)
        p = loc.get_solarposition(df.index)
        sky = loc.get_clearsky(df.index)
        fine_times = pd.date_range(df.index[0], df.index[-1], freq="10s")
        fine_pos = loc.get_solarposition(fine_times)
        fine_sky = loc.get_clearsky(fine_times)
        fine_x = np.asarray(pv.solarposition.hour_angle(fine_times, LON, eot))
        model_arrays = {}
        for gamma in [0., estimated_gamma]:
            poa = pv.irradiance.get_total_irradiance(float(ds.attrs["surface_tilt"]), gamma,
                p.zenith, p.azimuth, sky.dni, sky.ghi, sky.dhi,
                dni_extra=pv.irradiance.get_extra_radiation(df.index),
                airmass=pv.atmosphere.get_relative_airmass(p.zenith),
                albedo=float(ds.attrs["albedo"]), model="perez-driesse")["poa_global"]
            modeled = df.copy()
            modeled["gti"] = poa
            fine_poa = pv.irradiance.get_total_irradiance(float(ds.attrs["surface_tilt"]), gamma,
                fine_pos.zenith, fine_pos.azimuth, fine_sky.dni, fine_sky.ghi, fine_sky.dhi,
                dni_extra=pv.irradiance.get_extra_radiation(fine_times),
                airmass=pv.atmosphere.get_relative_airmass(fine_pos.zenith),
                albedo=float(ds.attrs["albedo"]), model="perez-driesse")["poa_global"]
            true_peak = float(fine_x[np.argmax(fine_poa)])
            model_arrays[f"poa_azimuth_{gamma:.1f}"] = np.asarray(poa)
            for label, ct in [("observed_center", center), ("modeled_center", poa.idxmax())]:
                for mode in ["none", "iterative"]:
                    mr = scenario(modeled, x, label, ct, mode=mode)
                    geometry_rows.append(dict(date=date, assumed_azimuth=gamma, synthetic=True,
                        center_choice=label, mode=mode, modeled_peak=true_peak,
                        modeled_peak_grid_seconds=10,
                        omega_star=mr["omega"], bias_vs_model_peak=mr["omega"] - true_peak,
                        n_rejected=len(mr["deleted"]), rmse_used=mr["summary"]["rmse_used"]))
            kc = base["keep"]
            model_coef = np.polyfit(x[kc], np.asarray(poa)[kc], 2)
            model_res = np.asarray(poa)[kc] - np.polyval(model_coef, x[kc])
            geometry_rows.append(dict(date=date, assumed_azimuth=gamma, synthetic=True,
                center_choice="observed_center_same_retained_points", mode="none",
                modeled_peak=true_peak, modeled_peak_grid_seconds=10,
                omega_star=-model_coef[1] / (2 * model_coef[0]),
                bias_vs_model_peak=-model_coef[1] / (2 * model_coef[0]) - true_peak,
                n_rejected=0, rmse_used=float(np.sqrt(np.mean(model_res ** 2)))))
        pd.DataFrame(dict(timestamp=df.index.astype(str), omega_deg=x, **model_arrays)).to_csv(dest / "synthetic_geometry.csv", index=False)
        day["lookup_azimuth_for_control_only"] = estimated_gamma
        daily.append(day)
        plot_day(dest, df, x, points, base, cases, vertex_time, paired, sky, model_arrays)
        plot_comparisons(dest, df, x, cases)
        plot_context(dest, df, base, cases, vertex_time, sky)
        print(date, json.dumps(day, default=str), flush=True)
    pd.DataFrame(all_summaries).to_csv(out / "sensitivity.csv", index=False)
    pd.DataFrame(geometry_rows).to_csv(out / "geometry_controls.csv", index=False)
    (out / "daily_summary.json").write_text(json.dumps(daily, indent=2, default=str) + "\n")
    manifest["tracked_files_unchanged"] = all(sha(repo / p) == h for p, h in source_hashes.items())
    assert manifest["tracked_files_unchanged"], "Production files changed during audit"
    manifest["output_hashes"] = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n")
    print("Completed:", out)


def plot_day(dest, df, x, points, base, cases, vertex_time, paired, sky, models):
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    minute = (df.index - vertex_time).total_seconds().to_numpy() / 60
    near = abs(minute) <= 150
    ax = axes[0, 0]
    styles = {"outside_window": ("#a5abb2", ".", "Fuera de ventana"),
              "iterative_2sigma": ("#d74635", "x", "Rechazo iterativo 2σ"),
              "used": ("#126ca6", "o", "Usados en ajuste")}
    for reason, (color, marker, label) in styles.items():
        zoom = (x >= x[base["selected"]].min() - 2.5) & (x <= x[base["selected"]].max() + 2.5)
        m = (points.reason.to_numpy() == reason) & zoom
        ax.scatter(x[m], df.gti[m], c=color, marker=marker, s=16, label=f"{label} ({int((points.reason == reason).sum())})")
    xx = np.linspace(x[base["selected"]].min(), x[base["selected"]].max(), 400)
    for name, label, color in [("baseline", "Cuadrática + 2σ", "#126ca6"), ("no_rejection", "Cuadrática sin rechazo", "#a87616")]:
        c = next(c for c in cases if c["summary"]["scenario"] == name)
        ax.plot(xx, np.polyval(c["coef"], xx), color=color, label=f"{label}: {c['omega']:.3f}°")
    ax.axvline(base["omega"], color="#126ca6", ls=":")
    ax.set(xlabel="Ángulo horario (°)", ylabel="GTI (W/m²)")
    ax.legend(fontsize=8)
    ax = axes[0, 1]
    m = base["selected"]
    ax.scatter(x[m], points.residual_final[m], c=np.where(points.used_in_fit[m], "#126ca6", "#d74635"), s=14)
    ax.axhline(0, color="black", lw=.7)
    ax.axhline(2 * base["trace"][-1]["sigma"], color="#999999", ls="--")
    ax.axhline(-2 * base["trace"][-1]["sigma"], color="#999999", ls="--")
    ax.set(xlabel="Ángulo horario (°)", ylabel="Residuo respecto al ajuste final (W/m²)", title="Líneas: ±2σ final; cada rechazo usó su σ de esa iteración")
    ax = axes[1, 0]
    trace = pd.DataFrame(base["trace"])
    ax.plot(trace.iteration, trace.omega_star, "o-", ms=3, color="#126ca6")
    ax.set(xlabel="Iteración de rechazo (0 = todos los puntos)", ylabel="ω* (°)")
    ax2 = ax.twinx()
    ax2.plot(trace.iteration, trace.sigma, color="#d74635", ls="--")
    ax2.set_ylabel("σ de residuos (W/m²)", color="#d74635")
    ax = axes[1, 1]
    ax.plot(paired.offset_min, paired.right_minus_left_gti, label="GTI cruda")
    ax.axhline(0, color="black", lw=.7)
    ax.set(xlabel="Distancia al vértice base (min)", ylabel="Derecha − izquierda (W/m²)", title="Pares por interpolación de datos a 1 min")
    ax.legend()
    for ax in axes.flat:
        ax.grid(alpha=.18)
    fig.suptitle(f"{dest.name} · ventana 120 min · ω* = {base['omega']:.6f}° · usados {len(base['keep'])}/120", fontsize=16)
    fig.tight_layout(rect=(0, 0, 1, .95))
    fig.savefig(dest / "diagnostic.png", dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(12, 7))
    m = base["eligible"]
    gti_res = points.residual_initial.to_numpy()[m]
    ghi_res = points.ghi_residual_own_quadratic_all_window.to_numpy()[m]
    axes[0].plot(x[m], gti_res / gti_res.std(ddof=1), label="GTI / σ inicial")
    axes[0].plot(x[m], ghi_res / ghi_res.std(ddof=1), "--", label="GHI / su propio σ")
    axes[0].set(ylabel="Residuo estandarizado", title=f"Cada señal resta su cuadrática sobre los 120 puntos; r={np.corrcoef(gti_res, ghi_res)[0,1]:.3f}")
    k = base["keep"]
    axes[1].plot(x[k], points.residual_final.iloc[k], label="GTI medida, puntos retenidos")
    for label, ymodel in models.items():
        c = np.polyfit(x[k], ymodel[k], 2)
        axes[1].plot(x[k], ymodel[k] - np.polyval(c, x[k]), "--", label="Control sintético " + label)
    axes[1].set(ylabel="Residuo (W/m²)", title="Mismos puntos retenidos: comparación con controles geométricos sin ruido")
    for ax in axes:
        ax.set_xlabel("Ángulo horario (°)")
        ax.axhline(0, color="black", lw=.7)
        ax.grid(alpha=.18)
        ax.legend(fontsize=9)
    fig.suptitle(dest.name + " · irregularidades compartidas y control solar", fontsize=15)
    fig.tight_layout(rect=(0,0,1,.95))
    fig.savefig(dest / "shared_residuals_geometry.png", dpi=160)
    plt.close(fig)


def plot_comparisons(dest, df, x, cases):
    chosen = ["baseline", "no_rejection", "one_pass_2sigma", "sigma_3",
              "center_baseline_vertex_iterative", "window_180_iterative"]
    titles = ["Base: 120 min, 2σ iterativo", "120 min, sin rechazo", "120 min, una pasada 2σ",
              "120 min, 3σ iterativo", "120 min, centrada en vértice base", "180 min, 2σ iterativo"]
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    for ax, label, title in zip(axes.flat, chosen, titles):
        r = next(c for c in cases if c["summary"]["scenario"] == label)
        m = r["selected"]
        xx = np.linspace(x[m].min(), x[m].max(), 300)
        rejected = np.asarray(list(r["deleted"]), dtype=int)
        ax.scatter(x[rejected], df.gti.to_numpy()[rejected], c="#d74635", marker="x", s=18, label="Rechazados")
        ax.scatter(x[r["keep"]], df.gti.to_numpy()[r["keep"]], c="#126ca6", s=12, label="Usados")
        ax.plot(xx, np.polyval(r["coef"], xx), c="#126ca6")
        if r["summary"]["vertex_inside"]:
            ax.plot(r["omega"], np.polyval(r["coef"], r["omega"]), "o", c="black", ms=5)
        ax.set(title=f"{title}\nω*={r['omega']:.3f}° · n={len(r['keep'])}",
               xlabel="Ángulo horario (°)", ylabel="GTI (W/m²)")
        ax.legend(fontsize=8)
        ax.grid(alpha=.18)
    fig.suptitle(dest.name + " · comparaciones reproducibles (escalas por panel)", fontsize=15)
    fig.tight_layout(rect=(0,0,1,.95))
    fig.savefig(dest / "comparisons.png", dpi=160)
    plt.close(fig)


def plot_context(dest, df, base, cases, vertex_time, sky):
    minute = (df.index - vertex_time).total_seconds().to_numpy() / 60
    near = abs(minute) <= 150
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    ax = axes[0]
    ax.plot(minute[near], df.gti[near], label="GTI cruda")
    ax.plot(minute[near], df.ghi[near], label="GHI cruda")
    ax.plot(minute[near], sky.ghi[near], "--", label="GHI modelo cielo claro (control)")
    ax.axvspan(minute[base["selected"]].min(), minute[base["selected"]].max(), alpha=.08)
    ax.axvline(0, color="black", ls=":")
    ax.set(xlabel="Minutos desde vértice base", ylabel="Irradiancia (W/m²)")
    ax.legend()
    ax = axes[1]
    for mode, label in [("iterative", "2σ iterativo"), ("none", "Sin rechazo")]:
        cc = [c["summary"] for c in cases if c["summary"]["scenario"] in [f"window_{w}_{mode}" for w in [60,90,150,180,240]]]
        cc.append(next(c["summary"] for c in cases if c["summary"]["scenario"] == ("baseline" if mode == "iterative" else "no_rejection")))
        cc = sorted(cc, key=lambda c: c["window_minutes"])
        ax.plot([c["window_minutes"] for c in cc], [c["omega_star"] for c in cc], "o-", label=label)
    ax.set(xlabel="Ancho total de ventana (min), centrada en máximo crudo", ylabel="ω* (°)")
    ax.legend()
    for ax in axes:
        ax.grid(alpha=.18)
    fig.suptitle(dest.name + " · contexto y sensibilidad a ventana", fontsize=15)
    fig.tight_layout()
    fig.savefig(dest / "window_context.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
