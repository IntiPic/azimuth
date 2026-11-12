# Azimut2026 publication results

This folder presents existing validated estimates. It does not run or import
the scientific pipeline, screening, irradiance data or lookup tables.

## Regenerate

Requires Python 3.10+, NumPy, pandas and Matplotlib. From the repository root:

```bash
python paper/generate_figures.py
```

This one command generates **all three figures and both tables**. For tables
alone, use `python paper/generate_tables.py --run-id tables_v1`.
Use a new run ID each time, or omit it for a UTC timestamp. An existing ID is
rejected; earlier results are never overwritten. Paths are resolved relative
to the scripts, independent of the working directory.

The reviewed first release is `publication_v1_verified`. The earlier
`publication_v1` run is retained as an inspection draft; both use identical
scientific inputs and presentation code. The verified run also records the
final verification test source and this README.

The first generation used `/Users/inti/conda/envs/uv-project/bin/python`.
Exact versions, command, Git commit/status, code hashes and input hashes are
recorded in each run's manifest.

## Fixed inputs and validation

Only these two CSVs supply scientific data; no newest-file selection:

- AZ: `outputs/AZ/results/azimuth_results_20261103_205945.csv` (7 cases).
- TA: `outputs/TA/results/azimuth_results_20261103_204427.csv` (29 cases).

Validation checks the complete column sets, row counts, station, finite numeric
values, unique ISO dates, day of year, tilt, angular ranges, discard metadata,
AZ nominal counts and consistency of the stored difference columns. No rows
are removed and no data are filled in. Each manifest retains original CSV row
numbers, raw dates and all original fields, including discard reasons.

## Outputs

- `outputs/figures/<run-id>/F01_azimuth_over_time.{pdf,png}`
- `outputs/figures/<run-id>/F02_estimated_vs_nominal_AZ.{pdf,png}`
- `outputs/figures/<run-id>/F03_differences_by_nominal_AZ.{pdf,png}`
- `outputs/tables/<run-id>/T01_AZ_by_nominal_orientation.{csv,tex}`
- `outputs/tables/<run-id>/T02_TA_azimuth_estimates.{csv,tex}`
- `outputs/manifests/<run-id>/manifest.json`

Figures use a local `matplotlib.rc_context`, embedded TrueType fonts, vector
PDF graphics and 300 dpi inspection PNGs. F01 is 7.1 inches wide (two columns);
F02/F03 are 3.5 inches wide (one column). The two F01 panels have different
vertical ranges. Colors and marker shapes distinguish AZ nominal groups in
F02/F03. LaTeX tables require `\usepackage{booktabs}`; no manuscript is edited.
CSV values retain floating-point precision. LaTeX rounds only for display to
two decimal places. Missing SD is `NA` in CSV and `--` in LaTeX.

## Scientific definitions and limits

- All angles are in degrees, retaining the CSV angular origin and sign.
- `delta_gamma = azimuth - azimuth_nominal`. The stored `azimuth_error_deg`
  uses the opposite sign (nominal minus estimated). Metrics are recomputed
  directly from original azimuths, not copied from that error field.
- For each AZ nominal group: signed bias = mean(delta); MAE = mean(abs(delta));
  RMSE = sqrt(mean(delta squared)); mean azimuth = arithmetic mean.
- Sample SD uses the N-1 denominator and is not calculated for N=1. In F03,
  mean and mean +/- sample SD are added only for N>=2 (10 and 30 degrees).
  Every daily point is shown; horizontal offsets within groups only prevent
  overlap. SD of the differences equals SD of azimuth at a fixed nominal.
- These narrow angular ranges do not cross the angular branch: direct
  differences and arithmetic summaries need no circular wrapping. These are
  descriptive statistics of the retained days, not calibrated uncertainties,
  standard errors or confidence intervals.
- AZ nominal orientations come exclusively from the CSV: 0 degrees (N=1),
  10 degrees (N=3), 20 degrees (N=1), 30 degrees (N=2). They are documented
  nominal settings, not independently established ground truth. There are no
  validated cases at 40 degrees. A 40-degree axis tick is only a scale tick.
- TA has no numeric nominal reference in its CSV. It receives no invented
  reference, bias or accuracy assessment.
- `date` is the calendar date of the GTI maximum, as assigned in `main.py`
  (`gti_max_time.date()`), with local zone `America/Montevideo` in
  `src/config.py` and `src/loader.py`. The CSVs contain neither the exact
  maximum timestamp nor its UTC offset; this workflow cannot independently
  revalidate that timing without additional inputs. It preserves the supplied
  dates, rather than using screening dates or filenames. No timestamps are
  invented or timezone-converted. Nominal markers appear only on AZ observed
  dates; there are no time-series connecting lines across missing observations.
- The TA measurement period is the span from its first to last retained GTI
  maximum date, not evidence of continuous acquisition or usable coverage.
- This is presentation of already validated results, not a new validation of
  the scientific estimator or the nominal settings. No estimator parameters,
  outlier criteria, time corrections, fits or LUTs are changed.

## Verification

```bash
python -m unittest discover -s tests -p 'test_paper_results.py'
```

The checks independently recompute summaries, verify sign/SD and data rejection,
compare figure points and error bars with the original rows and tables, and
check that style settings do not leak. Inspect the PNGs at column width after
each visual change. For PDF inspection, `pdfimages -list` should report no
images and `pdffonts` should report embedded fonts; a PDF parser can also verify
path operators and absence of image objects. The first run's verification
report records the actual PDF inspection and PNG review.

All writes are confined to `paper/outputs/` (apart from temporary Matplotlib
cache files). No files under repository `outputs/AZ/`, `outputs/TA/`, `OUT/`,
or the manuscript are modified. The repository-wide `outputs/` ignore rule
also ignores generated paper artifacts; source scripts remain trackable.
