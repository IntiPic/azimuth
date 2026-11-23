# Diagnóstico de cobertura y procesamiento de TA

Diagnóstico previo a cambios productivos, 2026-11-23. Rama `analysis/ta-full-period`, commit `9935f4e` (SHA completo en el manifiesto). No se ejecutaron `main.py` ni generadores históricos, ni se modificaron manuscrito, figuras o resultados previos. Inventario y controles: `runs/audit_20261123/`.

## Causas verificadas

Los 29 resultados no describen la disponibilidad de datos. Hay entradas hasta 2018. La reducción combina exclusión explícita del período de 30°, interpretación UTC constante de un reloj que cambia en mayo de 2017, y diferencias metodológicas respecto de la tesis. No existe un filtro explícito que termine el procesamiento el 2017-05-07: es el último día que supera el screening con el reloj mal interpretado después del cambio.

### Archivos y cobertura real

`data/TA/{2015,2016,2017,2018}/DataT/` contiene 1346 CSV y 24 temporales vacíos que el glob no selecciona. Todos los CSV se abrieron; sus hashes, extremos internos, número de filas, encabezados de GTI, orden temporal, duplicados e inválidos están en `inventory.csv`.

| Carpeta | CSV | Primer timestamp crudo | Último timestamp crudo |
|---|---:|---|---|
| 2015 | 250 | 2015-04-24 19:50:00.299 | 2015-12-31 23:59:00.304 |
| 2016 | 365 | 2016-01-01 00:00:00.358 | 2016-12-31 23:59:00.296 |
| 2017 | 365 | 2017-01-01 00:00:00.310 | 2017-12-31 23:59:00.308 |
| 2018 | 366 | 2018-01-01 00:00:00.304 | 2018-12-31 23:59:00.130 |

Estos timestamps no llevan zona; no se deben presentar directamente como UTC. La columna `TZ` contiene `n` en los ejemplos del cambio y no documenta UTC−3.

Hay 519 CSV con `GTI30_AV (W/m2)`, 750 con `GTI45_AV (W/m2)` y 77 posteriores sin GTI. La GTI termina en el archivo parcial del 2018-10-16; la presencia de archivos hasta diciembre no significa disponibilidad de GTI. El canal cambia a GTI45 el 2016-09-27, en un archivo parcial de 183 filas que comienza a las 20:53 crudas. El primer día completo GTI45 es el 28/09, compatible con la fecha de cambio suministrada por el usuario.

En el período solicitado falta el 2016-01-28. Son parciales 2015-12-20, 2016-01-29, 2016-03-22, 2016-09-27, 2017-05-12 y 2017-06-07; 2018-06-13 tiene 1439 filas. El 2016-07-26 contiene un minuto duplicado. El detector actual rechaza cadencias no uniformes en 2016-07-26, 2016-09-27, 2017-06-07 y 2018-06-13. Conservar estos descartes con motivo; no interpolar irradiancia ni borrar muestras para aumentar el número de casos.

### Restricciones del pipeline

- `src/config.py`: TA usa `valid_from=2016-09-28`, tilt fijo de 45°, columna GTI45, zona fuente UTC y una sola LUT de 45°. No incluye el tramo de 30°.
- `src/loader.py`: exige el nombre fijo del canal, convierte valores no numéricos a NaN, trunca timestamps al minuto, localiza UTC, convierte a Montevideo y ordena. No filtra fechas, no conserva por sí solo ID de fila/timestamp crudo y no usa `TZ`.
- `analysis/generate_daily_screening_TA.py`: inicio por configuración, sin final predeterminado; admite `--start/--end`. Filtra por nombre y también por la primera muestra local. Para días almacenados en UTC, la primera muestra local cae el día anterior. Por eso el screening histórico etiqueta el archivo 2016-10-02 como 2016-10-01 y el inicio excluye además el archivo del 28/09. Esa fecha no es la del máximo.
- `outputs/TA/screening/screening_summary.csv`: 746 registros que alcanzan octubre de 2018, de los que solo 29 superan estrictamente 110 minutos claros en una ventana de 120 minutos. Después del 07/05/2017 no supera el umbral ningún archivo.
- `main.py` consume la lista persistida de candidatos por nombre de archivo; no descubre nuevos candidatos ni aplica un límite final de mayo de 2017. La lista no se amplía cambiando solo el ajuste o la LUT. Sus salidas y las de screening usan rutas reutilizables que no conviene ejecutar sobre los históricos.

