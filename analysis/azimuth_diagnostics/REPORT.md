# Diagnóstico de selección de puntos y ω*

Repositorio: `/Users/inti/Desktop/SolarResearch/azimuth`.
Commit examinado: `30aa6a2c4a44cc9880791cde365523e62b5f4aae` (`Cambios varios`).
Corrida de referencia: `runs/20260912_verified/`. No se modificó lógica productiva.

## Resultado principal

Las tres figuras originales se reproducen numéricamente con el código actual.
La desaparición de puntos ocurre en el rechazo iterativo de residuos, no en la
máscara de cielo claro. La asimetría visual combina una ventana centrada en el
máximo crudo, una selección desigual de puntos y variaciones reales de las señales
que una cuadrática no representa. La geometría solar ideal no explica por sí sola
las irregularidades medidas en los controles realizados.

| Fecha | Candidatos | Rechazados por 2σ | Usados | ω* base (°) | Sin rechazo (°) | Base − sin rechazo (° / min) |
|---|---:|---:|---:|---:|---:|---:|
| 2026-07-01 | 120 | 50 (41.67%) | 70 | −5.379992 | −6.045195 | +0.665203 / +2.660812 |
| 2026-08-22 | 120 | 52 (43.33%) | 68 | −10.431771 | −8.208819 | −2.222952 / −8.891808 |
| 2026-08-31 | 120 | 2 (1.67%) | 118 | −15.648935 | −15.677790 | +0.028855 / +0.115419 |

Las diferencias son sensibilidad al procedimiento, **no errores respecto de una
orientación verdadera conocida ni intervalos de confianza**.

## Cadena exacta de selección

1. `main.py` lee los archivos ya seleccionados en `data/csk/`. En estas tres fechas
   cada archivo es idéntico, byte a byte, al correspondiente de `data/all/`.
   No hay recortes de filas entre esas dos copias; no se pudo inferir un criterio
   automático para la elección de días a partir de esa carpeta.
2. `src/loader.py` selecciona columnas, trunca timestamps al minuto y localiza
   `America/Montevideo`. No elimina filas. Cada día tiene 1440 registros, cadencia
   exacta de 1 minuto tras truncar, sin duplicados ni GTI/hour angle no finitos.
3. `get_clear_sky_mask` calcula una máscara GHI; `main.py` la usa para conteo y
   gráficos, pero **no la pasa a `estimate_omega_star`**. La condición `ghi > 0`
   en `plotting.py` pertenece al gráfico diario y tampoco filtra el ajuste.
4. `estimate_omega_star` toma `t_max = gti.idxmax()` antes de limpiar. La ventana
   es `(t_max−60 min, t_max+60 min]`, con extremo izquierdo excluido y derecho
   incluido. Quedan 120 candidatos; 1320 puntos están fuera de la ventana, no
   son outliers. En julio abarca 11:26–13:25; en ambas fechas de agosto 10:30–12:29.
5. El filtro `isfinite(omega) & isfinite(gti)` no elimina ninguno en estas fechas.
   Desactivarlo produce Δω*=0 exactamente dentro de tolerancia numérica.
6. En cada iteración se ajusta grado 2, se calcula el residuo de cada sobreviviente,
   `sigma = residuals.std(ddof=1)` y se elimina **solo el mayor residuo absoluto**
   si supera `2*sigma`. Se repite ajustando de nuevo y recalculando σ.
7. `plot_omega_fit` solo grafica sobrevivientes y dibuja la parábola entre su
   menor y mayor ángulo. No muestra descartes ni la ventana inicial.

El campo `reason` de `points.csv` distingue exclusión temporal, no finitud y
rechazo iterativo. `rejected_points.csv` identifica cada fila y línea CSV original,
timestamp crudo, GTI, hour angle, iteración, residuo, σ y razón `|residuo|/σ` en
el instante de rechazo. `residuals_each_iteration.csv` permite reconstruir cada
decisión, incluyendo por qué se detuvo. Un residuo comparado con el ajuste final
no debe confundirse con el residuo que disparó la eliminación.

