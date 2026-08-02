# VISOR DE VIDEOS

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Estado actual:** Arquitectura base consolidada; escaneo asíncrono
(`TareaEscaneo`), lectura asíncrona del catálogo SQLite
(`TareaLecturaCatalogo`), escritura individual asíncrona
(`TareaGuardarVideo`) y escritura de colección asíncrona
(`TareaGuardarVideos`) aprobados; pendiente la integración funcional del
pipeline asíncrono del catálogo (sincronización completa SQLite con
detección de archivos y eliminación de registros ausentes; el pipeline
Escaneo → SQLite aún no está encadenado y la interfaz no consume las
tareas asíncronas).

## Último commit aprobado

**Mensaje:** Incorporar escritura asíncrona de colecciones

**Etapa aprobada:** Escritura de colección transaccional asíncrona
(`guardar_videos` / `TareaGuardarVideos`), que reutiliza la capa de
escritura transaccional con un upsert compartido en una **única
transacción atómica** (un solo `connect` y un solo `commit` por
colección, `rollback` total ante cualquier fallo, `close` siempre en
`finally`), con instantánea de la colección y de cada registro y pruebas
automatizadas. Aprobada con observaciones resueltas: contrato de
`TareaGuardarVideos` ante entradas inválidas (el constructor **nunca
lanza**; todos los errores de contrato, incluido un generador que falla
al materializarse, se comunican por la señal `error` durante la
ejecución, sin abrir SQLite ni modificar la base) y suite ampliada de 31
a 34 pruebas.

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Implementación de la escritura de colección transaccional asíncrona
(`guardar_videos` en `escanear_videos.py` + `TareaGuardarVideos` en
`tareas_videos.py`) sobre la infraestructura de trabajos en segundo
plano, con pruebas automatizadas y reutilización de la capa de escritura
transaccional existente. La escritura persiste colecciones de registros
**ya preparados** en una única transacción; la sincronización completa
del catálogo (detección de archivos, FFprobe y eliminación de registros
ausentes) sigue pendiente.

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
-   Escritura de colección asíncrona.
-   Pruebas automatizadas.

### En desarrollo

Integración funcional del pipeline asíncrono del catálogo (la
sincronización completa del catálogo —detección de archivos, FFprobe y
eliminación de registros ausentes— sigue pendiente; el pipeline
Escaneo → SQLite aún no está encadenado y la interfaz no consume las
tareas asíncronas).

## Pendientes prioritarios

1.  Sincronización SQLite asíncrona (solo existe escritura de
    colecciones preparadas con upsert; falta la escritura masiva con
    detección de archivos, FFprobe y eliminación de registros ausentes).
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

## Deuda técnica

-   Crecimiento y duplicación de infraestructura entre las suites de
    prueba: cada suite (`prueba_escaneo.py`, `prueba_lectura.py`,
    `prueba_guardar.py`, `prueba_guardar_videos.py`, etc.) define sus
    propios helpers y versiones de conectores/falsificaciones
    (`ConectorConHilo`, `ConectorConFallo`, `Captura`, `correr`, bases
    temporales) en lugar de reutilizar una infraestructura común.
-   El patrón repetido de construir una base temporal + ejecutar con
    `GestorTareas`/`QThread` + verificar eventos/`error`/hilos se
    duplica en cada nueva suite.

## Próxima etapa

Diseñar una etapa **limitada** de infraestructura común de pruebas: una
primera consolidación de los helpers y falsificaciones que las suites
repiten (`Captura`/`correr`, construcción de bases SQLite temporales,
conectores de conteo de conexiones/hilos y de fallo controlado),
sin cambiar el comportamiento ni el contrato de los módulos probados y
manteniendo `escanear_videos.py` como única capa de datos. Solo se
diseñará; no se implementará todavía.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