### Cambio de reloj

`clock_hypotheses.csv` compara para cada entrada la interpretación UTC y UTC−3 fijo, manteniendo el modelo y umbral actuales. Antes del 12/05/2017 la mediana de correlación GHI/modelo, usando GHI modelada >50 W/m², es 0,823 en UTC y 0,186 en UTC−3. Después es 0,154 en UTC y 0,830 en UTC−3. No se ajusta el reloj día por día para maximizar candidatos: se identifica una discontinuidad persistente de tres horas.

El archivo del 12/05 es parcial, empieza a las 14:40 y no pasa el screening bajo ninguna interpretación. El último día anterior completo es 11/05; a partir del 13/05 la señal favorece UTC−3. Se excluirá explícitamente el día de transición, usando UTC hasta el 11/05 y UTC−3 desde el 13/05. Es una **inferencia física de los datos**, no una modificación de reloj acreditada por una bitácora. Se conserva el escenario UTC como control, y cada resultado nuevo identificará su política temporal.

Manteniendo Reno–Hansen, Ineichen y el umbral >110, la interpretación por períodos recupera 154 candidatos entre 2015-09-12 y 2018-10-10: 8 en 2015, 38 en 2016, 62 en 2017 y 46 en 2018. La igualdad con los 154 iniciales de la tesis es numérica: no prueba que sean los mismos días ni que el método sea equivalente.

### Inclinación y tablas

Aplicar 30° desde 2015-09-05 hasta 2016-09-26 (último archivo GTI30), excluir el archivo parcial de transición del 27/09, y aplicar 45° desde 2016-09-28. No renombrar GTI30 como GTI45 ni inferir 45° de la configuración global.

La única LUT TA disponible es `lookup/TA/lookup_omega_gamma.nc` y su derivada `_swc2021.nc`, ambas para 45°, latitud −31,74°, longitud −55,98°, albedo 0,20, Perez–Driesse y referencia 2026. No existe una LUT de 30°. La tabla de 45° no sirve para el período anterior. La tabla 3.1 de la tesis (p. impresa 29, PDF 50) resume TA con 45° para todo su período; no documenta allí el tramo de 30°. Esto limita una comparación literal de su agregado con una reconstrucción que respete las dos inclinaciones.

Se generará una LUT nueva de 30° con parámetros, discretización angular 0,1° y búsqueda temporal minutal compatibles con la TA histórica. Se comprobará el generador a 45° contra la tabla preservada antes de emplearlo a 30°. No introducir resolución de 1 s ni SPA en el ajuste como parte de la ampliación: TA usa Spencer para ω* medido y su tabla usa EOT solar SPA. Esa diferencia conocida se documenta, sin armonizarla silenciosamente.

### Selección de días y diferencias con la tesis

Fuentes locales: `docs/master_inti-piccioli.pdf`, §§4.1 y 4.4 (pp. impresas 54–60 y 69–70; PDF 75–81 y 90–91); `docs/swc2021-0109-Piccioli.pdf`, pp. 2–6. Se verificaron visualmente las páginas con el criterio, descarte y tabla final.

