# Resultados del procesamiento completo de TA

Se procesó el período solicitado 2015-09-05 a 2018-10-10 con el criterio actual, la inclinación correspondiente a cada tramo y convención SWC2021 (Este negativo, Oeste positivo). La corrida completa `outputs/TA/full_period/20261123_verified` contiene **154 candidatos y 154 ajustes válidos**. El primer día retenido es 2015-09-12; el último, 2018-10-10. El diagnóstico previo y su evidencia están en [DIAGNOSIS.md](DIAGNOSIS.md).

Los resultados posteriores al 12/05/2017 dependen de la interpretación **UTC−3 inferida de la señal solar**. No se encontró una bitácora local que confirme ese cambio. Se registró esta condición en el manifiesto y en cada resultado; el día de transición se excluyó. La consulta al usuario no se toma como confirmación si no hay respuesta.

## Resultados por inclinación y período

Todos los ángulos están en grados. SD es la desviación estándar muestral entre días, no una incertidumbre calibrada de orientación.

| Fechas retenidas | Tilt | N | Media γ | SD γ | Media ω* |
|---|---:|---:|---:|---:|---:|
| 2015-09-12 a 2016-09-26 | 30° | 35 | +20,500 | 4,222 | +7,961 |
| 2016-10-02 a 2018-10-10 | 45° | 119 | +14,011 | 1,808 | +7,973 |
| 2016-10-02 a 2017-05-07, tramo histórico UTC | 45° | 29 | +13,934 | 1,073 | +8,310 |
| 2017-06-10 a 2018-10-10, UTC−3 inferido | 45° | 90 | +14,036 | 1,993 | +7,864 |

| Año | Tilt | N | Media γ | SD γ |
|---|---:|---:|---:|---:|
| 2015 | 30° | 8 | +20,263 | 1,269 |
| 2016 | 30° | 27 | +20,570 | 4,781 |
| 2016 | 45° | 11 | +13,955 | 0,980 |
| 2017 | 45° | 62 | +13,610 | 1,886 |
| 2018 | 45° | 46 | +14,565 | 1,732 |

Los 29 casos históricos se recuperan dentro de la nueva corrida, con diferencia máxima 1,78×10⁻¹⁵° en ω* y γ respecto del CSV preservado convertido a SWC2021, y sin diferencias en porcentaje de descarte, número de pasadas o motivo de parada. El desempate explícito corrige el desplazamiento artificial de 0,3°–0,4° detectado al invertir el orden de la LUT.

## Descomposición de la diferencia de cobertura

1. El pipeline histórico excluía el tramo de 30°. Usando su mismo umbral y la LUT adecuada se agregan **35 casos**.
2. Interpretar todos los timestamps como UTC permite solo **64 candidatos** en el período completo: los 35 de 30° y los 29 conocidos de 45°.
3. Interpretar UTC−3 desde 13/05/2017 agrega **90 casos**, todos a 45°. El total pasa de 64 a 154. No había un filtro de fecha final en mayo de 2017; el reloj desplazado impedía que los días siguientes superaran el detector.
4. La tesis usó **154 días inicialmente seleccionados y 131 después de descartar 23 azimuts diarios**. El pipeline actual no aplica ese segundo descarte. La coincidencia entre los dos totales iniciales de 154 no demuestra identidad de días o reproducción metodológica.
5. El umbral de tesis (>90%) aplicado aisladamente a las máscaras actuales daría **162 candidatos** (38 a 30° y 124 a 45°), frente a 154 con >110 minutos (35 y 119). Es una sensibilidad de selección; esos ocho casos adicionales no forman parte del resultado principal. El 05/09/2015, primer día de la tabla de tesis, tiene aquí 109 minutos claros: pasa >90% y falla >110.

El inventario tiene 1346 CSV. El ledger de archivos registra 215 fuera del período, 2 días de transición excluidos, 3 archivos rechazados por duplicados/cadencia, 972 que no pasan screening y 154 estimados. Además registra como faltante el 2016-01-28. Así se cubre el período completo sin afirmar que todos los días tengan datos utilizables.

## Inclinación e interpretación científica

La LUT30 nueva y la LUT45 preservada tienen igual referencia temporal (2026), modelo Perez–Driesse, albedo 0,20 y búsqueda minutal. Cambia la inclinación; la relación entre ω* y γ cambia físicamente. Los signos son coherentes: ω*>0 y γ>0 indican Oeste.

Como control contrafactual, aplicar incorrectamente LUT45 a los mismos 35 ω* del tramo de 30° daría media +14,177° en vez de +20,500°, una diferencia de **6,323°** sin modificar ω*. El detalle se conserva en `runs/sensitivity_wrong_tilt_20261123.csv`; no se usa en los resultados. La semejanza del valor incorrecto con 14,5° no lo valida.

