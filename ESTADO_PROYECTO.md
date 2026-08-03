# VISOR DE VIDEOS

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Estado actual:** Arquitectura base consolidada; escaneo asíncrono
(`TareaEscaneo`), lectura asíncrona del catálogo SQLite
(`TareaLecturaCatalogo`), **lectura paginada del catálogo SQLite**
(`TareaLecturaCatalogoPaginada` con `LIMIT`/`OFFSET`/`COUNT` en SQL),
escritura individual asíncrona (`TareaGuardarVideo`), escritura de
colección asíncrona (`TareaGuardarVideos`), **integración asíncrona de
la primera carga del catálogo en la interfaz** (`visor_videos.py`
consume `TareaLecturaCatalogoPaginada` mediante `GestorTareas` para la
primera página, con estado de carga y manejo de errores sin bloquear la
ventana), **selección de carpeta desde la interfaz** (`visor_videos.py`
permite elegir la carpeta de videos con `QFileDialog`, la normaliza a
ruta absoluta, la valida y la conserva en la sesión sin escanearla),
**escaneo manual y asíncrono de la carpeta elegida desde la interfaz**
(`visor_videos.py` escanea la carpeta con `TareaEscaneo` mediante el
mismo `GestorTareas`, muestra la cantidad de videos detectados y no
ejecuta FFmpeg ni genera miniaturas) y **pipeline escaneo → FFprobe →
guardado** (`TareaEscaneo` → `TareaFFprobe` → `combinar_registros_con_ffprobe`
→ `TareaGuardarVideos`, encadenado desde la interfaz con el mismo gestor;
los archivos detectados se guardan en SQLite con metadatos FFprobe
(duración, resolución, codec; `NULL` ante vacíos/incompletos/fallos
individuales) mediante el upsert transaccional existente, conservando
los registros preexistentes) aprobadas; pendiente la integración
funcional completa del catálogo: la sincronización completa SQLite
(escritura masiva con detección de archivos y eliminación de registros
ausentes).

## Último commit aprobado

**Mensaje:** Integrar FFprobe en el pipeline del catálogo

**Etapa aprobada:** Pipeline escaneo → FFprobe → guardado: la interfaz
encadena `TareaEscaneo` → `TareaFFprobe` → combinación de registros
(`combinar_registros_con_ffprobe` en `escanear_videos.py`) →
`TareaGuardarVideos` como tareas sucesivas con el mismo `GestorTareas`
(el paso siguiente se lanza al recibir `tarea_finalizada` de la tarea
anterior). Los registros se preparan con las claves básicas `{nombre,
ruta, extension, fecha_importacion}` (ruta absoluta) más los metadatos
FFprobe `{duracion_segundos, ancho, alto, codec_video}` (`NULL` ante
vacíos, incompletos o fallos individuales) y se escriben en SQLite
mediante el upsert transaccional existente, conservando los registros
preexistentes; ante un error de guardado o de FFprobe el gestor queda
`inactivo` y un nuevo escaneo es posible. No se ejecuta FFmpeg, no se
generan miniaturas, no se eliminan registros ausentes, no se recarga el
catálogo y no se recorren subcarpetas; no es la sincronización completa.
Con suite `prueba_escaneo_guardado.py` ampliada a 19 pruebas y
`prueba_escaneo_interfaz.py` reforzada (36 pruebas). Aprobada con
observaciones.

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Pipeline `TareaEscaneo` → `TareaFFprobe` → `combinar_registros_con_ffprobe`
→ `TareaGuardarVideos`, encadenado desde `visor_videos.py` con el **mismo**
`GestorTareas` de la ventana. `_al_resultado_escaneo` copia los archivos
detectados en `videos_detectados` y marca `_ffprobe_pendiente = True`;
al terminar el escaneo (gestor de vuelta a `inactivo`), `_al_tarea_finalizada`
inicia `TareaFFprobe` sobre las rutas absolutas de los videos detectados;
`_al_resultado_ffprobe` guarda el resultado y marca `_guardado_pendiente = True`;
al terminar FFprobe, `_iniciar_guardado()` combina los registros con
`combinar_registros_con_ffprobe` (claves básicas `{nombre, ruta,
extension, fecha_importacion}` con ruta absoluta en la carpeta escaneada
+ metadatos FFprobe `{duracion_segundos, ancho, alto, codec_video}`;
`NULL` si el video no tiene `datos`) y los persiste con
`TareaGuardarVideos`. La escritura real usa el upsert transaccional
existente (`guardar_videos`), conserva los registros preexistentes, no
elimina registros ausentes y no recarga tarjetas; ante un error de
guardado se muestra "No se pudieron guardar los videos" y ante un error
global de FFprobe "No se pudieron obtener los metadatos"; en ambos casos
la interfaz queda recuperable con un nuevo escaneo posible. La
combinación de registros vive en `escanear_videos.py` (capa de
catálogo); `tareas_videos.py` la re-exporta. `_limpiar_cadena()` limpia
la cadena sin borrar `videos_detectados` (se conserva el último escaneo
exitoso aunque falle FFprobe o el guardado). **Ausencia deliberada**: sin
FFmpeg/miniaturas, sin eliminación de ausentes, sin recarga automática
de la interfaz y sin subcarpetas; **no es la sincronización completa del
catálogo**. Con suite `prueba_escaneo_guardado.py` ampliada a 19
pruebas y `prueba_escaneo_interfaz.py` (36 pruebas, incluido el smoke
test real con base SQLite temporal creada por `conectar_bd(ruta_db)`).
Aprobada con observaciones.

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
-   Lectura paginada asíncrona del catálogo.
-   Escritura individual asíncrona.
-   Escritura de colección asíncrona.
-   Integración asíncrona de la primera carga del catálogo en la
    interfaz.
