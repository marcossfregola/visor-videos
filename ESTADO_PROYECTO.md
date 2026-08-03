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
`{"diferencias", "plan", "incorporaciones", "eliminaciones", "resumen"}`)
y **la integración de la sincronización completa en la interfaz**
(`visor_videos.py` lanza `TareaSincronizacionCatalogo` con el mismo
`GestorTareas` **tras el guardado exitoso** del pipeline escaneo → FFprobe
→ miniaturas → guardado: `_sincronizacion_pendiente`/`tarea_sincronizacion`/
`resultado_sincronizacion`, mensajes `MENSAJE_SINCRONIZANDO`/
`MENSAJE_ERROR_SINCRONIZACION` y resumen final "Sincronización completa: N
incorporados, M eliminados, K candidatos restantes"; los registros ausentes
del disco se eliminan de SQLite y los presentes conservan intactos sus
metadatos FFprobe y `cantidad_miniaturas`; no se eliminan archivos físicos
ni miniaturas y la GUI no abre SQLite ni ejecuta SQL; la sincronización no
se inicia si falla una fase anterior y la interfaz queda recuperable tras
éxito o error) y **la recarga asíncrona del catálogo tras la
sincronización** (`visor_videos.py` recarga la primera página del catálogo
con la **misma** `TareaLecturaCatalogoPaginada`/`GestorTareas` **solo tras
una sincronización exitosa** y reemplaza las tarjetas con
`_reemplazar_tarjetas` —libera las tarjetas viejas (`removeWidget` +
`deleteLater`), vacía `self.tarjetas`, crea las nuevas en la misma grilla y
reaplica el filtro, conservando `resultado_sincronizacion`; ante un error
de recarga conserva las tarjetas viejas, muestra `MENSAJE_ERROR_RECARGA` y
no revierte la sincronización ya confirmada; sin FFprobe/FFmpeg/miniaturas
y sin SQL en la GUI—) aprobadas; quedan pendientes la **deduplicación de
nombres repetidos** y la **paginación completa** (scroll infinito, búsqueda
en SQL desde la interfaz y ordenamiento configurable), que todavía no
existen.

## Último commit aprobado

**Mensaje:** Recargar el catálogo después de sincronizar

