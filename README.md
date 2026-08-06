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

**Beta 2** — versión congelada en fase de pruebas reales. El Centro de Navegación (Bloque de trabajo 2) está completo y aprobado.

## Distribución

Los instaladores oficiales se publican en la sección **Releases** de este repositorio.

## Licencia

Pendiente de definir.