## 2026-07-01: una depresión coherente y rechazo en cascada

El máximo crudo ocurre a las 12:25, 866.19728 W/m²; el vértice base es
12:26:37.505, apenas 1.625 minutos después. El centro inicial no está muy alejado
del vértice final. Recentrar la misma ventana en ese vértice cambia ω* solo
−0.002432°.

Estos son **todos los timestamps truncados rechazados**, en orden temporal;
los extremos de los bloques son inclusivos:

| Hora local | Número de puntos |
|---|---:|
| 11:28 | 1 |
| 11:34 | 1 |
| 11:37–11:44 | 8 |
| 12:00 | 1 |
| 12:05–12:07 | 3 |
| 12:30 | 1 |
| 12:33–13:07 | 35 |
| **Total** | **50** |

Los 120 candidatos —incluidos los 50 rechazados— pasan la máscara de cielo claro.
El primer eliminado es la fila 768, línea CSV 770, a las 12:48, GTI
847.19944 W/m². Su residuo inicial es −10.303025 W/m² frente a un límite
±6.996102 W/m². Respecto del ajuste final su residuo alcanza −14.050461 W/m².

Inicialmente solo 6 puntos exceden 2σ. Una sola pasada los elimina y devuelve
ω*=−5.911141° con 114 puntos. La versión productiva continúa hasta 50 descartes:
σ cae de 3.498051 a 0.772939 W/m² y el umbral se estrecha de 6.996102 a
1.545878 W/m². El hueco largo 12:33–13:07 corresponde a una depresión suave
del lado posterior al máximo; luego también caen pequeños excesos y puntos de
borde que no excedían el umbral inicial.

La correlación entre residuos de GTI y GHI, tras quitar a cada señal su propia
cuadrática en los 120 candidatos, es **r=0.917731**. Esto respalda una variación
compartida de irradiancia como explicación probable del bloque, amplificada por
el rechazo adaptativo. No permite distinguir de forma concluyente nubosidad tenue,
transmisión atmosférica, sombreado compartido o respuesta instrumental. La etiqueta
de cielo claro no demuestra que GTI deba seguir una parábola exacta.

**Causa computacional confirmada:** eliminación secuencial 2σ con σ decreciente.
**Causa física probable:** variación temporal coherente de irradiancia; no está
demostrado que los 50 datos sean mediciones inválidas. El desplazamiento total
de +0.665203° es colectivo: la mayor influencia de quitar un solo punto antes
de limpiar es apenas |Δω*|=0.034662°.

## 2026-08-22: perturbaciones fuertes y ventana adelantada

El máximo crudo elegido para centrar es 1032.0088 W/m² a las 11:29. Ese mismo
punto se rechaza después: supera la cuadrática final en 42.828361 W/m². Un minuto
después, GTI cae a 587.92896 y GHI a 392.64516 W/m². A las 10:37 hay otra caída
hasta GTI=521.50524 y GHI=319.81592 W/m². Los residuos iniciales de GTI y GHI
tienen **r=0.994718**. Son episodios simultáneos compatibles con variabilidad
atmosférica/nubes o una perturbación compartida; no un efecto de cambiar el eje angular.

Se rechazan 52 puntos, incluidos bloques 10:35–10:47 y 11:15–11:41. El archivo
`rejected_intervals.csv` enumera también todos los intervalos menores. De los 120
candidatos, 81 pasan cielo claro; 15 de los rechazados también pasan esa máscara.
σ desciende de 71.029275 a 1.063331 W/m². Sin rechazo, el ajuste se desplaza
2.222952° respecto de base; quitar solo la observación de las 10:37 del ajuste
inicial ya cambia ω* en +3.272387°.

