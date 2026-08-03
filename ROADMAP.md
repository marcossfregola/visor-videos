# ROADMAP

## Objetivo

Este documento reúne las funcionalidades previstas para el Visor de
Videos. No representa el estado actual del proyecto, sino la dirección
de desarrollo. El orden podrá cambiar según las decisiones
arquitectónicas.

------------------------------------------------------------------------

# Prioridad inmediata

-   Escaneo asíncrono — **completado** (`TareaEscaneo`).
-   Lectura asíncrona del catálogo SQLite — **completado**
    (`TareaLecturaCatalogo`).
-   Lectura paginada del catálogo SQLite — **completado**
    (`listar_videos_paginado` / `TareaLecturaCatalogoPaginada`):
    consulta paginada (`LIMIT`/`OFFSET`) y `COUNT` con el mismo filtro,
    ambos en SQL, con búsqueda parcial por `LIKE` parametrizada.
-   Integración de la lectura asíncrona paginada con la interfaz —
    **completado** (`visor_videos.py` consume `TareaLecturaCatalogoPaginada`
    mediante `GestorTareas`): la primera página del catálogo se carga en
    segundo plano con estado de carga, manejo de errores y apagado
    ordenado, sin bloquear la ventana.
-   Escritura individual asíncrona — **completado** (`TareaGuardarVideo`).
-   Escritura de colección asíncrona — **completado**
    (`TareaGuardarVideos`): persiste colecciones de registros preparados
    en una única transacción atómica.
-   Selección de carpeta desde la interfaz — **completado**
    (`visor_videos.py`): el usuario elige la carpeta de videos con
    `QFileDialog`; la ruta se normaliza a absoluta, se valida que exista
    y sea un directorio, se muestra y se conserva durante la sesión sin
    escanearla.
-   Escaneo real y asíncrono de la carpeta seleccionada — **completado**
    (`visor_videos.py` + `TareaEscaneo` + `GestorTareas`): el botón
    "Escanear carpeta" escanea la carpeta elegida en segundo plano
    (mismo gestor de la ventana) y presenta la cantidad de videos
    detectados, sin tocar SQLite, FFprobe, FFmpeg ni miniaturas, y sin
    recorrer subcarpetas.
-   Detección de diferencias entre la carpeta y el catálogo — **completado
    (etapa no destructiva)** (`detectar_diferencias` en `escanear_videos.py`):
    compara por nombre los archivos de video de la carpeta con los
    registros de la base y devuelve `presentes_en_ambos`/`nuevos`/
    `ausentes_del_disco`. Solo lectura (no inserta, actualiza ni elimina),
    no integrada al pipeline ni a la interfaz, no detecta movimientos/
    renombrados y no recorre subcarpetas. La eliminación de registros
    ausentes y la integración asíncrona quedan pendientes.
-   Preparación del plan de sincronización — **completado (etapa de
    preparación)** (`preparar_plan_sincronizacion` en `escanear_videos.py`):
    recibe el resultado de `detectar_diferencias` y devuelve
    `a_incorporar` (registros básicos con `preparar_registros_basicos`; la
    `fecha_importacion` se genera en la preparación, no durante la
    detección)/`ya_sincronizados`/`candidatos_a_eliminar` (informativos).
    Operación pura: no inserta, actualiza ni elimina, no accede a SQLite,
    no ejecuta FFprobe/FFmpeg y no está integrada al pipeline ni a la
    interfaz. La aplicación de las incorporaciones ya existe
    (`aplicar_incorporaciones`); la eliminación controlada de registros
    ausentes y la deduplicación de nombres repetidos quedan pendientes.
-   Aplicación de incorporaciones del plan — **completado (etapa no
    destructiva)** (`aplicar_incorporaciones` en `escanear_videos.py`):
    recibe el plan `{"carpeta", "a_incorporar", "ya_sincronizados",
    "candidatos_a_eliminar"}` y persiste únicamente `a_incorporar`
    reutilizando la escritura transaccional `guardar_videos` (misma
    atomicidad: un solo `commit`, `rollback` total ante fallos). Valida
    el plan completo antes de abrir SQLite; no elimina
    `candidatos_a_eliminar`, no modifica `ya_sincronizados` ni los
    preexistentes sincronizados; devuelve `incorporados`/`nombres`/
    `pendientes_eliminacion`. No integrada al pipeline ni a la interfaz,
    sin escaneo/FFprobe/FFmpeg/miniaturas/subprocesos.