La tabla 3.1 de la tesis presenta TA a 45° para todo el período; los archivos antiguos dicen GTI30 y la instrucción de esta auditoría establece 30° antes del cambio. La documentación consultada no permite determinar si la tesis trató efectivamente esos datos como 45° o si el encabezado reflejaba exactamente la geometría física. El resultado de 30° queda condicionado al cronograma solicitado. No corresponde inferir una única orientación constante atravesando el cambio mecánico sin revisar su metadato instrumental.

La sensibilidad aislada de rechazo iterativo entre azimuts diarios a 2σ, aplicada separadamente por inclinación, conserva 29 de 35 casos a 30° (media +20,397°, SD 1,332°) y 94 de 119 a 45° (media +13,996°, SD 0,906°). Suma 123, **no 131**, y no sustituye los 154 resultados principales. Además de la selección, la tesis difiere en ESRA/turbidez local, parametrización de la curva y convergencia del rechazo de puntos; esta corrida no afirma reproducirla.

No se cambió la ecuación del tiempo: Spencer en el ajuste medido y SPA en la geometría de la LUT, como en TA histórica. El cambio de interpretación UTC a UTC−3 desplaza el instante físico tres horas; para un mismo máximo con fecha solar sin cambio, aumenta ω en 45°. Por eso debe registrarse como corrección temporal explícita, sin confundirla con una conversión de signo angular.

## Cambios y verificación

Cambios productivos: dos parámetros opcionales en `load_gti_file` (`gti_col`, `source_tz`) y uno en `AzimuthEstimator.estimate` (`tie_break`). Sus valores predeterminados conservan el comportamiento anterior. La nueva entrada completa es `analysis/ta_full_period/run_full_period.py`; no se amplía silenciosamente la corrida de AZ ni se ejecuta el `main.py` que escribe rutas históricas.

La corrida guarda identidad/hash por archivo, 1129 ledgers con **1.621.776 filas crudas** trazables por ID y línea CSV, timestamps crudos y con zona, motivos de selección/rechazo, coeficientes y parámetros, hashes de LUT, código y datos, commit y diff local. Se verificaron los conteos de puntos retenidos y descartados contra cada ajuste y todos los hashes de salida del manifiesto. Hay un caso retenido el 29/02/2016: se identifica con `lookup_mapping=feb29_midpoint_omega_curve`, usando la curva media de ω entre 28/02 y 01/03 de la referencia no bisiesta. Es una aproximación de calendario explícita; no se inventa un día 366 ni se desplazan los DOY de marzo a diciembre.

Para ese 29/02, ω*=+7,472485° no cambia; la curva intermedia devuelve γ=+18,1°. Consultar solo 28/02 daría +18,1° y solo 01/03, +18,3°. Ese intervalo es sensibilidad al mapeo de calendario, no incertidumbre calibrada.

- `python -m pytest -q`: **23 tests y 13 subtests aprobados**.
- `python -m unittest discover -s analysis/azimuth_diagnostics -p 'test_*.py'`: **3 tests aprobados**.
- `git diff --check`: sin errores.
- Control sintético: igualdad de 1801 valores de ω por día en siete fechas estacionales para la reconstrucción de LUT45 (máxima diferencia 0); pruebas de signo físico Este/Oeste a 30° y 45°.
- Control medido: reproducción de los 29 casos históricos, sin cambio de ω ni de sus descartes.
- Conservación: **1655 archivos protegidos comprobados, cero modificados**, incluidos los resultados TA históricos, LUT existentes, manuscrito y figuras inventariadas.

Se emitieron dos advertencias del entorno durante pytest: deprecación de una API interna de pytest usada por anyio, y tamaño de `numpy.ndarray` al importar el lector NetCDF. No hubo tests fallidos; se comprobó numéricamente la lectura de LUT. Versiones: Python según manifiesto, numpy 2.4.6, pandas 3.0.3, pvlib 0.15.2, scipy 1.18.0, xarray 2026.4.0.

La primera corrida quedó incompleta por un chequeo de cadencia dependiente de la unidad interna de pandas. Se conserva marcada `INCOMPLETE.txt`; se corrigió el chequeo con Timedelta y un test que cubre segundos, milisegundos, microsegundos y nanosegundos. Solo `20261123_verified`, con `complete=true`, es el resultado entregado. No se modificaron el manuscrito ni las figuras existentes y no se realizaron commits.

## Archivos principales

- [Resultados por día](../../outputs/TA/full_period/20261123_verified/azimuth_results.csv).
- [Resumen por período](../../outputs/TA/full_period/20261123_verified/summary_by_period.csv).
- [Screening y descartes](../../outputs/TA/full_period/20261123_verified/screening.csv).
- [Manifiesto](../../outputs/TA/full_period/20261123_verified/manifest.json).
- [Verificación independiente](runs/verification_20261123.json).
- [Comandos y descripción de artefactos](README.md).

Fuentes: tesis local `docs/master_inti-piccioli.pdf`, pp. impresas 29, 55–60 y 70 (PDF 50, 76–81 y 91); artículo `docs/swc2021-0109-Piccioli.pdf`, pp. 2–6. Sus hashes se conservan en el manifiesto del diagnóstico.