| Paso | Tesis | Pipeline actual |
|---|---|---|
| Detector | Reno–Hansen, ventana móvil de 10 min | `pvlib.clearsky.detect_clearsky`, parámetros predeterminados |
| GHI de referencia | ESRA, turbidez Linke con ciclos locales | `Location.get_clearsky`: Ineichen, Linke climatológica de pvlib, altura por defecto |
| Selección diaria | Más de 90% en dos horas alrededor de máximo GTI | Más de 110 minutos de 120, es decir ≥111, más restrictivo que >108 |
| Ajuste | Cuadrático, rechazo simultáneo >2σ hasta no encontrar nuevos outliers | Cuadrático contra ω real, máximo tres evaluaciones de 2σ; parada registrada, no siempre convergente |
| Inversión | ESRA + Perez, parametrización `a tan(b ω*)` | Ineichen + Perez–Driesse, vecino más cercano en LUT minutal de 2026 |
| Agregación | Rechazo iterativo entre azimuts diarios a >2σ | No existe ese descarte entre días |

La tesis dice explícitamente **154 días inicialmente seleccionados, 23 descartados y 131 retenidos**, γ=+14,5°, σ=1,0° (p. impresa 60 y tabla 4.3, p. 70). Los 131 no son el número bruto de candidatos de screening. No corresponde forzar el umbral ni descartar días hasta obtener 131. Tampoco llamar incertidumbre calibrada a la desviación estándar del nuevo agregado. La aplicación exacta de ESRA y de los ciclos locales no queda reproducida por los scripts actuales; los nuevos resultados serán del pipeline actual ampliado, no una reproducción de la tesis.

### Signos y desempates

SWC2021 define Norte=0°, Este negativo y Oeste positivo en el hemisferio sur. ω es negativo antes y positivo después del mediodía solar. Para pvlib, azimut horario desde el Norte, la conversión es `surface_azimuth = (-gamma_swc2021) % 360`. No se debe negar ω al convertir γ.

Los resultados TA originales de 29 días tienen γ negativo con ω*>0. La derivada `_swc2021.csv` corrige γ por negación y preserva el resto. La media publicada convertida es positiva, hacia el Oeste. El generador configurable actual todavía usa coordenadas de la convención antigua y no se debe guardar su salida directamente bajo un nombre SWC2021.

Control con las 29 entradas históricas: ω* se reproduce con diferencia máxima 1,78e−15°. Sin embargo, la LUT minutal tiene mesetas: convertir sus coordenadas y ordenarlas invierte el orden de los candidatos empatados. `np.argmin` toma el primer índice; en la tabla convertida devuelve 0,3°–0,4° menos que la negación del resultado original. No es un cambio físico ni de ω*, sino una pérdida de equivalencia por desempate. `legacy_equivalence.csv` registra cada caso. Se necesita un desempate explícito que respete el orden original (último empate en la tabla SWC ascendente), limitado a esta ruta y documentado en resultados.

## Intervención mínima justificada

Crear un punto de entrada aislado en `analysis/ta_full_period/` para inventario, screening y ajuste sin figuras; directorio nuevo obligatorio por corrida. Reutilizar las funciones científicas existentes. Permitir al loader sobrescribir explícitamente canal y zona de origen, con valores predeterminados intactos; permitir desempate explícito en el estimador, manteniendo el predeterminado histórico. El nuevo runner seleccionará por fecha del máximo, canal/inclinación y política de reloj por períodos.

Registrar todos los archivos, faltantes y motivos de rechazo, y para cada fila procesada ID, línea CSV, timestamp crudo, timestamp con zona, canal, política temporal y estado del ajuste. Registrar commit, diferencias locales, hashes de datos, código, LUT y fuentes, parámetros y versiones. Crear LUT30 en la corrida; reutilizar LUT45 validada por hash. Comparar también el control UTC y el umbral >90% como sensibilidad identificada, sin adoptar otros cambios científicos.

Los resultados finales se informarán separados por año, inclinación y régimen horario. El agregado entre inclinaciones solo será descriptivo; no se presupone orientación idéntica antes y después del cambio mecánico. Conservar sin cambios los resultados anteriores, manuscrito y figuras. No realizar commits.
