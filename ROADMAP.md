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

1.  Opción de incluir o excluir subcarpetas — **pendiente** (configurar
    si el escaneo de la carpeta elegida recorre las subcarpetas).
2.  Escaneo real de la carpeta seleccionada — **pendiente** (conectar la
    carpeta elegida en la interfaz con `TareaEscaneo` y mostrar el
    resultado del escaneo).
3.  Sincronización Escaneo → SQLite — **pendiente** (solo existe la
    escritura de colecciones preparadas con upsert; la sincronización
    completa del catálogo —detección de archivos, FFprobe y eliminación
    de registros ausentes— y la escritura masiva no están implementadas).
4.  FFprobe — **pendiente** (integrar la ejecución de FFprobe en el
    pipeline Escaneo → SQLite para completar los metadatos).
5.  Generación asíncrona de miniaturas — **pendiente** (FFmpeg en
    segundo plano).
6.  Actualización dinámica de tarjetas — **pendiente** (refrescar la
    grilla a medida que se sincroniza el catálogo).
7.  Progreso — **pendiente** (barra de progreso y estado de las tareas
    en curso).
8.  Persistencia de configuración — **pendiente** (recordar entre
    sesiones la carpeta seleccionada y las preferencias; hoy la
    selección vive solo en la sesión).
9.  Beta funcional — **pendiente** (aplicación utilizable de punta a
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
