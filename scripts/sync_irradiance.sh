#!/usr/bin/env bash

set -e

REMOTE="inti@164.73.222.4:/datos01/LES/VAULT/vault_LES/AZ/2026/DataT/"
LOCAL="data/irradiance/"

mkdir -p "$LOCAL"

echo "Actualizando datos de irradiancia..."

rsync -av --progress \
    --include='AZ_DT_2026052[1-9]T*.csv' \
    --include='AZ_DT_2026053[0-1]T*.csv' \
    --include='AZ_DT_20260[6-9]*.csv' \
    --include='AZ_DT_20261[0-2]*.csv' \
    --exclude='*' \
    "$REMOTE" \
    "$LOCAL"

echo "Datos actualizados en $LOCAL"