El vértice final corresponde a **12:06:16.186**, 37.270 minutos después del centro
de ventana. Quedan 47 puntos a la izquierda y 21 a la derecha. El soporte es
24.067441° por la izquierda y solo 5.682559° por la derecha: unos **96.27 frente
a 22.73 minutos**. Esto explica por qué el segmento de parábola dibujado parece
descentrado. La limpieza elimina el máximo que definió el centro, pero no vuelve
a elegir la ventana.

Recentrar en el vértice base y repetir 2σ devuelve **−10.523852°**, un cambio
de −0.092081°. Ventanas de 90, 120, 150 y 180 minutos con 2σ dan −10.284403,
−10.431771, −10.495702 y −10.521619°. La ventana desigual es real, pero su
apariencia no demuestra por sí sola un gran sesgo de ω*: con rechazo las variantes
anteriores son mucho más estables que sin él. Cambiar a 3σ da −10.944532°;
el umbral también importa.

**Causa probable:** perturbaciones reales de irradiancia determinan un máximo crudo
temprano, la ventana queda adelantada y el rechazo crea huecos. La cobertura desigual
domina la asimetría visual; el efecto cuantitativo sobre ω* depende de la limpieza.

## 2026-08-31: estructura suave que la cuadrática no reproduce

El máximo crudo es 1001.9736 W/m² a las 11:29; el vértice base se sitúa a
11:42:47.144, 13.786 minutos después. Se conservan 118/120 puntos. Solo se
eliminan las **10:55** (primero) y **10:50** (después); no hay un hueco de
limpieza que explique la forma de la nube.

Sin rechazo, ω*=−15.677790°, apenas −0.028855° respecto de base, equivalentes
a 6.93 segundos. Recentrar en el vértice produce −15.660932°, diferencia de
−0.011997°. En cambio, ampliar la ventana a 180 minutos produce −15.217495°,
y a 240 minutos −14.831144°: +0.431440° y +0.817791°, respectivamente.

La nube tiene una elevación alrededor de ω≈−20° y una depresión posterior cerca
de −16…−12°, con residuos que conservan estructura temporal. Sobre exactamente
los mismos 118 puntos, grado 3 da **−16.529029°** (Δ=−0.880094°), y grado 4
**−16.382749°** (Δ=−0.733813°). El RMSE baja de 2.216130 a 1.704966 y
1.692637 W/m², respectivamente. Esa mejora dentro de la muestra no prueba que
los máximos de grado superior sean más cercanos al máximo físico buscado.

La correlación de residuos iniciales GTI/GHI es **r=0.931438**. La diferencia
media absoluta entre pares crudos a ±1…60 minutos del vértice es 2.009718 W/m²,
aproximadamente 0.20% de la GTI máxima. Parte de esos pares usa datos fuera de
la ventana de fit; es un diagnóstico de la señal, no una prueba independiente
del ajuste. La cobertura usada es 71 puntos a izquierda y 47 a derecha,
con extensiones de 72.79 y 46.21 minutos.

**Causa probable:** variación suave compartida en las señales más el error de
aproximar esa forma mediante grado 2, sobre soporte desigual. Los dos outliers
tienen influencia pequeña; corregir únicamente el centro no elimina la estructura.

## Sensibilidad resumida

ω* en grados. Las variantes mantienen el resto de las elecciones base salvo
lo indicado. En el CSV completo cada fila incluye número de puntos, diferencias,
coeficientes y controles de validez.

