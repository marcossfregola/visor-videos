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
miniaturas → guardado** (`TareaEscaneo` → `TareaFFprobe` →
`combinar_registros_con_ffprobe` → `TareaMiniaturas` →
`combinar_registros_con_miniaturas` → `TareaGuardarVideos`, encadenado
desde la interfaz con el mismo gestor; los archivos detectados se
guardan en SQLite con metadatos FFprobe (duración, resolución, codec;
`NULL` ante vacíos/incompletos/fallos individuales) y cantidad de
miniaturas por video mediante el upsert transaccional existente,
conservando los registros preexistentes) aprobadas; pendiente la
integración funcional completa del catálogo: la sincronización completa
SQLite (escritura masiva con detección de archivos y eliminación de
registros ausentes).

## Último commit aprobado

**Mensaje:** Integrar generación de miniaturas en el pipeline del catálogo

**Etapa aprobada:** Pipeline escaneo → FFprobe → miniaturas → guardado:
la interfaz encadena `TareaEscaneo` → `TareaFFprobe` → `TareaMiniaturas`
→ combinación de registros (`combinar_registros_con_ffprobe` +
`combinar_registros_con_miniaturas` en `escanear_videos.py`) →
`TareaGuardarVideos` como tareas sucesivas con el mismo `GestorTareas`
(el paso siguiente se lanza al recibir `tarea_finalizada` de la tarea
anterior). Los registros se preparan con las claves básicas `{nombre,
ruta, extension, fecha_importacion}` (ruta absoluta), los metadatos
FFprobe `{duracion_segundos, ancho, alto, codec_video}` (`NULL` ante
vacíos, incompletos o fallos individuales) y `cantidad_miniaturas`
(asignada por ruta normalizada desde el resultado de `TareaMiniaturas`) y
se escriben en SQLite mediante el upsert transaccional existente,
conservando los registros preexistentes. La generación de miniaturas
ocurre en la capa de catálogo (`asegurar_miniaturas`) y corre en segundo
plano dentro de `TareaMiniaturas`; la interfaz no ejecuta FFmpeg. Ante un
error de cualquier etapa el gestor queda `inactivo` y un nuevo escaneo es
posible. Alcance limitado: sin selección inteligente, sin múltiples
miniaturas, sin limpieza de miniaturas antiguas, sin eliminación de
registros ausentes, sin recarga del catálogo y sin subcarpetas; no es la
sincronización completa. Con suite `prueba_escaneo_guardado.py` ampliada
a 24 pruebas y `prueba_escaneo_interfaz.py` actualizada (36 pruebas).
Aprobada con observaciones.

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Pipeline `TareaEscaneo` → `TareaFFprobe` → `TareaMiniaturas` →
`combinar_registros_con_ffprobe` + `combinar_registros_con_miniaturas` →
`TareaGuardarVideos`, encadenado desde `visor_videos.py` con el **mismo**
`GestorTareas` de la ventana. `_al_resultado_escaneo` copia los archivos
detectados en `videos_detectados` y marca `_ffprobe_pendiente = True`;
al terminar el escaneo (gestor de vuelta a `inactivo`), `_al_tarea_finalizada`
inicia `TareaFFprobe` sobre las rutas absolutas de los videos detectados;
`_al_resultado_ffprobe` guarda el resultado y marca `_miniaturas_pendiente = True`;
al terminar FFprobe se inicia `TareaMiniaturas` sobre `videos_detectados`;
`_al_resultado_miniaturas` guarda el resumen y marca `_guardado_pendiente = True`;
al terminar, `_iniciar_guardado()` combina los registros con
`combinar_registros_con_ffprobe` (claves básicas `{nombre, ruta,
extension, fecha_importacion}` con ruta absoluta en la carpeta escaneada
+ metadatos FFprobe `{duracion_segundos, ancho, alto, codec_video}`;
`NULL` si el video no tiene `datos`) y luego con
`combinar_registros_con_miniaturas` (`cantidad_miniaturas` por ruta
normalizada desde el resultado de `TareaMiniaturas`) y los persiste con
`TareaGuardarVideos`. La generación de miniaturas vive en
`asegurar_miniaturas` (`escanear_videos.py`, capa de catálogo) y corre en
segundo plano dentro de la tarea; la interfaz no ejecuta FFmpeg. La
escritura real usa el upsert transaccional existente (`guardar_videos`),
conserva los registros preexistentes, no elimina registros ausentes y no
recarga tarjetas; ante un error de guardado se muestra "No se pudieron
guardar los videos", ante un error global de FFprobe "No se pudieron
obtener los metadatos" y ante un error de miniaturas "No se pudieron
generar las miniaturas"; en todos los casos la interfaz queda recuperable
con un nuevo escaneo posible. La combinación de registros y la generación
de miniaturas viven en `escanear_videos.py` (capa de catálogo);
`tareas_videos.py` re-exporta `asegurar_miniaturas` y
`combinar_registros_con_miniaturas`. `_limpiar_cadena()` limpia la cadena
sin borrar `videos_detectados` (se conserva el último escaneo exitoso
aunque falle cualquier etapa). **Ausencia deliberada**: sin selección
inteligente, sin múltiples miniaturas, sin limpieza de miniaturas
antiguas, sin eliminación de ausentes, sin recarga automática de la
interfaz y sin subcarpetas; **no es la sincronización completa del
catálogo**. Con suite `prueba_escaneo_guardado.py` ampliada a 24 pruebas
y `prueba_escaneo_interfaz.py` (36 pruebas, incluido el smoke test real
con base SQLite temporal creada por `conectar_bd(ruta_db)` y FFmpeg real
con carpeta temporal de miniaturas). Aprobada con observaciones.

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
-   Generación asíncrona de miniaturas integrada en el pipeline
    (escaneo → FFprobe → miniaturas → guardado; `TareaMiniaturas` en
    segundo plano con el mismo gestor; `cantidad_miniaturas` persistida).
