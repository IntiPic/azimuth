#!/usr/bin/env python3
"""Screening configurable para AZ y TA, reutilizando el punto de entrada de TA.

Ejemplo: python analysis/generate_daily_screening.py --station AZ
Sin --station se procesa AZ; el script antiguo de TA conserva su valor por defecto.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.generate_daily_screening_TA import main as screening_main


def main():
    screening_main(default_station="AZ")


if __name__ == "__main__":
    main()
