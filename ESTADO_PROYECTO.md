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
recorre subcarpetas), **preparación del plan de sincronización**
(`preparar_plan_sincronizacion` en `escanear_videos.py`: operación pura
que recibe el resultado de `detectar_diferencias` y devuelve
`a_incorporar` (registros básicos con `preparar_registros_basicos`; la
`fecha_importacion` se genera en la preparación, no durante la
detección)/`ya_sincronizados`/`candidatos_a_eliminar` (informativos); no
inserta, actualiza ni elimina, no accede a SQLite, no ejecuta
FFprobe/FFmpeg y no está integrada al pipeline ni a la interfaz) y
**aplicación no destructiva de las incorporaciones del plan**
(`aplicar_incorporaciones(plan, ruta_db=None)` en `escanear_videos.py`:
valida el plan completo antes de abrir SQLite, persiste únicamente
`a_incorporar` reutilizando la escritura transaccional `guardar_videos`,
no elimina `candidatos_a_eliminar`, no modifica `ya_sincronizados` ni
los registros preexistentes sincronizados y devuelve `incorporados`/
`nombres`/`pendientes_eliminacion`; no está integrada al pipeline ni a
la interfaz) y **eliminación controlada de los candidatos ausentes del
catálogo** (`eliminar_candidatos(plan, ruta_db=None)` en
`escanear_videos.py`: recibe el plan completo, valida antes de abrir
SQLite, elimina únicamente los registros de `candidatos_a_eliminar` con
una única transacción atómica —`rowcount` por candidato, un solo
`commit`, rollback total, `close` en `finally`—, no elimina archivos
físicos ni miniaturas, no toca `a_incorporar` ni `ya_sincronizados`,
devuelve `eliminados`/`nombres`/`incorporados` (informativo, derivado
del plan y puede ser `None`)/`restantes` y no está integrada al pipeline
ni a la interfaz) y **sincronización asíncrona del catálogo**
(`TareaSincronizacionCatalogo` en `tareas_videos.py`: orquesta en un
`QThread` la secuencia completa `detectar_diferencias` →
`preparar_plan_sincronizacion` → `aplicar_incorporaciones` →
`eliminar_candidatos`; las propiedades `carpeta`/`ruta_db` devuelven
directamente los valores actualmente inmutables (`str` o `None`) del
constructor; el `parent` es un padre Qt compatible con `QObject`; la
tarea no contiene SQL, no abre SQLite directamente, no almacena
conexiones, no usa `check_same_thread=False`, no ejecuta
FFprobe/FFmpeg/miniaturas/subprocesos ni accede a la interfaz; las
incorporaciones y la eliminación son transacciones independientes —si
falla la incorporación no se elimina, y si falla la eliminación las
incorporaciones confirmadas permanecen—; devuelve
`{"diferencias", "plan", "incorporaciones", "eliminaciones", "resumen"}`
y **aún no está integrada con `visor_videos.py`**) aprobadas; pendiente
la integración funcional completa del catálogo: la **integración de la
sincronización asíncrona con el flujo de la interfaz** y la
deduplicación de nombres repetidos.

## Último commit aprobado

**Mensaje:** Agregar sincronización asíncrona del catálogo

