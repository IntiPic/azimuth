# Azimut2026 — template del artículo (v0.1, 2026-10-15)

**Objetivo:** empezar la redacción en inglés del paper, manteniendo el estado de análisis y las tareas de investigación separados del manuscrito publicable.

## Archivos

- `main.tex`: título, abstract, bibliografía y configuración.
- `sections/*.tex`: estructura de Introducción, Metodología, Datos, Resultados, Discusión y Conclusiones.
- `references.bib`: las seis referencias discutidas hasta ahora (4 DOI verificados, 1 tesis con Handle y 1 conferencia HAL sin DOI verificado).
- `internal_checklist.tex`: checklist de tareas dentro del PDF **solo** en modo draft.
- `TODO.md`: hoja de ruta detallada en español con prioridades, outputs y figuras.
- `figures/`: espacio para figuras finales y datos gráficos.

## Uso con Overleaf

1. Subir el ZIP como proyecto nuevo (Upload Project), o copiar todos los archivos.
2. Seleccionar `main.tex` como archivo principal y compilador pdfLaTeX.
3. Compilar. Bibliografía con BibTeX (Overleaf la ejecuta automáticamente en la mayoría de proyectos).
4. Editar `sections/`, reemplazar figuras de ejemplo y completar referencias adicionales.
5. Cambiar `\\drafttrue` a `\\draftfalse` en `main.tex` para ocultar notas y apéndice interno.

## Uso local

`latexmk -pdf -interaction=nonstopmode main.tex`

## Limitaciones intencionales

- **No hay resultados simulados o inventados.** Las métricas y tablas están vacías.
- El formato es clase `article`, neutral, para escritura temprana: adaptar al template editorial definitivo antes del envío.
- Verificar las convenciones angulares y las ecuaciones contra la implementación ACTUAL en Azimut2026.
- El DOI del SWC2021 pertenece al paper cuyo PDF se titula *Surface azimuth estimation from solar irradiance on tilted surfaces*; la página de ISES le asigna un título diferente.
- Barbier 2019 está identificado mediante HAL `hal-02291410`; no se asignó DOI por falta de verificación.

## Referencias base

- Piccioli et al. 2021: https://doi.org/10.18086/swc.2021.39.02
- Piccioli Artecona 2022, tesis: https://hdl.handle.net/20.500.12008/35834
- Barbier et al. 2019: https://hal.science/hal-02291410
- Meng et al. 2020: https://doi.org/10.1016/j.solener.2020.09.077
- Menyhart et al. 2015: https://doi.org/10.1016/j.solener.2015.06.033
- Urraca et al. 2017: https://doi.org/10.1016/j.rse.2017.07.013
