# Auditoría y procesamiento completo de TA

`DIAGNOSIS.md` contiene los hallazgos previos a cambios productivos. Esta ruta amplía TA al período solicitado sin ejecutar los scripts que escriben en las ubicaciones históricas. No produce figuras ni modifica el manuscrito. `main.py` conserva su comportamiento histórico; la entrada reproducible para el período completo es `run_full_period.py`.

## Reproducción

Desde la raíz, con numpy, pandas, scipy, pvlib, xarray y un backend NetCDF:

```sh
python analysis/ta_full_period/audit_inputs.py --out analysis/ta_full_period/runs/audit_NUEVO
python analysis/ta_full_period/run_full_period.py \
  --audit analysis/ta_full_period/runs/audit_NUEVO \
  --out outputs/TA/full_period/corrida_NUEVA
python -m pytest -q
python -m unittest discover -s analysis/azimuth_diagnostics -p 'test_*.py'
```

Ambos directorios de salida deben ser nuevos. Entorno utilizado: `/Users/inti/conda/envs/uv-project/bin/python`. Las versiones exactas, comandos, commit, modificaciones y hashes están en los manifiestos. Los datos y las salidas de `outputs/` están ignorados por Git: no se presupone que estén respaldados. No hay descarga de datos ni commits automáticos.

Para reutilizar la auditoría existente con la hipótesis de 45° constantes:

```sh
python analysis/ta_full_period/run_full_period.py \
  --audit analysis/ta_full_period/runs/audit_20261123 \
  --clock-policy audited \
  --out outputs/TA/full_period/ta_beta45_run01
```

En Spyder, abrir `run_full_period.py` y configurar como argumentos de ejecución
`--audit /ruta/azimuth/analysis/ta_full_period/runs/audit_20261123 --clock-policy audited --out /ruta/azimuth/outputs/TA/full_period/ta_beta45_run01`.
Usar una ruta de salida nueva en cada corrida. El control `legacy_equivalence()`
de los 29 resultados históricos sigue ejecutándose antes del procesamiento.
El test `test_tilt_and_clock_boundaries` todavía espera 30° en el tramo antiguo;
queda pendiente actualizarlo, fuera del alcance de esta modificación de dos archivos.

## Decisiones de procesamiento

- Inclinación física fija de 45° durante 2015-09-05 a 2018-10-10, según la comparación independiente comunicada por el usuario: ambos canales minimizan nRMSD cerca de 45°. Se registra en `manifest.json` mediante `parameters.tilt` y `parameters.tilt_basis`. El canal sigue siendo GTI30 hasta 2016-09-26 y GTI45 desde 28/09; el 27/09 parcial se excluye como `channel_transition`. El nombre del canal no determina la inclinación.
- UTC hasta 2017-05-11; excluir el 12/05 parcial; UTC−3 fijo a partir del 13/05. Esta política `audited` es una inferencia explícita de la señal solar, no una bitácora del equipo. El argumento `--clock-policy utc` permite ejecutar el control histórico sin corregir el reloj, siempre en una salida nueva. La auditoría guarda ambos conteos de screening por archivo.
- La fecha del caso es la del máximo GTI en zona `America/Montevideo`, no la primera muestra del archivo. Se conserva el bloque de medidas original de cada archivo para no alterar el contexto de Reno–Hansen respecto de producción.
- No se rellenan huecos ni se eliminan duplicados. Los archivos con cadencia irregular quedan registrados como rechazados. Se registra también cada archivo fuera de período y cada fecha ausente.
- Se conservan ventana `(t_max−60 min, t_max+60 min]`, más de 110 minutos claros, Ineichen/Reno–Hansen, ajuste cuadrático contra ω, Spencer y hasta tres evaluaciones simultáneas de 2σ. No se aplica la máscara de cielo claro a los puntos del ajuste.
- SWC2021: Norte=0, Este negativo, Oeste positivo; ω no cambia de signo. Se elige el último índice empatado en las LUT SWC ordenadas de menor a mayor γ para reproducir el primer índice de la tabla original antes de la conversión de signos.
- Referencia LUT 2026 por mes/día, no por DOY directo de 2016. Para el 29/02 se define explícitamente la curva intermedia de ω entre 28/02 y 01/03. El manifiesto/resultado identifica esa excepción si se usa.
- Se utiliza exclusivamente la LUT TA45 SWC2021 existente, validada por hash, geometría y convención. No se genera ni sobrescribe ninguna LUT. `build_lut30()` queda como función histórica sin llamadas desde el pipeline.

## Entregables

- Auditoría: `inventory.csv`, `clock_hypotheses.csv`, hashes de documentos y archivos protegidos. `legacy_equivalence.csv` del diagnóstico inicial muestra el efecto del desempate anterior; el de la corrida final verifica su corrección.
- `screening.csv`: resultado por archivo, fecha cruda y fecha del máximo, inclinación, canal (`gti_column`), política temporal, conteo claro, control UTC, umbral >90% informativo, advertencias y motivo de rechazo. No confundir candidatos de screening con ajustes válidos.
- `azimuth_results.csv`: estimaciones válidas, canal (`gti_column`), ω* y γ en grados, GTI en W/m², coeficientes, descarte, tabla y hash. No se han podado azimuts diarios del resultado principal.
- `rows/*.csv.gz`: índice original base cero, línea CSV base uno incluyendo encabezado, timestamp crudo y con zona, irradiancias crudas, canal, cielo claro y motivo de conservación/descarte de cada fila procesada. Archivos fuera del período o de transición se excluyen a nivel de archivo y conservan su identidad/hash en el inventario.
- `summary_by_period.csv`: grupos por inclinación, año/inclinación e inclinación/zona fuente. La desviación estándar es descriptiva, no incertidumbre calibrada.
- `sensitivity_between_day_2sigma.csv`: experimento separado, inspirado en el descarte entre días de la tesis. Conserva las poblaciones temporales anteriores agrupando por canal, ahora ambas a 45°, y mantiene el mismo algoritmo de rechazo. No modifica el resultado principal ni pretende reproducir los 131 casos.
- `synthetic_lut_equivalence.csv`: control de la corrida anterior; ya no se genera al reutilizar exclusivamente LUT45.
- `manifest.json`, `working_tree.patch`: procedencia, parámetros y hashes de entradas, tablas, código y salidas; el manifiesto solo declara `complete=true` tras comprobar archivos protegidos.

La corrida inicial `outputs/TA/full_period/20261123_audited` falló en un chequeo de cadencia que suponía nanosegundos mientras pandas almacenaba microsegundos; queda preservada y marcada `INCOMPLETE.txt`. La corrida anterior verificada es `outputs/TA/full_period/20261123_verified`, con comparación por Timedelta y test de regresión de unidades. Esa corrida, `DIAGNOSIS.md` y `RESULTS.md` conservan la hipótesis anterior de dos inclinaciones; no son resultados de la nueva hipótesis de 45° constantes. No reutilizar una corrida sin `complete=true`.