**Etapa aprobada:** Sincronización asíncrona del catálogo: nueva clase
`TareaSincronizacionCatalogo(TareaBase)` en `tareas_videos.py`, que en
segundo plano (con `QThread` mediante `TareaBase` + `GestorTareas`)
encadena la secuencia exacta `detectar_diferencias` →
`preparar_plan_sincronizacion` → `aplicar_incorporaciones` →
`eliminar_candidatos` e importa `escanear_videos as escanear_mod` (el
módulo, no los nombres de las funciones). El constructor recibe
`carpeta` y `ruta_db` opcional (por defecto cada función delega su
default `ruta_biblioteca()`) más `parent` como **padre Qt compatible
con `QObject`**; las propiedades de solo lectura `carpeta` y `ruta_db`
**devuelven directamente los valores actualmente inmutables (`str` o
`None`) recibidos en el constructor**, sin copias generales. `_trabajo()`
devuelve `{"diferencias", "plan", "incorporaciones", "eliminaciones",
"resumen"}` (`resumen` = `nuevos`/`ya_sincronizados`/`incorporados`/
`eliminados`/`candidatos_restantes`); **no se afirma que el resultado
completo sea inmutable**. **La tarea no contiene SQL, no abre SQLite
directamente, no almacena conexiones y no usa `check_same_thread=False`**;
**no ejecuta FFprobe, FFmpeg, miniaturas ni subprocesos** y **no accede a
la interfaz**. **Atomicidad**: la incorporación y la eliminación son
**transacciones independientes**, no una única transacción global; si
falla la incorporación **no se ejecuta la eliminación**; si falla la
eliminación, las **incorporaciones ya confirmadas permanecen** y la
eliminación fallida revierte **únicamente su propia transacción**.
`prueba_plan_sincronizacion.py` se **adaptó con una allowlist exacta**:
la condición de T02 permite exclusivamente `TareaSincronizacionCatalogo`
y **rechaza cualquier otra clase** con "Plan"/"Sincronizacion". Se
agregó `prueba_sincronizacion_asincrona.py` (27 pruebas). Regresiones
completas 321/321 OK. **No está integrada todavía con
`visor_videos.py`**; la integración con el flujo de la interfaz y la
deduplicación de nombres repetidos quedan pendientes. Aprobada con
observaciones.

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Sincronización asíncrona del catálogo: `TareaSincronizacionCatalogo`
en `tareas_videos.py` (capa de tareas asíncronas sobre `TareaBase` +
`GestorTareas`). En segundo plano (un `QThread` propio) encadena la
secuencia exacta `detectar_diferencias` → `preparar_plan_sincronizacion`
→ `aplicar_incorporaciones` → `eliminar_candidatos`, importando
`escanear_videos as escanear_mod` (el módulo, no los nombres de las
funciones). El constructor recibe `carpeta` y `ruta_db` opcional (por
defecto cada función delega su default `ruta_biblioteca()`) más `parent`
como **padre Qt compatible con `QObject`**; las propiedades de solo
lectura `carpeta` y `ruta_db` **devuelven directamente los valores
actualmente inmutables (`str` o `None`) recibidos en el constructor**,
sin copias generales. `_trabajo()` devuelve `{"diferencias", "plan",
"incorporaciones", "eliminaciones", "resumen"}` (`resumen` =
`nuevos`/`ya_sincronizados`/`incorporados`/`eliminados`/
`candidatos_restantes`); **no se afirma que el resultado completo sea
inmutable**. **La tarea no contiene SQL, no abre SQLite directamente, no
almacena conexiones y no usa `check_same_thread=False`**; **no ejecuta
FFprobe, FFmpeg, miniaturas ni subprocesos** y **no accede a la
interfaz**. **Atomicidad**: la incorporación y la eliminación son
**transacciones independientes**, no una única transacción global; si
falla la incorporación **no se ejecuta la eliminación**; si falla la
eliminación, las **incorporaciones ya confirmadas permanecen** y la
eliminación fallida revierte **únicamente su propia transacción**.
**No está integrada todavía con `visor_videos.py`**. **Ausencia
deliberada**: la integración con el flujo de la interfaz y la
deduplicación de nombres repetidos continúan pendientes. `prueba_plan_
sincronizacion.py` se adaptó con una allowlist exacta (solo
`TareaSincronizacionCatalogo` permitida en T02; cualquier otra clase con
"Plan"/"Sincronizacion" rechazada). Con suite nueva
`prueba_sincronizacion_asincrona.py` (27 pruebas). Aprobada con
observaciones.

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
    deduplicación de nombres repetidos queda pendiente).
-   Aplicación de incorporaciones del plan de sincronización
    (`aplicar_incorporaciones`; valida el plan completo antes de abrir
    SQLite, persiste únicamente `a_incorporar` reutilizando
    `guardar_videos` con su atomicidad existente, no elimina
    `candidatos_a_eliminar`, no modifica `ya_sincronizados`; devuelve
    `incorporados`/`nombres`/`pendientes_eliminacion`; sin pipeline/
    interfaz/escaneo/FFprobe/FFmpeg).
-   Eliminación controlada de candidatos ausentes del plan de
    sincronización (`eliminar_candidatos`; recibe el plan completo,
    valida antes de abrir SQLite con `_validar_plan_sincronizacion`
    (compartida con `aplicar_incorporaciones`), elimina únicamente los
    registros de `candidatos_a_eliminar` con una única transacción
    atómica (`rowcount` por candidato, un solo `commit`, rollback total,
    `close` en `finally`), no elimina archivos físicos ni miniaturas ni
    toca `a_incorporar`/`ya_sincronizados`; devuelve
    `eliminados`/`nombres`/`incorporados` (informativo, puede ser
    `None`)/`restantes`; sin pipeline/interfaz/escaneo/FFprobe/FFmpeg/
    `conectar_bd`/`guardar_videos`; la integración asíncrona queda
    pendiente).
