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
ventana) y **selección de carpeta desde la interfaz** (`visor_videos.py`
permite elegir la carpeta de videos con `QFileDialog`, la normaliza a
ruta absoluta, la valida y la conserva en la sesión sin escanearla)
aprobadas; pendiente la integración funcional del pipeline asíncrono
del catálogo (sincronización completa SQLite con detección de archivos
y eliminación de registros ausentes; el pipeline Escaneo → SQLite aún
no está encadenado; la selección de carpeta existe pero todavía no
inicia el escaneo real de la carpeta elegida).

## Último commit aprobado

**Mensaje:** Incorporar selección de carpeta en la interfaz

**Etapa aprobada:** Selección de carpeta en la interfaz: `visor_videos.py`
agrega el botón "Seleccionar carpeta" y una etiqueta de solo lectura con
la ruta elegida, conservando la carpeta en el atributo de sesión
`carpeta_seleccionada`. `seleccionar_carpeta()` abre
`QFileDialog.getExistingDirectory`, normaliza la ruta con
`os.path.abspath`, valida que exista y sea un directorio con
`os.path.isdir`, conserva la selección anterior al cancelar y rechaza
rutas inválidas con un mensaje visible sin cerrar la ventana. La
selección no es persistente y todavía no inicia el escaneo (no se
escanea la carpeta, no se abre SQLite, no se ejecuta FFprobe/FFmpeg ni
se generan miniaturas). Con suite nueva `prueba_seleccion_carpeta.py`
(26 pruebas).

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Selección de carpeta en la interfaz: `visor_videos.py` incorpora el
botón "Seleccionar carpeta" (`boton_seleccionar_carpeta`), la etiqueta
de solo lectura con la ruta (`etiqueta_carpeta`) y el atributo de sesión
`carpeta_seleccionada`. `seleccionar_carpeta()` abre
`QFileDialog.getExistingDirectory`, normaliza la ruta elegida con
`os.path.abspath`, valida con `os.path.isdir` que exista y sea un
directorio, muestra la ruta en la interfaz y la conserva durante la
sesión; al cancelar conserva la selección anterior y ante una ruta
inválida rechaza la selección, mantiene la anterior y muestra un mensaje
visible sin cerrar la ventana. La selección **no es persistente** (vive
solo en la sesión) y **todavía no inicia el escaneo**: no se escanea la
carpeta, no se abre SQLite, no se ejecuta FFprobe/FFmpeg ni se generan
miniaturas. Con suite nueva `prueba_seleccion_carpeta.py` (26 pruebas,
incluido el smoke test real con selección simulada). Aprobada sin
observaciones. Conectar la carpeta seleccionada con `TareaEscaneo`
queda para la próxima etapa.

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
-   Pruebas automatizadas.

### En desarrollo

Integración funcional del pipeline asíncrono del catálogo: la selección
de carpeta desde la interfaz ya existe, pero el escaneo real de la
carpeta elegida y la sincronización completa del catálogo —detección de
archivos, FFprobe y eliminación de registros ausentes— siguen
pendientes; el pipeline Escaneo → SQLite aún no está encadenado. La
carga inicial asíncrona de la primera página del catálogo ya está
integrada en la interfaz.

## Pendientes prioritarios

1.  Conectar la carpeta seleccionada con `TareaEscaneo`: escanear la
    carpeta elegida y mostrar el resultado del escaneo en la interfaz
    (próxima etapa limitada).
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
`closeEvent`); - el escaneo real de carpetas y la sincronización
completa del catálogo siguen pendientes; - decisión pendiente sobre si
`%` y `_` como comodines `LIKE` en la búsqueda de
`listar_videos_paginado` se aceptan como contrato; - FFmpeg continúa
siendo síncrono; - siguen pendientes progreso y cancelación; - limpieza
controlada de miniaturas antiguas.

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

Etapa limitada: conectar la carpeta seleccionada desde la interfaz con
`TareaEscaneo`, mostrando el resultado del escaneo de la carpeta elegida
**sin modificar todavía SQLite, sin ejecutar FFprobe ni generar
miniaturas**. Se usará la infraestructura asíncrona existente
(`TareaEscaneo` y `GestorTareas`); la sincronización completa del
catálogo (FFprobe, actualización y eliminación de registros ausentes)
queda para una etapa posterior. Después de esa integración, una etapa de
infraestructura común de pruebas consolidará los helpers y
falsificaciones que las suites repiten (`Captura`/`correr`, bases
SQLite temporales, conectores de conteo de conexiones/hilos y de fallo
controlado), sin cambiar el comportamiento ni el contrato de los
módulos probados y manteniendo `escanear_videos.py` como única capa de
datos. Solo se diseñará; no se implementará todavía.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
