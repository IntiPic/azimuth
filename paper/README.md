# Azimut2026 publication results — SWC2021

This workflow presents existing estimates. It does not execute the estimator,
screening, raw irradiance processing or LUT generation. All angles are degrees.
SWC2021 uses north = 0, east negative and west positive; `omega_star` is unchanged.
The manuscript sections, TODO and figures are not edited by this workflow.

## Reproduce

Use Python 3.10+, NumPy, pandas, Matplotlib, xarray and netCDF4; pytest is needed
for regression checks. The installed environment used for this change is
`/Users/inti/conda/envs/uv-project/bin/python`.

```bash
# One-time derivation, only if the explicit TA derivative does not yet exist:
python paper/convert_ta_results.py
python -m pytest -q
python paper/generate_figures.py --run-id NEW_UNIQUE_RUN_ID
```

The figure command creates F01–F03, F_LUT and T01–T02 with a provenance manifest.
Tables alone: `python paper/generate_tables.py --run-id NEW_UNIQUE_RUN_ID`.
Without `--run-id`, a new UTC timestamp is used. Existing run IDs are rejected.
No command updates `paper/outputs/current` or copies products into the manuscript.
Standalone LUT inspection requires a new directory:

```bash
python paper/generate_lut_figure.py --output-dir paper/outputs/NEW_LUT_RUN/figures
```

## Fixed inputs and provenance

- AZ: `outputs/AZ/results/spa_1s/azimuth_results.csv`, already SWC2021, 14 cases.
  `AZ_RESULTS_CSV` may select an explicit alternative, subject to the same
  validation; the selected path, hash and original rows are recorded.
- TA: `outputs/TA/results/azimuth_results_20261103_204427_swc2021.csv`, 29 cases.
  The source `outputs/TA/results/azimuth_results_20261103_204427.csv` is preserved.
  `convert_ta_results.py` negates only azimuth using exact decimal sign inversion;
  every other field, including omega*, row order and numeric text is unchanged.
  Loading verifies this derivation and records both hashes. A pre-existing
  derivative is never overwritten.
- F_LUT: `lookup/AZ/lookup_omega_gamma_1s_swc2021.nc`, versioned NetCDF, read
  directly with xarray/netCDF4. No auxiliary CSV is read. Coordinates, values,
  attributes, shape (1801 × 365), dates, 0.1° spacing and strictly increasing
  omega*(gamma) on every day are checked. No omega* transformation is applied.

The manifest records commit, branch, local status/diff hash, source/test hashes,
versions, command, input and output hashes, original CSV row numbers, raw dates,
all original fields and discard reasons. The LUT entry identifies the actual
NetCDF read, its hash, attributes and minimum positive omega* increment.
`paper/metadata/lut_AZ_1s.json` describes that same SWC2021 NetCDF.

## Products and definitions

Products are written under `paper/outputs/<run-id>/`:

- `figures/F01_azimuth_over_time.{pdf,png}`: 14 AZ and 29 TA points; no lines
  implying continuous observations. AZ nominal markers appear only on its dates.
- `figures/F02_estimated_vs_nominal_AZ.{pdf,png}`: equal limits and equal angular
  scales, with identity line; all 14 cases are included.
- `figures/F03_differences_by_nominal_AZ.{pdf,png}`: signed daily differences,
  with mean ± sample SD only for groups with N ≥ 2.
- `figures/F_LUT_seasonal_AZ_1s.{pdf,png}`: four seasonal curves from the NetCDF.
- `tables/T01_AZ_by_nominal_orientation.{csv,tex}` and
  `tables/T02_TA_azimuth_estimates.{csv,tex}`.
- `manifest.json`.

`delta_gamma = azimuth - azimuth_nominal` is computed from the supplied angles.
The stored `azimuth_error_deg` is nominal minus estimated; it is validated but
never substituted for delta. Signed bias = mean(delta), MAE = mean(abs(delta)),
and RMSE = sqrt(mean(delta²)). Reversing both azimuth signs reverses signed bias
and preserves MAE/RMSE and sample SD. No error is negated solely for display.
The plots' angular ranges are mirrored to match the converted inputs.

AZ nominal counts are 0° (1), −10° (3), −20° (1), −30° (5), −40° (3), −50° (1).
The style also supports −60°; no −60° observations are invented. Each orientation
retains its previous magnitude-specific color and marker. Nominal settings are
not independently established ground truth. TA has no numeric nominal reference:
its converted sign alone does not establish physical east/west orientation
without external evidence. No TA bias or accuracy assessment is inferred.

Sample SD uses N−1 and is omitted for N=1. These are descriptive statistics,
not calibrated uncertainties. Direct differences need no wrapping for these
angular spans. CSV precision is retained; LaTeX uses two decimal places.
Dates are the supplied local GTI-maximum calendar dates (America/Montevideo),
without time of day or UTC offset. No new timestamps are invented. TA's period
spans its first and last retained dates, not continuous acquisition.

## Regression and review

`python -m pytest -q` checks signs, exact counts, figure points and error bars,
visible ranges, equal F02 scales, TA field preservation, AZ MAE/RMSE invariance,
signed bias inversion and exact omega* preservation. It also checks increasing
LUT values against both the versioned NetCDF and the preserved original LUT.
Invalid LUT controls are kept separate from measured results.

`tests/fixtures/AZ_legacy_14.csv` restores the historical 14-row AZ input from
`paper/outputs/current/manifest.json`; its bytes match the original CSV hash
recorded in that manifest. The adjacent JSON records the extraction provenance.
This fixed reference makes regression independent of regenerated historical
figures or tables. No historical artifact was modified to create it.

Inspect the new PNGs before replacing any publication artifact. PDFs use vector
paths and embedded TrueType fonts; PNGs use 300 dpi. Matplotlib style is local.
Generated artifacts and the TA derivative follow existing Git ignore rules;
keep the new derivative and run directory when archiving this publication run.