-   Pruebas automatizadas.

### En desarrollo

Integración funcional completa del catálogo: el pipeline (`TareaEscaneo`
→ `TareaFFprobe` → `combinar_registros_con_ffprobe` → `TareaMiniaturas`
→ `combinar_registros_con_miniaturas` → `TareaGuardarVideos`) ya
convierte los archivos detectados por la interfaz en registros con
metadatos FFprobe y cantidad de miniaturas y los escribe en SQLite
conservando los preexistentes, pero la **sincronización completa** —la
escritura masiva con detección de archivos y la eliminación de registros
ausentes— sigue pendiente. La carga inicial asíncrona de la primera
página del catálogo ya está integrada en la interfaz.

## Pendientes prioritarios

1.  Sincronización completa SQLite asíncrona (el pipeline ya escribe
    registros con metadatos FFprobe y miniaturas mediante el upsert
    existente; falta la escritura masiva con detección de archivos y la
    eliminación de registros ausentes).
2.  Integración SQLite asíncrona en el pipeline (encadenado).
3.  Actualización asíncrona de la interfaz (tarjetas dinámicas).
4.  FFmpeg asíncrono.
5.  Varias miniaturas por video.
6.  Selección inteligente de miniaturas.
7.  Barra de progreso.
8.  Caché avanzada.
9.  Optimización para miles de videos.

## Problemas abiertos

Ver `DOCUMENTO_TECNICO.md`.

Pendientes principales: - cancelación cooperativa; - integración
definitiva del ciclo de vida de tareas con la ventana (la carga inicial
asíncrona ya usa `GestorTareas` y cierra de forma ordenada en
`closeEvent`, aunque `closeEvent` puede esperar hasta 5 s por una tarea
activa); - el pipeline ya convierte los archivos detectados en registros
con metadatos FFprobe y miniaturas y los escribe, pero la sincronización
completa sigue pendiente (escritura masiva con detección de archivos y
eliminación de registros ausentes); - el enrutado de resultados por
`_escaneo_pendiente`/`_ffprobe_pendiente`/`_miniaturas_pendiente`/
`_guardado_pendiente` es suficiente para una única tarea activa y debe
revisarse si la interfaz incorpora más tipos de tarea; - el escaneo no
incluye subcarpetas; - decisión pendiente sobre si `%` y `_` como
comodines `LIKE` en la búsqueda de `listar_videos_paginado` se aceptan
como contrato; - la generación de miniaturas corre en segundo plano
dentro de `TareaMiniaturas` (FFmpeg ya no se ejecuta en el hilo
principal, aunque la extracción de fotograma sigue siendo una llamada
síncrona dentro de la tarea); - siguen pendientes progreso y cancelación; -
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

**Sincronización completa del catálogo** (escritura masiva con detección
de archivos y eliminación de registros ausentes). La etapa anterior
(escaneo → FFprobe → miniaturas → guardado, encadenado desde la
interfaz) quedó aprobada y commiteada; la sincronización completa sigue
pendiente y se abordará como próxima etapa, manteniendo el alcance
limitado: sin selección inteligente, sin múltiples miniaturas, sin
eliminación de archivos antiguos y sin recarga automática de la
interfaz.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