-   Eliminación controlada de registros ausentes — **completado (etapa
    controlada)** (`eliminar_candidatos` en `escanear_videos.py`):
    recibe el plan `{"carpeta", "a_incorporar", "ya_sincronizados",
    "candidatos_a_eliminar"}` y elimina únicamente los registros de
    `candidatos_a_eliminar` con una transacción atómica (un solo
    `commit`, `rollback` total ante fallos y `close` en `finally`; el
    `rowcount` por candidato cuenta solo las eliminaciones reales).
    Valida el plan completo antes de abrir SQLite (validación compartida
    con `aplicar_incorporaciones`); no elimina archivos físicos ni
    miniaturas, no toca `a_incorporar`/`ya_sincronizados`; devuelve
    `eliminados`/`nombres`/`incorporados` (informativo, puede ser
    `None`)/`restantes`. No integrada al pipeline ni a la interfaz, sin
    escaneo/FFprobe/FFmpeg/miniaturas/subprocesos. La integración
    asíncrona de la sincronización completa queda pendiente.
-   Sincronización asíncrona del catálogo — **completado (etapa de
    orquestación)** (`TareaSincronizacionCatalogo` en `tareas_videos.py`):
    encadena en segundo plano (un `QThread` con `TareaBase` +
    `GestorTareas`) la secuencia exacta `detectar_diferencias` →
    `preparar_plan_sincronizacion` → `aplicar_incorporaciones` →
    `eliminar_candidatos`, importando `escanear_videos` como módulo.
    Constructor con `carpeta` y `ruta_db` opcional (por defecto cada
    función delega su default `ruta_biblioteca()`) y `parent` compatible
    con `QObject`; propiedades `carpeta`/`ruta_db` que devuelven
    directamente los valores actualmente inmutables (`str` o `None`) del
    constructor. Devuelve `{"diferencias", "plan", "incorporaciones",
    "eliminaciones", "resumen"}`. Sin SQL, sin abrir SQLite directamente,
    sin conexiones almacenadas, sin `check_same_thread=False`, sin
    FFprobe/FFmpeg/miniaturas/subprocesos y sin acceso a la interfaz.
    Incorporación y eliminación como transacciones independientes (si
    falla la incorporación no se elimina; si falla la eliminación las
    incorporaciones confirmadas permanecen). **No integrada todavía con
    `visor_videos.py`**: la integración con el flujo de la interfaz y la
    deduplicación de nombres repetidos quedan pendientes.

1.  Opción de incluir o excluir subcarpetas — **pendiente** (configurar
    si el escaneo de la carpeta elegida recorre las subcarpetas).
2.  Preparación y escritura de registros detectados — **completado**
    (el pipeline `TareaEscaneo` → `TareaFFprobe` →
    `combinar_registros_con_ffprobe` → `TareaMiniaturas` →
    `combinar_registros_con_miniaturas` → `TareaGuardarVideos`, encadenado
    desde la interfaz, convierte los archivos detectados en registros
    con metadatos FFprobe y cantidad de miniaturas y los escribe en
    SQLite con el upsert transaccional, conservando los registros
    preexistentes).
