# Visor de Videos

Visor de escritorio para Windows orientado a explorar colecciones de videos mediante miniaturas representativas y previews.

## Descripción

La aplicación permite cargar un catálogo de videos desde una o más carpetas, escanearlas y navegar visualmente por el contenido mediante tarjetas con miniatura y previews. Incluye un Centro de Navegación con el árbol del sistema de archivos ("Este equipo" → discos → carpetas), selección de carpeta, escaneo (con opciones de incluir subcarpetas y de escaneo automático al seleccionar), persistencia de preferencias, búsqueda por nombre, carga de páginas adicionales ("Cargar más") y apertura del video con la aplicación predeterminada del sistema.

## Objetivo del proyecto

Explorar de forma visual y eficiente grandes colecciones de videos, facilitando la identificación del contenido mediante miniaturas y previews sin necesidad de abrir cada archivo.

## Tecnologías utilizadas

- **Python 3.13**
- **PySide6** (Qt 6)
- **SQLite** (catálogo)
- **FFmpeg** y **FFprobe** (extracción de fotogramas y metadatos)

> Nota: FFmpeg/FFprobe no se empaquetan en el instalador; deben estar disponibles en el `PATH` del sistema.

## Estado actual

Desarrollo actual en **Beta 6 — "De marcar a conservar"** (rama `beta6`). La
**Beta 5** quedó cerrada internamente y la **Beta 6 continúa abierta**, con
**B6.1–B6.5** completadas (B6.3 commit `c28ccf6`, B6.4 commit `74bb459` en `origin/beta6`, B6.5 validada y cerrada en este commit; suites `prueba_filtro_b65` 24/24, `prueba_color_b63` 21/21, `prueba_ordenamiento_b62` 18/18, `prueba_resumen_colapsado_b64` 8/8); la próxima
etapa funcional prevista es **B6.6**. Para el detalle del alcance completo y el
estado vigente ver `ROADMAP.md` y `ESTADO_PROYECTO.md`.

## Distribución

La publicación de instaladores en la sección **Releases** de este repositorio se
realiza **únicamente con autorización explícita** y mediante el procedimiento de
`EMPACADO.md`. Las betas recientes se mantienen **sin distribución pública** ni
GitHub Release; no debe asumirse que todos los instaladores generados estén
publicados (ver `ESTADO_PROYECTO.md`).

## Licencia

Pendiente de definir.
