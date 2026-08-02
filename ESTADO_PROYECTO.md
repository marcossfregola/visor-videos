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
ruta absoluta, la valida y la conserva en la sesión sin escanearla) y
**escaneo manual y asíncrono de la carpeta elegida desde la interfaz**
(`visor_videos.py` escanea la carpeta con `TareaEscaneo` mediante el
mismo `GestorTareas`, muestra la cantidad de videos detectados y no
modifica SQLite, no ejecuta FFprobe/FFmpeg ni genera miniaturas)
aprobadas; pendiente la integración funcional del pipeline asíncrono del
catálogo: la sincronización completa SQLite (escritura masiva con
detección de archivos, FFprobe y eliminación de registros ausentes) y el
encadenamiento del pipeline Escaneo → SQLite con registros básicos a
partir de los archivos detectados.

## Último commit aprobado

**Mensaje:** Escaneo manual y asíncrono de la carpeta seleccionada desde la interfaz

**Etapa aprobada:** Escaneo manual y asíncrono de la carpeta elegida
desde la interfaz: `visor_videos.py` agrega el botón "Escanear carpeta"
(`boton_escanear`), la etiqueta de estado (`estado_escaneo`), el
atributo `videos_detectados` y el método `iniciar_escaneo()`. El botón
queda habilitado solo con una carpeta válida y el gestor inactivo;
`iniciar_escaneo()` revalida la carpeta con `os.path.isdir`, crea una
`TareaEscaneo(carpeta)` y la ejecuta con el mismo `GestorTareas` de la
ventana. El resultado se enruta por `_escaneo_pendiente` y se muestra la
cantidad de videos detectados ("1 video detectado" / "N videos
detectados"); ante un error se conserva el último resultado exitoso. El
escaneo no escribe en SQLite, no ejecuta FFprobe/FFmpeg ni genera
miniaturas, no crea tarjetas ni recarga el catálogo, y no recorre
subcarpetas. Con suite nueva `prueba_escaneo_interfaz.py` (36 pruebas).

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Escaneo manual y asíncrono de la carpeta seleccionada desde la interfaz:
`visor_videos.py` incorpora el botón "Escanear carpeta"
(`boton_escanear`), la etiqueta de estado (`estado_escaneo`), el
atributo `videos_detectados` y el método `iniciar_escaneo()`. El botón
queda habilitado solo con una carpeta válida y el gestor inactivo;
`iniciar_escaneo()` revalida la carpeta con `os.path.isdir`, crea una
`TareaEscaneo(carpeta)` y la ejecuta con el **mismo** `GestorTareas` de
la ventana (reutilizado para la carga inicial y los escaneos sucesivos).
El resultado se enruta a `_al_resultado_escaneo` mediante el estado
interno `_escaneo_pendiente` y se muestra el conteo ("1 video
detectado" / "N videos detectados") sin crear tarjetas ni recargar el
catálogo; ante un error se muestra "No se pudo escanear la carpeta"
**preservando el último resultado exitoso**. Los controles quedan
bloqueados mientras el gestor está ocupado. **Ausencia deliberada**: el
escaneo solo cuenta los archivos de video de la carpeta elegida (sin
subcarpetas), no escribe en SQLite, no ejecuta FFprobe/FFmpeg ni genera
miniaturas. Con suite nueva `prueba_escaneo_interfaz.py` (36 pruebas,
incluido el smoke test real con escaneo simulado). Aprobada sin
observaciones. Los archivos detectados todavía no se convierten en
registros del catálogo; esa conversión y su escritura con
`TareaGuardarVideos` quedan para la próxima etapa.

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
-   Pruebas automatizadas.

### En desarrollo

Integración funcional del pipeline asíncrono del catálogo: la selección
de carpeta y el escaneo manual y asíncrono de la carpeta elegida desde
la interfaz ya existen (la ventana muestra la cantidad de videos
detectados), pero los archivos detectados todavía no se convierten en
registros del catálogo ni se escriben en SQLite; la sincronización
completa —detección de archivos, preparación de registros, FFprobe y
eliminación de registros ausentes— y el encadenamiento del pipeline
Escaneo → SQLite siguen pendientes. La carga inicial asíncrona de la
primera página del catálogo ya está integrada en la interfaz.

## Pendientes prioritarios

1.  Preparar registros básicos a partir de los archivos detectados y
    escribirlos mediante `TareaGuardarVideos` (próxima etapa limitada:
    `TareaEscaneo` → preparación de registros básicos →
    `TareaGuardarVideos`, sin ejecutar todavía FFprobe/FFmpeg ni
    miniaturas y sin eliminar registros ausentes).
2.  Sincronización SQLite asíncrona (solo existe escritura de
    colecciones preparadas con upsert; falta la escritura masiva con
    detección de archivos, FFprobe y eliminación de registros ausentes).
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
activa); - los archivos detectados por el escaneo de la interfaz
todavía no se convierten en registros del catálogo y la sincronización
completa sigue pendiente; - el enrutado de resultados del escaneo por
`_escaneo_pendiente` es suficiente para una única tarea activa y debe
revisarse si la interfaz incorpora más tipos de tarea; - el escaneo no
incluye subcarpetas; - decisión pendiente sobre si `%` y `_` como
comodines `LIKE` en la búsqueda de `listar_videos_paginado` se aceptan
como contrato; - FFmpeg continúa siendo síncrono; - siguen pendientes
progreso y cancelación; - limpieza controlada de miniaturas antiguas.

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

Preparar registros básicos a partir de los archivos detectados y
escribirlos mediante `TareaGuardarVideos`, sin ejecutar todavía FFprobe,
FFmpeg ni miniaturas y sin eliminar registros ausentes. Es un
encadenamiento limitado inicial: `TareaEscaneo` → preparación de
registros básicos → `TareaGuardarVideos`. No constituye todavía la
sincronización completa del catálogo (que además incluye FFprobe,
miniaturas y la eliminación de registros ausentes); la integración
funcional completa del pipeline asíncrono del catálogo sigue pendiente.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
