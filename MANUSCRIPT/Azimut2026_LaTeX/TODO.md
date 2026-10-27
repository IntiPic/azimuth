# Azimut2026 — hoja de ruta / lista de pendientes

Versión inicial: 15 de octubre de 2026. Este archivo es **interno**, no forma parte del artículo que se enviará a la revista.

## A. Prioridad 1: base experimental y ajuste diario

- [ ] **A1. Inventario reproducible:** generar tabla maestra con fecha, orientación nominal, inclinación, período estable, instrumento, resolución y muestras disponibles. **Salida:** `campaign_inventory.csv`. **Paper:** 3.1, Tabla 1.
- [ ] **A2. Referencia independiente:** reconstruir cómo se midieron o impusieron azimut y tilt; cuantificar incertidumbre absoluta/repetibilidad. Distinguir claramente `gamma_nom` de `gamma_ref`. **Paper:** 3.2.
- [ ] **A3. Traza QC completa:** por día, informar muestras crudas, filtradas, seleccionadas, rechazadas y usadas en el fit, con motivo. **Paper:** 3.3, 4.1.
- [ ] **A4. Auditar casos problemáticos** 2026-07-01, 2026-08-31 y 2026-09-17: visualizar GTI cruda, máscara, curva y residuales; repetir fit con/sin rechazos y medir `delta_omega*` y `delta_gamma`. **Paper:** 2.3–2.4, 4.1, Fig. 2.
- [ ] **A5. Congelar baseline:** tag del repositorio + versión de datos + configuración del algoritmo, previo a nuevas reglas. **Salida:** resultados base que puedan reproducirse.

## B. Prioridad 1: exactitud e incertidumbre

- [ ] **B1. Estadísticas por orientación:** error azimutal, sesgo, MAE y RMSE. Tratar períodos/orientaciones como unidades experimentales y los días como repeticiones, sin pseudorreplicación. **Paper:** 4.2, Fig. 3.
- [ ] **B2. Indicadores de calidad:** RMSE GTI (con unidades), fracción de descartes, curvatura, asimetría, cobertura alrededor del máximo y residuales autocorrelacionados. **Paper:** 2.4, 4.3.
- [ ] **B3. Propagación de incertidumbre:** covarianza del ajuste para `omega*`; derivada local de conversión a `gamma`; separar incertidumbre formal de fuentes sistemáticas. **Paper:** 2.5.
- [ ] **B4. Incertidumbre empírica:** bootstrap temporal por bloques o método equivalente; comparar con variación entre días. **Paper:** 4.3.
- [ ] **B5. Calibración:** comprobar cobertura de intervalos nominales y relación de los indicadores con errores reales. No elegir cortes optimizados sobre el mismo conjunto de validación. **Paper:** 4.3, Fig. 4.

## C. Prioridad 2: estimación multidiaria y sensibilidad

- [ ] **C1. Agregación:** comparar mediana, estimador robusto y promedio ponderado en períodos de orientación estable. **Paper:** 2.6, 4.4.
- [ ] **C2. Convergencia:** error/dispersión versus cantidad de días claros, con submuestreos repetidos sin mezclar cambios de orientación. **Paper:** 4.4, Fig. 5.
- [ ] **C3. Perturbaciones:** `tilt ±1/2/5°`, timestamp desplazado, ruido, gaps, resolución 1/5/10/15 min, ventana del fit. Ajustar rangos a viabilidad real. **Paper:** 4.5 / Supplement.
- [ ] **C4. Sensibilidad modelo:** verificar dependencia del mapeo `omega* -> gamma` con atmósfera, albedo y transposición; documentar método *realmente usado* en el repositorio. **Paper:** 2.2, 4.5.
- [ ] **C5. Robustez fuera de muestra:** fijar criterios usando desarrollo y testear sobre días/períodos distintos. **Paper:** 2.7.

## D. Prioridad 2: estaciones históricas / tesis

- [ ] **D1. Recuperar estaciones:** localizar datos y scripts de la tesis 2022 y seleccionar casos con desalineaciones y potenciales cambios de orientación. **Paper:** 3.4, 4.6.
- [ ] **D2. Evidencia externa:** registrar si hay inspecciones, metadatos o intervenciones que corroboren la desalineación. No usar mejora de RMSD como prueba directa del azimut verdadero. **Paper:** 4.6.
- [ ] **D3. Series temporales:** estimación `gamma(t)` con incertidumbre y ventanas estables; comparar con eventos documentados si existen. **Paper:** 4.6, Fig. 6.
- [ ] **D4. Impacto en transposición:** nominal vs estimado, varios modelos, MBD/RMSD y período separado para evaluación. **Paper:** 4.7, Tabla 2.

## E. Redacción y reproducibilidad

- [ ] **E1. Estado del arte actualizado:** completar bibliografía >2021 sobre inferencia de orientación y QC radiométrico.
- [ ] **E2. Introducción:** motivación -> literatura -> gap -> objetivos (sin presentar PA como método totalmente nuevo).
- [ ] **E3. Methods:** parametrizar ecuaciones y umbrales contra código; explicitar convención azimutal y dependencias de los modelos.
- [ ] **E4. Results:** reemplazar todos los placeholders por figuras reales y tablas, con métricas y número de muestras.
- [ ] **E5. Discussion:** límites físicos, timestamp/tilt, curvatura pequeña y confusores instrumentales; distinguir `azimut efectivo` de `verdad física`.
- [ ] **E6. Research artifacts:** publicar versión rastreable del código, config, estructura de datos y documentación de disponibilidad.
- [ ] **E7. Preparación editorial:** acordar coautores, contribuciones, revista, formato de envío, límites de longitud, supplementary y declaración de datos.

## Decisiones metodológicas abiertas (resolver antes de redactar resultados)

1. ¿Cuál es la precisión de referencia para cada orientación impuesta, y qué es realmente `gamma_ref`?
2. ¿Qué mapeo diario `omega* -> gamma` usa el código ACTUAL? ¿LUT, fit tangente u otro?
3. ¿El filtro de cielo claro es enteramente reproducible, y requiere GHI independiente?
4. ¿La función cuadrática se usa para todos los azimuts o necesita un dominio de aplicabilidad?
5. ¿Qué criterio impide confundir timestamp offset / tilt con azimut?
6. ¿Cuántos días y orientaciones verdaderamente independientes incluye la campaña?
7. ¿Qué resultados de tesis son reutilizables sin necesidad de campañas/afirmaciones no verificadas?

## Figuras previstas

- Fig. 1: geometría y montaje.
- Fig. 2: GTI fits buenos y difíciles.
- Fig. 3: azimut estimado vs referencia.
- Fig. 4: errores / incertidumbre / calibración de cobertura.
- Fig. 5: agregación multidiaria y sensibilidad.
- Fig. 6: estación(es) histórica(s) y cambios detectados.
- Tabla 1: inventario experimental.
- Tabla 2: transposición nominal vs corregida.

## Recordatorios para revisores exigentes

- [ ] Claridad entre validación independiente y diagnóstico de campo.
- [ ] No seleccionar solamente días de buen resultado para reclamar exactitud.
- [ ] No usar dispersión intradiaria como incertidumbre total sin justificación.
- [ ] Diferenciar mejoras de método, implementación, QC y nuevas aplicaciones respecto de 2021/tesis.
- [ ] Publicar resultados negativos/limitaciones razonables (azimut extremo, curvas planas, errores temporales).
