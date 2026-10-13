# Instrucciones para agentes — azimuth

- Objetivo científico: estimar el ángulo horario del máximo de irradiancia global
  inclinada (GTI), `omega_star`, y convertirlo a azimut de la superficie mediante
  la tabla solar; preservar trazabilidad y significado físico del resultado.
- Estructura: `main.py` orquesta; `src/loader.py` carga GTI/GHI y timestamps;
  `src/clearsky.py` calcula máscara de cielo claro y ajuste de ω*;
  `src/estimator.py` consulta la tabla; `src/plotting.py` dibuja;
  `lookup_table.py` genera la tabla anual; `data/all/` y `data/csk/` contienen
  entradas; `OUT/` tablas; `outputs/` y `FIG /` figuras.
- Diagnóstico aislado: `python analysis/azimuth_diagnostics/run_diagnostics.py`.
  Acepta `--repo` y `--out`; usar un directorio nuevo por corrida. Pruebas:
  `python -m unittest discover -s analysis/azimuth_diagnostics -p 'test_*.py'`.
  Ver su README y manifest para dependencias, versiones y reproducción.
- Cambios mínimos: preferir scripts/tests bajo `analysis/` o `tests/`.
  No refactorizar ni cambiar comportamiento principal para facilitar un diagnóstico.
  Antes de modificar archivos productivos, reportar hallazgos y justificación.
- Nunca borrar datos, tablas ni outputs; no sobrescribir resultados históricos.
  Evitar ejecutar `main.py` o `lookup_table.py` si no se pretende regenerar salidas.
  No asumir que los CSV ignorados por Git están respaldados.
- Convenciones: grados para ω y azimut; W/m² para irradiancia; minutos para
  ventanas; timestamps con zona explícita. Conservar ID de fila, timestamp crudo,
  motivo de descarte y parámetros. No cambiar signo/origen angular sin documentarlo.
- Reproducibilidad: registrar commit, cambios locales, hashes de código/datos,
  versiones, comandos y parámetros; verificar equivalencia con producción antes
  de comparar variantes. Separar datos medidos y controles sintéticos.
- No cambiar lógica científica sin evidencia. Documentar cualquier cambio de
  ventana, centro, outliers, ecuación del tiempo, ajuste o tabla, su efecto en ω*
  y azimut y sus limitaciones. Separar diagnóstico de propuestas metodológicas.
