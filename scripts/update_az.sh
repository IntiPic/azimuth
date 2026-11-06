
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--no-sync" ) ]]; then
    echo "Uso: $0 [--no-sync]"
    exit 2
fi

# 1. Descargar archivos nuevos, salvo que se indique lo contrario.
if [[ "${1:-}" != "--no-sync" ]]; then
    echo "[1/4] Sincronizando datos AZ..."
    bash scripts/sync_irradiance.sh
fi

# 2. Actualizar candidatos clear-sky.
echo "[2/4] Actualizando screening..."
python analysis/generate_daily_screening.py --station AZ

# 3. Estimar azimuts utilizando la configuración científica actual.
echo "[3/4] Estimando azimuts..."
python main.py

# Localizar el archivo de resultados desde config.py.
export AZ_RESULTS_CSV="$(
python - <<'PY'
from pathlib import Path
from src.config import get_station_config

path = Path(get_station_config("AZ")["results_dir"]) / "azimuth_results.csv"

if not path.is_file():
    raise SystemExit(f"No existe el resultado: {path}")

print(path.as_posix())
PY
)"

# 4. Regenerar publicación manteniendo respaldo ante errores.
echo "[4/4] Actualizando figuras, tablas y manifiesto..."

OUT="$ROOT/paper/outputs"
mkdir -p "$OUT"

BACKUP="$(mktemp -d "$OUT/.current_backup.XXXXXXXX")"

if [[ -d "$OUT/current" ]]; then
    mv "$OUT/current" "$BACKUP/current"
fi

if python paper/generate_figures.py --run-id current; then
    rm -rf "$BACKUP"
else
    echo "ERROR: restaurando publicación anterior..."
    rm -rf "$OUT/current"

    if [[ -d "$BACKUP/current" ]]; then
        mv "$BACKUP/current" "$OUT/current"
    fi

    rmdir "$BACKUP"
    exit 1
fi

echo ""
echo "Actualización finalizada."
echo "Resultados: $AZ_RESULTS_CSV"
echo "Publicación: paper/outputs/current/"