3.  Sincronización completa del catálogo — **en curso (detección,
    preparación, aplicación de incorporaciones, eliminación controlada y
    orquestación asíncrona completadas)**: la detección no destructiva de
    diferencias existe (`detectar_diferencias`, por nombre y solo
    lectura), el plan ya se prepara de forma pura
    (`preparar_plan_sincronizacion`, con
    `a_incorporar`/`ya_sincronizados`/`candidatos_a_eliminar` y
    candidatos informativos), las incorporaciones ya se aplican de forma
    no destructiva (`aplicar_incorporaciones`, persistiendo únicamente
    `a_incorporar` con `guardar_videos`), los registros ausentes ya se
    eliminan de forma controlada (`eliminar_candidatos`, transacción
    atómica y validación previa) y la secuencia completa ya se orquesta
    en segundo plano (`TareaSincronizacionCatalogo` con `QThread` +
    `GestorTareas`); quedan pendientes la **integración de
    `TareaSincronizacionCatalogo` con el flujo de la interfaz** y la
    deduplicación de nombres repetidos.
4.  FFprobe integrado en el pipeline — **completado** (el pipeline
    escaneo → guardado completa duración, resolución y codec antes de
    escribir o actualizar los registros; `NULL` ante vacíos, incompletos
    o fallos individuales).
5.  FFmpeg y miniaturas — **completado (etapa limitada)**: generación asíncrona de una miniatura básica por video
    integrada en el pipeline (`TareaMiniaturas` con el mismo
    `GestorTareas`, reutilizando `asegurar_miniatura`/`contar_miniaturas`
    existentes; `cantidad_miniaturas` persistida). Quedan fuera del
    alcance: selección inteligente, múltiples miniaturas, eliminación de
    archivos antiguos y recarga automática de la interfaz. La limpieza
    controlada de versiones antiguas sigue pendiente.
6.  Eliminación de registros ausentes — **completado (aplicación
    controlada; la orquestación asíncrona completa existe; falta la
    integración con la interfaz)** (sincronizar la
    BD con los archivos que dejaron de existir; la detección de los
    ausentes ya existe de forma no destructiva en `detectar_diferencias`,
    el plan ya los expone como `candidatos_a_eliminar` en
    `preparar_plan_sincronizacion` (únicamente informativos), las
    incorporaciones ya se aplican en `aplicar_incorporaciones` sin tocar
    a los candidatos, la **aplicación controlada de la eliminación** ya
    existe en `eliminar_candidatos` (transacción atómica y validación
    previa) y la **orquestación asíncrona completa** ya existe en
    `TareaSincronizacionCatalogo`; falta su **integración con el flujo
    de la interfaz**).
7.  Recarga automática del catálogo tras la escritura — **pendiente**
    (refrescar la grilla a medida que se sincroniza el catálogo).
8.  Progreso — **pendiente** (barra de progreso y estado de las tareas
    en curso).
9.  Persistencia de configuración — **pendiente** (recordar entre
    sesiones la carpeta seleccionada y las preferencias; hoy la
    selección vive solo en la sesión).
10. Beta funcional — **pendiente** (aplicación utilizable de punta a
    punta con las funcionalidades anteriores integradas).

------------------------------------------------------------------------

# Experiencia de usuario

-   Barra de progreso.
-   Cancelación de tareas.
-   Reanudación de trabajos.
-   Configuración persistente.
-   Mejor navegación entre videos.

------------------------------------------------------------------------

# Calidad de miniaturas

-   Selección inteligente de fotogramas.
-   Evitar pantallas negras.
-   Evitar fundidos.
-   Evitar créditos.
-   Evitar imágenes repetidas.
-   Cantidad configurable de miniaturas.

------------------------------------------------------------------------

# Organización

-   Etiquetas.
-   Favoritos.
-   Puntuaciones.
-   Carpetas virtuales.
-   Filtros avanzados.
-   Búsqueda avanzada.

------------------------------------------------------------------------

# Administración

-   Detección de archivos movidos.
-   Renombrado masivo.
-   Organización automática.
-   Detección de duplicados.

------------------------------------------------------------------------

# Futuro

-   IA para descripción de videos.
-   IA para clasificación automática.
-   Reconocimiento de escenas.
-   OCR.
-   Reconocimiento de rostros y objetos.
-   Plugins o extensiones.
-   Múltiples vistas del catálogo.

------------------------------------------------------------------------

# Criterio

Las funcionalidades solo pasarán de este documento al desarrollo cuando
exista una etapa aprobada para implementarlas.