-   Selección de carpeta desde la interfaz.
-   Escaneo manual y asíncrono de la carpeta elegida desde la interfaz.
-   Pipeline escaneo → FFprobe → guardado (encadenado desde la interfaz
    con el mismo gestor; los registros se guardan con metadatos FFprobe).
-   Pruebas automatizadas.

### En desarrollo

Integración funcional completa del catálogo: el pipeline (`TareaEscaneo`
→ `TareaFFprobe` → `combinar_registros_con_ffprobe` →
`TareaGuardarVideos`) ya convierte los archivos detectados por la
interfaz en registros con metadatos FFprobe y los escribe en SQLite
conservando los preexistentes, pero la **sincronización completa** —la
escritura masiva con detección de archivos y la eliminación de registros
ausentes— sigue pendiente. La carga inicial asíncrona de la primera
página del catálogo ya está integrada en la interfaz.

## Pendientes prioritarios

1.  Sincronización completa SQLite asíncrona (el pipeline ya escribe
    registros con metadatos FFprobe mediante el upsert existente; falta
    la escritura masiva con detección de archivos y la eliminación de
    registros ausentes).
2.  Generación asíncrona de una miniatura básica por video e integración
    con el pipeline (próxima etapa limitada; sin selección inteligente,
    sin múltiples miniaturas, sin eliminación de archivos antiguos y sin
    recarga automática de la interfaz).
3.  Integración SQLite asíncrona en el pipeline (encadenado).
4.  Actualización asíncrona de la interfaz (tarjetas dinámicas).
5.  FFmpeg asíncrono.
6.  Varias miniaturas por video.
7.  Selección inteligente de miniaturas.
8.  Barra de progreso.
9.  Caché avanzada.
10. Optimización para miles de videos.

## Problemas abiertos

Ver `DOCUMENTO_TECNICO.md`.

Pendientes principales: - cancelación cooperativa; - integración
definitiva del ciclo de vida de tareas con la ventana (la carga inicial
asíncrona ya usa `GestorTareas` y cierra de forma ordenada en
`closeEvent`, aunque `closeEvent` puede esperar hasta 5 s por una tarea
activa); - el pipeline ya convierte los archivos detectados en registros
con metadatos FFprobe y los escribe, pero la sincronización completa
sigue pendiente (escritura masiva con detección de archivos y
eliminación de registros ausentes); - el enrutado de resultados por
`_escaneo_pendiente`/`_ffprobe_pendiente`/`_guardado_pendiente` es
suficiente para una única tarea activa y debe revisarse si la interfaz
incorpora más tipos de tarea; - el escaneo no incluye subcarpetas; -
decisión pendiente sobre si `%` y `_` como comodines `LIKE` en la
búsqueda de `listar_videos_paginado` se aceptan como contrato; - FFmpeg
continúa siendo síncrono; - siguen pendientes progreso y cancelación; -
limpieza controlada de miniaturas antiguas.

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

**Generación asíncrona de una miniatura básica por video e integración
con el pipeline.** La próxima etapa queda **limitada** a esa
integración: sin selección inteligente, sin múltiples miniaturas, sin
eliminación de archivos antiguos y sin recarga automática de la
interfaz. El encadenamiento `TareaEscaneo` → `TareaFFprobe` →
`combinar_registros_con_ffprobe` → `TareaGuardarVideos` ya existe como
pipeline; la sincronización completa del catálogo (que además incluye la
eliminación de registros ausentes) sigue pendiente.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