**Etapa aprobada:** Recarga asíncrona del catálogo tras la sincronización:
`visor_videos.py` recarga el catálogo en segundo plano **solo tras una
sincronización exitosa** y **reemplaza las tarjetas** por las de la primera
página actualizada, extendiendo la cadena a **6 tareas** (`TareaEscaneo` →
`TareaFFprobe` → `TareaMiniaturas` → `TareaGuardarVideos` →
`TareaSincronizacionCatalogo` → `TareaLecturaCatalogoPaginada`) con el
mismo `GestorTareas`. `_al_resultado_sincronizacion` marca
`_recarga_catalogo_pendiente = True` y `_al_tarea_finalizada` (gestor
`inactivo`) inicia la recarga con `_iniciar_recarga_catalogo()`, que usa la
misma factoría `_crear_tarea_lectura()` (misma
`TareaLecturaCatalogoPaginada(TAMANIO_PAGINA_INICIAL, 0, None, ruta_db)`,
primera página). Se incorporan los atributos `_recarga_catalogo_pendiente`/
`tarea_recarga_catalogo`, los handlers `_al_resultado_recarga`/
`_al_error_recarga`, la constante `MENSAJE_ERROR_RECARGA` ("No se pudo
actualizar el catálogo") y `_reemplazar_tarjetas(filas)`: **las tarjetas
viejas se conservan hasta que llega el resultado válido y completo**; al
llegar, se quitan de la grilla (`removeWidget` + `deleteLater`, liberando
los widgets Qt), se vacía `self.tarjetas`, se crean las tarjetas nuevas en
la **misma `QGridLayout` y el mismo `QScrollArea` reutilizados** y se
reaplica el filtro (que actualiza el contador) — **sin tarjetas ocultas
obsoletas**—; `resultado_sincronizacion` se conserva. Ante un **fallo de
recarga**, `_al_error_recarga` **conserva las tarjetas viejas**, muestra
`MENSAJE_ERROR_RECARGA`, el gestor queda `INACTIVO`, el botón de escaneo se
rehabilita y un nuevo escaneo es posible; la recarga fallida **no revierte
la sincronización ya confirmada en SQLite**. La recarga es de **solo
lectura** de la primera página: **no ejecuta FFprobe/FFmpeg/miniaturas**, la
GUI sigue sin SQLite ni SQL y **no llama a `listar_videos_paginado`
directamente**. **No existen todavía** páginas posteriores, scroll
infinito, búsqueda en SQL desde la interfaz ni ordenamiento configurable.
Se agregó `prueba_recarga_catalogo.py` (**20 pruebas**) y se actualizaron
`prueba_escaneo_guardado.py` (24), `prueba_escaneo_interfaz.py` (36) y
`prueba_sincronizacion_interfaz.py` (18) a la cadena de 6 tareas. Smoke
test `visor_videos.py` con `tarjetas_finales=['clip.avi', 'peli.mp4',
'serie.mkv']` (recarga tras la sincronización) y `resumen_sincronizacion`
conservado, exit 0. Regresiones parciales 82/82 OK (suites ajenas no
reejecutadas). **Alcance**: la recarga muestra únicamente la primera página;
la paginación completa (scroll infinito), la búsqueda en SQL desde la
interfaz, el ordenamiento configurable y la deduplicación de nombres
repetidos quedan pendientes. Aprobada con observaciones.

**SHA definitivo:** debe consultarse con `git log -1` (el SHA no se
escribe en este documento para evitar autorreferencias al commit).

## Última etapa aprobada

Recarga asíncrona del catálogo tras la sincronización: `visor_videos.py`
recarga el catálogo en segundo plano **solo tras una sincronización
exitosa** y **reemplaza las tarjetas** por las de la primera página
actualizada, extendiendo la cadena a **6 tareas** (`TareaEscaneo` →
`TareaFFprobe` → `TareaMiniaturas` → `TareaGuardarVideos` →
`TareaSincronizacionCatalogo` → `TareaLecturaCatalogoPaginada`) con el
**mismo** `GestorTareas`. `_al_resultado_sincronizacion` marca
`_recarga_catalogo_pendiente = True` y `_al_tarea_finalizada` (gestor
`inactivo`) inicia la recarga con `_iniciar_recarga_catalogo()`, que usa la
misma factoría `_crear_tarea_lectura()` (misma
`TareaLecturaCatalogoPaginada(TAMANIO_PAGINA_INICIAL, 0, None, ruta_db)`,
primera página). Estados nuevos `_recarga_catalogo_pendiente`/
`tarea_recarga_catalogo`, handlers `_al_resultado_recarga` (reemplaza las
tarjetas con `_reemplazar_tarjetas`) y `_al_error_recarga` (muestra
`MENSAJE_ERROR_RECARGA`, gestor `INACTIVO`, interfaz recuperable),
constante `MENSAJE_ERROR_RECARGA` ("No se pudo actualizar el catálogo") y
`_reemplazar_tarjetas(filas)`: **las tarjetas viejas se conservan hasta que
llega el resultado válido y completo**; al llegar se quitan de la grilla
(`removeWidget` + `deleteLater`, liberando los widgets Qt), se vacía
`self.tarjetas`, se crean las tarjetas nuevas en la **misma `QGridLayout` y
el mismo `QScrollArea` reutilizados** y se reaplica el filtro (que actualiza
el contador) — **sin tarjetas ocultas obsoletas** —; `resultado_sincronizacion`
se conserva. Ante un **fallo de recarga** se **conservan las tarjetas
viejas**, se muestra `MENSAJE_ERROR_RECARGA`, el gestor queda `INACTIVO`,
el botón de escaneo se rehabilita y un nuevo escaneo es posible; la recarga
fallida **no revierte la sincronización ya confirmada en SQLite**. La
recarga es de **solo lectura** de la primera página: **no ejecuta
FFprobe/FFmpeg/miniaturas**, la GUI sigue sin SQLite ni SQL y **no llama a
`listar_videos_paginado` directamente**. La sincronización **solo se lanza
tras un guardado exitoso** (no se inicia si falla cualquier fase anterior).
**Ausencia deliberada**: la recarga muestra únicamente la primera página;
la paginación completa (scroll infinito), la búsqueda en SQL desde la
interfaz, el ordenamiento configurable y la deduplicación de nombres
repetidos continúan pendientes. Con suite nueva `prueba_recarga_catalogo.py`
(20 pruebas) y suites actualizadas `prueba_escaneo_guardado.py` (24),
`prueba_escaneo_interfaz.py` (36) y `prueba_sincronizacion_interfaz.py`
(18) a la cadena de 6 tareas. Regresiones parciales 82/82 OK (suites ajenas
no reejecutadas). Aprobada con observaciones.

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
    "eliminaciones", "resumen"}`).
-   Integración de la sincronización completa en la interfaz
    (`visor_videos.py` lanza `TareaSincronizacionCatalogo` con el mismo
    `GestorTareas` **tras el guardado exitoso** del pipeline escaneo →
    FFprobe → miniaturas → guardado; estados
    `_sincronizacion_pendiente`/`tarea_sincronizacion`/
    `resultado_sincronizacion`, handlers `_al_resultado_sincronizacion`/
    `_al_error_sincronizacion`, constantes `MENSAJE_SINCRONIZANDO`/
    `MENSAJE_ERROR_SINCRONIZACION` y `texto_resumen_sincronizacion()`;
    al terminar elimina de SQLite los registros ausentes del disco,
    conserva intactos los metadatos FFprobe y `cantidad_miniaturas` de
    los presentes, **no elimina archivos físicos ni miniaturas**, **no
    recarga ni reconstruye tarjetas** y **no abre SQLite ni ejecuta SQL**
    desde la GUI; la sincronización solo se lanza tras un guardado
    exitoso y la interfaz queda recuperable tras éxito o error).
-   Recarga asíncrona del catálogo tras la sincronización
    (`visor_videos.py` recarga la primera página con la **misma**
    `TareaLecturaCatalogoPaginada`/`GestorTareas` **solo tras una
    sincronización exitosa** y reemplaza las tarjetas con
    `_reemplazar_tarjetas`: estados `_recarga_catalogo_pendiente`/
    `tarea_recarga_catalogo`, handlers `_al_resultado_recarga`/
    `_al_error_recarga`, constante `MENSAJE_ERROR_RECARGA` y factoría
    `_crear_tarea_lectura`; las tarjetas viejas se conservan hasta el
    resultado válido y completo, luego se liberan (`removeWidget` +
    `deleteLater`), se vacía `self.tarjetas`, se crean las nuevas en la
    **misma grilla y el mismo `QScrollArea` reutilizados** y se reaplica
    el filtro — sin tarjetas ocultas obsoletas —; `resultado_sincronizacion`
    se conserva; ante un error de recarga se conservan las tarjetas viejas,
    se muestra `MENSAJE_ERROR_RECARGA`, el gestor queda `INACTIVO`, el botón
    de escaneo se rehabilita y **no se revierte la sincronización ya
    confirmada en SQLite**; fase de solo lectura de la primera página sin
    FFprobe/FFmpeg/miniaturas y sin SQL en la GUI).
-   Pruebas automatizadas.

### En desarrollo

La sincronización completa del catálogo ya está integrada en la interfaz:
el pipeline (`TareaEscaneo` → `TareaFFprobe` → `TareaMiniaturas` →
`TareaGuardarVideos`) convierte los archivos detectados en registros con
metadatos FFprobe y cantidad de miniaturas y los escribe en SQLite
conservando los preexistentes, tras el guardado exitoso se lanza
`TareaSincronizacionCatalogo` (detección de diferencias
`detectar_diferencias`, preparación del plan
`preparar_plan_sincronizacion`, aplicación de incorporaciones
`aplicar_incorporaciones` y eliminación controlada de ausentes
`eliminar_candidatos`) con el mismo `GestorTareas`, que elimina de SQLite
los registros ausentes y conserva los presentes, y **tras una
sincronización exitosa se recarga el catálogo en segundo plano**
(`TareaLecturaCatalogoPaginada` con el mismo gestor) y se **reemplazan las
tarjetas** con la primera página actualizada (`_reemplazar_tarjetas`).
Quedan pendientes la **deduplicación de nombres repetidos** y la
**paginación completa** del catálogo (páginas posteriores, scroll
infinito, búsqueda en SQL desde la interfaz y ordenamiento configurable,
que todavía no existen): la carga inicial y la recarga muestran únicamente
la primera página.

## Pendientes prioritarios

1.  Paginación completa del catálogo en la interfaz (páginas posteriores,
    scroll infinito, búsqueda en SQL desde la interfaz y ordenamiento
    configurable). **No existen todavía**: la carga inicial y la recarga
    tras la sincronización muestran únicamente la primera página
    (`TAMANIO_PAGINA_INICIAL = 100`); la recarga tras una sincronización
    exitosa ya está implementada (`visor_videos.py` relee la primera página
    con la misma `TareaLecturaCatalogoPaginada`/`GestorTareas` y reemplaza
    las tarjetas con `_reemplazar_tarjetas`).
2.  Deduplicación de nombres repetidos en el plan de sincronización.
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
con metadatos FFprobe y miniaturas y los escribe, y la **sincronización
completa ya está integrada en la interfaz** (`visor_videos.py` lanza
`TareaSincronizacionCatalogo` tras el guardado exitoso, que encadena en
un `QThread` la detección no destructiva de diferencias
(`detectar_diferencias`), el plan preparado de forma pura
(`preparar_plan_sincronizacion`, con `candidatos_a_eliminar`
únicamente informativos), la aplicación no destructiva de las
incorporaciones (`aplicar_incorporaciones`, que persiste solo
`a_incorporar` reutilizando `guardar_videos`) y la eliminación
controlada de los registros ausentes (`eliminar_candidatos`, con
validación previa y transacción atómica)), **tras una sincronización
exitosa se recarga el catálogo en segundo plano** (`visor_videos.py`
relee la primera página con `TareaLecturaCatalogoPaginada` y reemplaza
las tarjetas con `_reemplazar_tarjetas`, liberando las viejas y creando
las nuevas en la misma grilla); quedan pendientes la **paginación
completa** (páginas posteriores, scroll infinito, búsqueda en SQL desde
la interfaz y ordenamiento configurable — no existen todavía) y la
deduplicación de nombres repetidos; - `detectar_diferencias` compara
por nombre y no detecta movimientos ni renombrados (queda para etapas
futuras); - **no existe todavía deduplicación de nombres repetidos** en
el plan de sincronización; - el enrutado de resultados por
`_escaneo_pendiente`/`_ffprobe_pendiente`/`_miniaturas_pendiente`/
`_guardado_pendiente`/`_sincronizacion_pendiente`/
`_recarga_catalogo_pendiente` es suficiente para una
única tarea activa y debe revisarse si la interfaz incorpora más tipos de tarea; - el escaneo no
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

**Aún no definida**: la recarga asíncrona del catálogo con la
actualización de tarjetas tras una sincronización exitosa ya quedó
aprobada y commiteada ("Recargar el catálogo después de sincronizar"), por
lo que no se inicia ninguna etapa nueva en esta entrega. Los siguientes
candidatos (todavía no definidos ni iniciados) son la **paginación
completa del catálogo en la interfaz** (páginas posteriores, scroll
infinito, búsqueda en SQL desde la interfaz y ordenamiento configurable —
hoy la carga inicial y la recarga muestran únicamente la primera página) y
la **deduplicación de nombres repetidos** en el plan de sincronización,
manteniendo el alcance limitado: sin selección inteligente, sin múltiples
miniaturas, sin eliminación de archivos antiguos y sin paginación más allá
de la primera página.

## Documentos del proyecto

-   DOCUMENTO_TECNICO.md
-   REGLAS_PROYECTO.md
-   ESTADO_PROYECTO.md
