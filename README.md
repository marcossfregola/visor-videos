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

Desarrollo actual en **Beta 7 — "Organización y operaciones de archivos"** (rama `beta7` HEAD `6ceb3902beda633ed11cdf586a11a5b53f661053`; **B7.0–B7.13 completas y auditadas funcionalmente**; **identidad `Beta 7 - B7.13`**; **cerrada localmente** —sin commit final, sin tag `v7.0-beta`, sin push, sin publicación/prerelease y sin validación específica del instalador Beta 7, pendientes). Beta 6 permanece **cerrada y publicada** (rama `beta6` commit `7d85e94bb8b617209a155e5b1086d1d38f4784f8`; **B6.1–B6.12 completas**; **identidad `Beta 6 - B6.12`**; **tag `v6.0-beta` anotado publicado sobre `7d85e94`, `origin/beta6` alineado y GitHub Release Beta 6 prerelease sin binarios**). Suites `prueba_integracion_b612` 14/14, `prueba_reescaneo_preserva_metadatos_b612` 3/3 y `prueba_derivados_b611` 15/15 de control en verde. Para el detalle del alcance completo y el estado vigente ver `ROADMAP.md` y `ESTADO_PROYECTO.md`. **Beta 7 cerrada localmente en B7.13 pero todavía no publicada como Beta 7 mientras no se complete el proceso Git/GitHub (commit/tag/push/prerelease).**

## Distribución

La publicación de instaladores en la sección **Releases** de este repositorio se
realiza **únicamente con autorización explícita** y mediante el procedimiento de
`EMPACADO.md`. Las betas recientes se mantienen **sin distribución pública de binarios**; Beta 6 cuenta con **GitHub Release `v6.0-beta` prerelease sin binarios** (tag `v6.0-beta` anotado sobre `7d85e94`, `origin/beta6` alineado); no debe asumirse que todos los instaladores generados estén
publicados (ver `ESTADO_PROYECTO.md`).

## Licencia

Pendiente de definir.
