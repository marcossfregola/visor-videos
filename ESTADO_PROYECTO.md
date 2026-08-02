# VISOR DE VIDEOS

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Estado actual:** Arquitectura base consolidada; escaneo asíncrono
(`TareaEscaneo`) aprobado; pendiente la integración funcional del
pipeline asíncrono del catálogo.

## Último commit aprobado

**Mensaje:** Incorporar escaneo asíncrono de videos

**Etapa aprobada:** Escaneo asíncrono de videos (`TareaEscaneo`), sobre
la infraestructura reutilizable de trabajos en segundo plano, con
pruebas automatizadas.

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Implementación del escaneo asíncrono de videos (`TareaEscaneo`) sobre la
infraestructura de trabajos en segundo plano, con pruebas automatizadas
y reutilización de la lógica de escaneo existente (`escanear_videos`).

## Estado de la arquitectura

### Completado

-   Arquitectura general.
-   Git.
-   Documentación técnica.
-   Resolución centralizada de rutas.
-   Preservación de archivos.
-   Generación inicial de miniaturas.
-   Infraestructura reutilizable de trabajos.
-   Procesamiento asíncrono de FFprobe.
-   Escaneo asíncrono de videos.
-   Pruebas automatizadas.

### En desarrollo

Integración funcional del pipeline asíncrono del catálogo.

## Pendientes prioritarios

1.  Integración SQLite asíncrona.
2.  Actualización asíncrona de la interfaz.
3.  FFmpeg asíncrono.
4.  Varias miniaturas por video.
5.  Selección inteligente de miniaturas.
6.  Barra de progreso.
7.  Caché avanzada.
8.  Optimización para miles de videos.

## Problemas abiertos

Ver `DOCUMENTO_TECNICO.md`.

Pendientes principales: - cancelación cooperativa; - integración
definitiva del ciclo de vida de tareas con la ventana; - la interfaz
todavía no consume `TareaEscaneo`; - FFmpeg continúa siendo síncrono; -
siguen pendientes progreso y cancelación; - limpieza controlada de
miniaturas antiguas.

## Próxima etapa

Integración SQLite asíncrona en el pipeline del catálogo (segundo
eslabón del pipeline asíncrono).

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