| Variante | 01/07 | 22/08 | 31/08 |
|---|---:|---:|---:|
| Base: 120 min, grado 2, 2σ iterativo | −5.379992 | −10.431771 | −15.648935 |
| Sin rechazo | −6.045195 | −8.208819 | −15.677790 |
| Una pasada 2σ | −5.911141 | −10.639216 | −15.657888 |
| 2.5σ iterativo | −5.853451 | −10.739676 | −15.659470 |
| 3σ iterativo | −6.045195 | −10.944532 | −15.677790 |
| 4σ iterativo | −6.045195 | −11.884161 | −15.677790 |
| Ventana 60 min, 2σ | −7.324865 | −11.358019 | −17.010752 |
| Ventana 90 min, 2σ | −6.362555 | −10.284403 | −15.905074 |
| Ventana 150 min, 2σ | −5.318099 | −10.495702 | −15.492027 |
| Ventana 180 min, 2σ | −5.405125 | −10.521619 | −15.217495 |
| Ventana 240 min, 2σ | −5.404032 | −10.260774 | −14.831144 |
| 120 min centrados en vértice base, 2σ | −5.382424 | −10.523852 | −15.660932 |
| Aplicar máscara cielo claro + 2σ (experimental) | −5.379992 | −10.438413 | −15.648935 |
| Sin ventana, todo el día, sin rechazo¹ | −9.195962 | −9.323843 | −9.043767 |

¹ Incluye la noche y no representa un ajuste local del máximo; solo cuantifica
la ablación completa del criterio temporal. No es un estimador recomendado.

El ensayo 1.5σ deja solo 11, 5 y 10 puntos, respectivamente. En 22/8 activa
además una condición de salida con coeficientes desactualizados respecto de los
5 puntos finales; está marcado `stale_coefficients=True` y no se considera un
resultado científicamente utilizable. Esto ilustra por qué no se debe escoger
el umbral por el menor RMSE de los sobrevivientes.

## Hour angle, geometría solar y representación

`pvlib.solarposition.hour_angle` recibe tiempos localizados y devuelve grados,
con cero en mediodía solar. El código utiliza longitud negativa al oeste y
Spencer para la ecuación del tiempo, constante por día. Así, en estas fechas,
el eje angular es una transformación afín del tiempo con paso **0.25°/min**:
no deforma un lado respecto del otro. Se verificó también con un control numérico
que trasladar el eje preserva la selección y traslada el vértice en igual cantidad.
No se verificó externamente la configuración del reloj del datalogger; los CSV
por sí solos no prueban su zona física. [Documentación de pvlib](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.solarposition.hour_angle.html).

