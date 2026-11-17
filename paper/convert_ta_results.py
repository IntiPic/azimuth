"""Create an explicit SWC2021 derivative; never overwrite the historical TA CSV.

Only azimuth is negated. All other fields (including omega_star), row order and
numeric text are preserved. This conversion does not establish TA's physical
orientation without an external reference.
"""
import csv
from decimal import Decimal
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TA_SOURCE = "outputs/TA/results/azimuth_results_20261103_204427.csv"
TA_DERIVED = "outputs/TA/results/azimuth_results_20261103_204427_swc2021.csv"


def converted_bytes(raw):
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8"))))
    column = rows[0].index("azimuth")
    if len(rows) - 1 != 29:
        raise ValueError("Expected 29 historical TA cases")
    for row in rows[1:]:
        # copy_negate is exact, independent of Decimal context precision.
        row[column] = str(Decimal(row[column]).copy_negate())
    result = io.StringIO(newline="")
    csv.writer(result, lineterminator="\n").writerows(rows)
    return result.getvalue().encode("utf-8")


def main():
    source, target = ROOT / TA_SOURCE, ROOT / TA_DERIVED
    converted = converted_bytes(source.read_bytes())
    with target.open("xb") as stream:
        stream.write(converted)
    print(f"Created {target}; N=29; azimuth negated, omega_star unchanged.")


if __name__ == "__main__":
    main()
