# Diagnóstico de azimut: julio y agosto de 2026

Auditoría independiente de `src/clearsky.py::estimate_omega_star` para
2026-07-01, 2026-08-22 y 2026-08-31. No cambia código productivo, datos ni
figuras existentes. El informe de la corrida entregada está en `REPORT.md`.

## Ejecución

Desde la raíz del repositorio, con un entorno que tenga numpy, pandas, pvlib,
matplotlib, scipy, xarray y un lector NetCDF compatible:

```sh
python analysis/azimuth_diagnostics/run_diagnostics.py
python -m unittest discover -s analysis/azimuth_diagnostics -p 'test_*.py'
```

También acepta rutas explícitas:

```sh
python analysis/azimuth_diagnostics/run_diagnostics.py --repo /ruta/azimuth --out /ruta/nueva/corrida
```

Se utilizó `/Users/inti/conda/envs/uv-project/bin/python`. Las versiones exactas
están en `runs/20260912_verified/manifest.json`. El programa crea un directorio nuevo
y rechaza sobrescribir uno existente. No ejecutar `main.py` ni `lookup_table.py`
para esta auditoría: producen outputs históricos y la tabla anual.

## Entradas y trazabilidad

- Los tres CSV originales de `data/csk/`; se verifica si son idénticos a `data/all/`.
- Carga y ajuste productivos importados directamente del repo, con verificación
  numérica de coeficientes, ω*, datos y puntos retenidos en cada fecha.
- `OUT/lookup_omega_gamma.nc` solamente para controles sintéticos. El azimut
  inferido por esta tabla no es una verdad independiente ni una validación del método.
- Latitud −34.918034°, longitud −56.166802°, `America/Montevideo`, igual que `main.py`.
- `row_id` comienza en 0; `csv_line = row_id + 2` identifica la línea original
  contando el encabezado. Se conserva timestamp original y timestamp truncado.

## Salidas por corrida

`sensitivity.csv` contiene todos los escenarios, coeficientes, ω*, diferencias
contra base, número de puntos y controles de validez. `geometry_controls.csv`
contiene experimentos sintéticos, y `daily_summary.json` los resúmenes por fecha.
`manifest.json` registra commit, hashes, versiones, comando y ausencia de cambios
en archivos versionados durante la ejecución.

Por fecha:

- `points.csv`: las 1440 filas, GTI/GHI, hour angle, etapa de exclusión, máscara
  de cielo claro informativa y motivo/iteración/residuo/σ para cada rechazo.
- `rejected_points.csv` y `rejected_intervals.csv`: rechazos y bloques temporales.
- `iterations.csv`: evolución de σ y ω* en las decisiones del algoritmo original.
- `residuals_each_iteration.csv`: cada punto sobreviviente en cada iteración,
  con residuo, umbral y decisión. La última iteración documenta la parada.
- `scenario_point_selection.csv`, `scenario_curves.csv`: selección de filas y
  curvas de todos los escenarios; se unen a `points.csv` por `row_id`.
- `leave_one_out.csv`: influencia de quitar cada punto, antes del rechazo iterativo.
- `raw_symmetry_pairs.csv`: datos crudos interpolados en pares ±1…60 min del
  vértice base; pueden usar datos fuera de la ventana de fit, sin extrapolar.
  No suponer que GHI debe ser simétrica alrededor del máximo de GTI.
- `synthetic_geometry.csv`: GTI simulada en los timestamps originales.
- `diagnostic.png`, `comparisons.png`, `window_context.png`,
  `shared_residuals_geometry.png`: inspección visual de puntos, residuos y variantes.

## Alcance de las variantes

Base: ventana `(t_max−60 min, t_max+60 min]`, grado 2, máximo crudo para centrar,
eliminación secuencial del mayor residuo absoluto mientras exceda `2*std(ddof=1)`.
La máscara de cielo claro **no se aplica** en producción. Aplicarla aquí es
un experimento explícito.

Se varían umbrales 1.5/2/2.5/3/4σ, una sola pasada, ausencia de rechazo,
ventanas 60/90/120/150/180/240 min, centro temporal, límites de ventana,
finitud, precisión temporal y Spencer frente a SPA. Se comparan grados 3 y 4
con los mismos puntos base y con todos los puntos de la ventana. Estas variantes
no se proponen automáticamente como cambios científicos.

Revisar `vertex_inside`, `curvature_at_vertex`, `stale_coefficients` y `n_used`:
un número finito no garantiza un máximo físicamente interpretable. En particular,
el algoritmo original puede salir al quedar menos de 6 puntos conservando los
coeficientes del conjunto anterior. La auditoría reproduce y marca ese comportamiento;
no lo corrige silenciosamente. Los casos sin ventana incluyen la noche a propósito
y solo prueban la dependencia del filtro temporal. El mínimo RMSE entre conjuntos
de puntos distintos no sirve para elegir un umbral.

Los controles de cielo claro son simulaciones Perez–Driesse con parámetros de la
tabla del repo y cielo atmosférico climatológico de pvlib. El máximo de referencia
se busca en una malla de 10 s (paso 0.041667°). No sustituyen mediciones de
DNI/DHI, nubosidad o azimut. Toda comparación es sensibilidad, no incertidumbre
estadística ni estimación de la orientación verdadera.
