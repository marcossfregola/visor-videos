# VISOR DE VIDEOS

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Estado actual:** Arquitectura base consolidada; escaneo asíncrono
(`TareaEscaneo`), lectura asíncrona del catálogo SQLite
(`TareaLecturaCatalogo`) y escritura individual asíncrona
(`TareaGuardarVideo`) aprobados; pendiente la integración funcional del
pipeline asíncrono del catálogo (escritura masiva y sincronización
SQLite asíncronas; el pipeline Escaneo → SQLite aún no está encadenado y
la interfaz no consume las tareas asíncronas).

## Último commit aprobado

**Mensaje:** Incorporar escritura individual asíncrona

**Etapa aprobada:** Escritura individual asíncrona de video
(`TareaGuardarVideo`), que reutiliza la capa de escritura transaccional
síncrona (`guardar_video`) con conexión SQLite por hilo, `commit`/
`rollback`/`close` dentro del hilo de trabajo y pruebas automatizadas.
Aprobada con observaciones resueltas: aislamiento del registro (el
constructor toma una instantánea del diccionario) y validación previa a
SQL (`TypeError`/`ValueError` antes de abrir la conexión, sin modificar
la base ni dejar conexiones abiertas).

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Implementación de la escritura individual asíncrona de video
(`TareaGuardarVideo`) sobre la infraestructura de trabajos en segundo
plano, con pruebas automatizadas y reutilización de la capa de escritura
transaccional existente (`guardar_video`). La escritura es individual
(un registro por operación): la escritura masiva y la sincronización
completa del catálogo siguen pendientes.

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
-   Escritura individual asíncrona.
-   Pruebas automatizadas.

### En desarrollo

Integración funcional del pipeline asíncrono del catálogo (escritura
masiva y sincronización SQLite asíncronas pendientes; el pipeline
Escaneo → SQLite aún no está encadenado y la interfaz no consume las
tareas asíncronas).

## Pendientes prioritarios

1.  Escritura masiva y sincronización SQLite asíncrona (solo existe
    escritura individual).
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

Diseñar una operación de sincronización **limitada** (no la
sincronización completa del catálogo): un único proceso que actualice
los metadatos de los videos existentes en la base sin ejecutar
escaneo/FFprobe/FFmpeg, manteniendo `escanear_videos.py` como única
capa de datos y la escritura individual como base. Solo se diseñará;
no se implementará todavía.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
