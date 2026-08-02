# VISOR DE VIDEOS

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Estado actual:** Arquitectura base consolidada; escaneo asíncrono
(`TareaEscaneo`) y lectura asíncrona del catálogo SQLite
(`TareaLecturaCatalogo`) aprobados; pendiente la integración funcional
del pipeline asíncrono del catálogo (escritura/sincronización SQLite
asíncronas).

## Último commit aprobado

**Mensaje:** Incorporar lectura asíncrona del catálogo

**Etapa aprobada:** Lectura asíncrona del catálogo SQLite
(`TareaLecturaCatalogo`), que reutiliza la capa de lectura síncrona
(`listar_videos`) con conexión SQLite por hilo, validación previa de
existencia de la base (una lectura nunca crea archivos) y pruebas
automatizadas. Aprobada con observaciones resueltas: comportamiento
definido y verificado ante bases inexistentes (archivo o directorio
padre) mediante `FileNotFoundError` sin creación de archivos.

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Implementación de la lectura asíncrona del catálogo SQLite
(`TareaLecturaCatalogo`) sobre la infraestructura de trabajos en segundo
plano, con pruebas automatizadas y reutilización de la capa de lectura
existente (`listar_videos`).

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
-   Lectura asíncrona del catálogo.
-   Pruebas automatizadas.

### En desarrollo

Integración funcional del pipeline asíncrono del catálogo (escritura y
sincronización SQLite asíncronas pendientes; el pipeline Escaneo →
SQLite aún no está encadenado).

## Pendientes prioritarios

1.  Escritura/sincronización SQLite asíncrona.
2.  Integración SQLite asíncrona en el pipeline (encadenado).
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
definitiva del ciclo de vida de tareas con la ventana; - la interfaz
todavía no consume las tareas asíncronas (usa la lectura síncrona); -
FFmpeg continúa siendo síncrono; - siguen pendientes progreso y
cancelación; - limpieza controlada de miniaturas antiguas.

## Próxima etapa

Escritura/sincronización SQLite asíncrona en el pipeline del catálogo
(primer paso hacia el segundo eslabón asíncrono del pipeline),
manteniendo `escanear_videos.py` como única capa de datos.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
