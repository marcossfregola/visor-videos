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
    ambos en SQL, con búsqueda parcial por `LIKE` parametrizada; aún no
    consumida por la interfaz.
-   Escritura individual asíncrona — **completado** (`TareaGuardarVideo`).
-   Escritura de colección asíncrona — **completado**
    (`TareaGuardarVideos`): persiste colecciones de registros preparados
    en una única transacción atómica.

1.  Sincronización SQLite asíncrona — **pendiente** (solo existe la
    escritura de colecciones preparadas con upsert; la sincronización
    completa del catálogo —detección de archivos, FFprobe y eliminación
    de registros ausentes— y la escritura masiva no están implementadas).
2.  Encadenamiento progresivo del pipeline — **pendiente** (el pipeline
    Escaneo → SQLite aún no está encadenado).
3.  Actualización asíncrona de la interfaz — **pendiente** (la interfaz
    no consume las tareas asíncronas; la lectura paginada
    `TareaLecturaCatalogoPaginada` está implementada pero aún no se
    integra con la ventana).
4.  FFmpeg en segundo plano.
5.  Generación de múltiples miniaturas por video.

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