Cambiar solo a la ecuación del tiempo SPA produce desplazamientos de
**−0.109830°, +0.113536° y +0.107148°**, conservando en las tres fechas los
mismos puntos retenidos. Dentro de cada ventana la diferencia SPA−Spencer varía
solo 0.003938°, 0.005318° y 0.006504°. Es principalmente una traslación, no la
causa de las formas visibles. La tabla anual sí fue construida usando SPA:
esta inconsistencia merece un estudio de calibración, separado de la asimetría.
[Implementación oficial de ambas fórmulas](https://pvlib-python.readthedocs.io/en/stable/_modules/pvlib/solarposition.html).

Manteniendo los mismos puntos, no truncar los timestamps cambia ω* alrededor
de +0.0011° en las tres fechas. Si además se vuelve a aplicar la ventana con
timestamps fraccionarios, el 22/8 cambia +0.025861° por la selección en los
límites. Incluir ambos extremos del minuto cambia ω* en +0.004134°, +0.024786°
y −0.000312°: el convenio de límites existe, pero no explica la asimetría grande.

La identidad `p(ω)=p(ω*)+a(ω−ω*)²` confirma que **una cuadrática es exactamente
simétrica alrededor de su vértice**, aunque se dibuje un segmento desigual. Un
test con parábola exacta, ventana asimétrica y huecos recupera su vértice sin
sesgo. El riesgo surge cuando los datos no siguen exactamente ese modelo y el
muestreo da más peso a un lado.

Los controles sintéticos Perez–Driesse usan inclinación 35°, albedo 0.25 y
coordenadas de la tabla; se evalúan orientación norte y la orientación obtenida
de la propia tabla para cada ω* base (13.3°, 23.5° y 36.4°). Esta última elección
es dependiente del estimador y **no valida el azimut verdadero**. El máximo de
referencia se busca cada 10 segundos, paso angular 0.041667°.

Con esos últimos controles y exactamente los timestamps retenidos en cada fecha,
el RMSE de aproximar el modelo solar por una cuadrática es **0.066646, 0.052194
y 0.123299 W/m²**, frente a **0.767398, 1.055483 y 2.216130 W/m²** medidos.
Los desplazamientos del vértice sintético respecto de su propio máximo son
+0.064060°, −0.022673° y +0.061951°. Bajo estas hipótesis, la geometría ideal
aporta una desviación pequeña y no reproduce las perturbaciones de los datos.
Los modelos climatológicos no permiten excluir toda posible contribución atmosférica.

Además, aplicar 2σ iterativo a los controles suaves sin ruido elimina **97–100
de 120 puntos**. La regla también puede perseguir diferencias suaves entre el
modelo solar y una parábola hasta dejar σ casi nulo. El número de rechazados
por sí solo no mide calidad instrumental ni fracción nubosa.

## Recomendaciones: solo diagnóstico

- Conservar el algoritmo actual mientras se define qué máximo físico se pretende
  estimar: máximo observado, máximo de una envolvente de cielo claro o máximo
  de un modelo bajo condiciones atmosféricas especificadas.
- Usar estos gráficos con descartes y registrar todos los motivos/iteraciones;
  presentar ω* junto con ventana, centro, fracción rechazada y soporte a ambos lados.
- Revisar el bloque 12:33–13:07 del 1/7 y los episodios simultáneos GHI/GTI del
  22/8 con registros meteorológicos/instrumentales, si existen.
- Ampliar la comparación a días de control y orientación conocida antes de
  interpretar variaciones diarias de ω* como cambios del azimut.
- No interpretar el RMSE final reducido, una figura más simétrica ni una máscara
  de cielo claro como evidencia suficiente para cambiar el método.

## Recomendaciones: cambio metodológico sugerido, no aplicado

- Evaluar un centro obtenido después de identificar perturbaciones, con cobertura
  mínima a ambos lados. La evidencia apoya probarlo, pero no garantiza que recentrar
  solo mejore ω*; en estas fechas el cambio aislado es pequeño.
- Comparar rechazo acotado o regresión robusta con un piso de escala ligado al
  ruido instrumental, y ensayar límites de descarte. Evitar reducir σ indefinidamente
  para forzar una parábola. Calibrar parámetros con señales y orientaciones conocidas.
- Comparar grado 2 con un modelo físico local y validación fuera de muestra.
  Grados 3/4 son aquí diagnósticos de dependencia del modelo, no reemplazos aprobados.
- Unificar y validar la ecuación del tiempo usada por estimador y tabla, incluyendo
  resolución temporal de la tabla, convención angular y efecto en azimut.
- Corregir en una modificación independiente el caso `<6` para que los coeficientes
  y puntos correspondan, y declarar fallo si no hay soporte, concavidad o máximo
  interior adecuados. No afecta las tres corridas base; sí el ensayo 1.5σ del 22/8.

## Archivos y comprobaciones

Añadidos en el repositorio: `AGENTS.md`; `analysis/azimuth_diagnostics/README.md`,
`REPORT.md`, `run_diagnostics.py`, `test_diagnostics.py` y
`analysis/azimuth_diagnostics/runs/20260912_verified/` con tablas, manifiesto y
cuatro gráficos por fecha. Los gráficos y CSV originales se preservan.
Ningún archivo productivo existente fue modificado.

Verificaciones: equivalencia con producción en las tres fechas; partición completa
de las 1440 filas por etapa; reproducción de cada rechazo con su umbral;
controles numéricos de simetría exacta e invariancia angular; hashes de código,
datos y salidas; inspección visual de gráficos. Las tres pruebas unitarias pasan.
El análisis utiliza exclusivamente los tres días pedidos y controles sintéticos;
no determina por sí solo una nueva metodología ni la orientación verdadera.
