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
conservando los registros preexistentes), **detección no destructiva de
diferencias entre la carpeta y el catálogo SQLite** (`detectar_diferencias`
en `escanear_videos.py`: compara por nombre lo que hay en disco con lo que
hay en la base y devuelve `presentes_en_ambos`/`nuevos`/`ausentes_del_disco`;
solo lectura, no inserta, actualiza ni elimina, no está integrada al
pipeline ni a la interfaz, no detecta movimientos ni renombrados y no
recorre subcarpetas) y **preparación del plan de sincronización**
(`preparar_plan_sincronizacion` en `escanear_videos.py`: operación pura
que recibe el resultado de `detectar_diferencias` y devuelve
`a_incorporar` (registros básicos con `preparar_registros_basicos`; la
`fecha_importacion` se genera en la preparación, no durante la
detección)/`ya_sincronizados`/`candidatos_a_eliminar` (informativos); no
inserta, actualiza ni elimina, no accede a SQLite, no ejecuta
FFprobe/FFmpeg y no está integrada al pipeline ni a la interfaz)
aprobadas; pendiente la integración funcional completa
del catálogo: la sincronización completa SQLite (escritura masiva con
detección de archivos y la eliminación controlada de registros ausentes,
y su integración asíncrona).

## Último commit aprobado

**Mensaje:** Preparar el plan de sincronización del catálogo

**Etapa aprobada:** Preparación del plan de sincronización del catálogo:
nueva función `preparar_plan_sincronizacion(diferencias)` en
`escanear_videos.py` (capa de catálogo). Recibe el resultado de
`detectar_diferencias()` y devuelve el plan `{"carpeta",
"a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}`.
`a_incorporar` son los registros básicos de los videos nuevos preparados
con `preparar_registros_basicos` (claves `{nombre, ruta, extension,
fecha_importacion}`); **`fecha_importacion` se genera al preparar esos
registros, no durante `detectar_diferencias`**. `ya_sincronizados` y
`candidatos_a_eliminar` son listas ordenadas de nombres; los candidatos
a eliminación son **únicamente informativos**. **Sin efectos**: el plan
no inserta, actualiza ni elimina registros, **no accede a SQLite**, no
ejecuta FFprobe ni FFmpeg y no está integrado al pipeline ni a la
interfaz. Pendiente: la aplicación real del plan y la deduplicación de
nombres repetidos. Con suite nueva `prueba_plan_sincronizacion.py` (12
pruebas). Aprobada con observaciones.

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Preparación del plan de sincronización del catálogo:
`preparar_plan_sincronizacion(diferencias)` en `escanear_videos.py`
(capa de catálogo, ubicada entre `detectar_diferencias` y
`listar_videos_paginado`). Operación **pura** que recibe el resultado de
`detectar_diferencias()` y devuelve el plan `{"carpeta",
"a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}`.
`a_incorporar` son los registros básicos de los videos nuevos preparados
con `preparar_registros_basicos(nuevos, carpeta)` (claves `{nombre,
ruta, extension, fecha_importacion}`); **`fecha_importacion` se genera
al preparar esos registros, no durante `detectar_diferencias`**.
`ya_sincronizados` y `candidatos_a_eliminar` son listas ordenadas de
nombres; los candidatos a eliminación son **únicamente informativos**.
Validaciones: `diferencias` no-dict → `TypeError`; claves obligatorias
faltantes (`carpeta`, `presentes_en_ambos`, `nuevos`,
`ausentes_del_disco`) → `ValueError`; `carpeta` no texto no vacío →
`ValueError`; colecciones de nombres de texto o no iterables →
`TypeError` (helper interno `_coleccion_nombres`); claves extra
ignoradas. **Sin efectos**: el plan no inserta, actualiza ni elimina
registros, **no accede a SQLite**, no ejecuta FFprobe ni FFmpeg y no
está integrado al pipeline ni a la interfaz. **Ausencia deliberada**: la
aplicación real del plan continúa pendiente y **no existe todavía
deduplicación de nombres repetidos**. Con suite nueva
`prueba_plan_sincronizacion.py` (12 pruebas). Aprobada con observaciones.

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
-   Detección no destructiva de diferencias entre la carpeta y el
    catálogo SQLite (`detectar_diferencias`; compara por nombre, solo
    lectura, sin integración al pipeline ni a la interfaz).
-   Preparación del plan de sincronización del catálogo
    (`preparar_plan_sincronizacion`; pura, sin SQLite/FFprobe/FFmpeg/
    pipeline/interfaz; candidatos a eliminación informativos; la
    aplicación del plan y la deduplicación de nombres repetidos quedan
    pendientes).
-   Pruebas automatizadas.

### En desarrollo

Integración funcional completa del catálogo: el pipeline (`TareaEscaneo`
→ `TareaFFprobe` → `combinar_registros_con_ffprobe` → `TareaMiniaturas`
→ `combinar_registros_con_miniaturas` → `TareaGuardarVideos`) ya
convierte los archivos detectados por la interfaz en registros con
metadatos FFprobe y cantidad de miniaturas y los escribe en SQLite
conservando los preexistentes, y la **detección de diferencias** disco ↔
BD ya existe de forma no destructiva (`detectar_diferencias`) con su
**plan de sincronización** ya preparado de forma pura
(`preparar_plan_sincronizacion`, sin efectos ni integración), pero la
**sincronización completa** —la escritura masiva con detección de
archivos y la **eliminación controlada de registros ausentes** con su
integración asíncrona— sigue pendiente. La carga inicial asíncrona de la
primera página del catálogo ya está integrada en la interfaz.

## Pendientes prioritarios

1.  Sincronización completa SQLite asíncrona (la detección de diferencias
    ya existe en `detectar_diferencias` —solo lectura, por nombre— y el
    plan ya se prepara en `preparar_plan_sincronizacion` —puro, sin
    efectos—; falta la **aplicación del plan** (escritura masiva con
    detección de archivos y eliminación controlada de registros ausentes)
    y su integración asíncrona).
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
con metadatos FFprobe y miniaturas y los escribe, y existen la detección
no destructiva de diferencias (`detectar_diferencias`) y el plan de
sincronización preparado de forma pura (`preparar_plan_sincronizacion`,
con `candidatos_a_eliminar` únicamente informativos), pero la
sincronización completa sigue pendiente (aplicación del plan: escritura
masiva con detección de archivos y eliminación controlada de registros
ausentes, con su integración asíncrona); - `detectar_diferencias` compara
por nombre y no detecta movimientos ni renombrados (queda para etapas
futuras); - **no existe todavía deduplicación de nombres repetidos** en
el plan de sincronización; - el enrutado de resultados por
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
de archivos y **eliminación controlada de registros ausentes**, con su
integración asíncrona). Las etapas anteriores (detección no destructiva
de diferencias con `detectar_diferencias` y preparación del plan con
`preparar_plan_sincronizacion`) quedaron aprobadas y commiteadas; la
**aplicación del plan** (insertar/actualizar `a_incorporar` y eliminar
de forma controlada los registros de `candidatos_a_eliminar`, con su
integración asíncrona) sigue pendiente y se abordará como próxima etapa,
manteniendo el alcance limitado: sin selección inteligente, sin
múltiples miniaturas, sin eliminación de archivos antiguos y sin recarga
automática de la interfaz.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
