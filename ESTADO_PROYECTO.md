# VISOR DE VIDEOS

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Estado actual:** Arquitectura base consolidada y lista para comenzar
la integración funcional.

## Último commit aprobado

**SHA:** `439b9ff1c8cd81f1512c4270e7879fc49c0c7c89`

**Mensaje:** Incorporar procesamiento asíncrono de metadatos con
FFprobe.

## Última etapa aprobada

Implementación de la primera tarea reutilizable basada en la
infraestructura de trabajos en segundo plano (`TareaFFprobe`), con
pruebas automatizadas y separación entre infraestructura genérica y
lógica de videos.

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
-   Pruebas automatizadas.

### En desarrollo

Integración funcional del pipeline asíncrono del catálogo.

## Pendientes prioritarios

1.  Escaneo asíncrono.
2.  Integración SQLite asíncrona.
3.  Actualización asíncrona de la interfaz.
4.  FFmpeg asíncrono.
5.  Varias miniaturas por video.
6.  Selección inteligente de miniaturas.
7.  Barra de progreso.
8.  Caché avanzada.
9.  Optimización para miles de videos.

## Problemas abiertos

Ver `DOCUMENTO_TECNICO.md`.

Pendientes principales: - cancelación cooperativa; - integración
definitiva del ciclo de vida de tareas con la ventana; - FFmpeg continúa
siendo síncrono; - limpieza controlada de miniaturas antiguas.

## Próxima etapa

Pipeline asíncrono del catálogo:

Escaneo → FFprobe → SQLite → Señales → Interfaz

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