-   Sincronización asíncrona del catálogo (`TareaSincronizacionCatalogo`
    en `tareas_videos.py`; encadena en un `QThread` la secuencia
    `detectar_diferencias` → `preparar_plan_sincronizacion` →
    `aplicar_incorporaciones` → `eliminar_candidatos` importando
    `escanear_videos` como módulo; `parent` compatible con `QObject`;
    propiedades `carpeta`/`ruta_db` que devuelven directamente los
    valores actualmente inmutables del constructor; sin SQL, sin abrir
    SQLite directamente, sin conexiones almacenadas, sin
    `check_same_thread=False`, sin FFprobe/FFmpeg/miniaturas/
    subprocesos/interfaz; incorporación y eliminación como transacciones
    independientes; devuelve `{"diferencias", "plan", "incorporaciones",
    "eliminaciones", "resumen"}`; sin integración con `visor_videos.py`).
-   Pruebas automatizadas.

### En desarrollo

Integración funcional completa del catálogo: el pipeline (`TareaEscaneo`
→ `TareaFFprobe` → `combinar_registros_con_ffprobe` → `TareaMiniaturas`
→ `combinar_registros_con_miniaturas` → `TareaGuardarVideos`) ya
convierte los archivos detectados por la interfaz en registros con
metadatos FFprobe y cantidad de miniaturas y los escribe en SQLite
conservando los preexistentes, la **detección de diferencias** disco ↔
BD ya existe de forma no destructiva (`detectar_diferencias`), el
**plan de sincronización** ya se prepara de forma pura
(`preparar_plan_sincronizacion`, sin efectos ni integración), la
**aplicación de las incorporaciones** ya existe de forma no destructiva
(`aplicar_incorporaciones`: valida el plan antes de abrir SQLite y
persiste únicamente `a_incorporar` reutilizando `guardar_videos`), la
**eliminación controlada de los candidatos ausentes** ya existe
(`eliminar_candidatos`: valida el plan antes de abrir SQLite y elimina
únicamente los registros de `candidatos_a_eliminar` con una transacción
atómica) y la **sincronización asíncrona del catálogo** ya orquesta la
secuencia completa en segundo plano (`TareaSincronizacionCatalogo` con
`QThread` + `GestorTareas`), pero la **integración de esa tarea con el
flujo de la interfaz** (`visor_videos.py`) y la **deduplicación de
nombres repetidos** siguen pendientes. La carga inicial asíncrona de la
primera página del catálogo ya está integrada en la interfaz.

## Pendientes prioritarios

1.  Integración de la sincronización asíncrona del catálogo con el
    flujo de la interfaz (la detección de diferencias ya existe en
    `detectar_diferencias` —solo lectura, por nombre—, el plan ya se
    prepara en `preparar_plan_sincronizacion` —puro, sin efectos—, las
    incorporaciones ya se aplican en `aplicar_incorporaciones`
    —no destructivo, reutilizando `guardar_videos`—, la eliminación
    controlada de los registros ausentes ya existe en
    `eliminar_candidatos` —validación previa y transacción atómica— y la
    **orquestación asíncrona completa** ya existe en
    `TareaSincronizacionCatalogo` —`QThread` + `GestorTareas`—; falta la
    **integración de `TareaSincronizacionCatalogo` con `visor_videos.py`**
    y la deduplicación de nombres repetidos).
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
no destructiva de diferencias (`detectar_diferencias`), el plan de
sincronización preparado de forma pura (`preparar_plan_sincronizacion`,
con `candidatos_a_eliminar` únicamente informativos), la aplicación
no destructiva de las incorporaciones (`aplicar_incorporaciones`, que
persiste solo `a_incorporar` reutilizando `guardar_videos`) y la
eliminación controlada de los registros ausentes (`eliminar_candidatos`,
con validación previa y transacción atómica) y la orquestación asíncrona
completa (`TareaSincronizacionCatalogo`, que encadena la secuencia en un
`QThread`), pero la **integración de `TareaSincronizacionCatalogo` con
`visor_videos.py`** (junto con la deduplicación de nombres repetidos)
sigue pendiente); - `detectar_diferencias` compara
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

**Integración de la sincronización asíncrona del catálogo con el flujo
de la interfaz** (`TareaSincronizacionCatalogo` consumida desde
`visor_videos.py` mediante el `GestorTareas`, con su deduplicación de
nombres repetidos). Las etapas anteriores (detección no destructiva de
diferencias con `detectar_diferencias`, preparación del plan con
`preparar_plan_sincronizacion`, aplicación no destructiva de las
incorporaciones con `aplicar_incorporaciones`, eliminación controlada de
los registros ausentes con `eliminar_candidatos` y la orquestación
asíncrona con `TareaSincronizacionCatalogo`) quedaron aprobadas y
commiteadas; la **integración con el flujo de la interfaz** y la
deduplicación de nombres repetidos siguen pendientes y se abordarán como
próxima etapa, manteniendo el alcance limitado: sin selección
inteligente, sin múltiples miniaturas, sin eliminación de archivos
antiguos y sin recarga automática de la interfaz.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
