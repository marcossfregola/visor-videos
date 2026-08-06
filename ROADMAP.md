# ROADMAP

## Objetivo

Este documento reúne las funcionalidades previstas para el Visor de
Videos. No representa el estado actual del proyecto, sino la dirección
de desarrollo. El orden podrá cambiar según las decisiones
arquitectónicas.

------------------------------------------------------------------------

# Próximas líneas de trabajo previstas

Dirección general acordada para el desarrollo futuro. Constituye una
guía de prioridades y no un compromiso rígido e inamovible:

1. **Infraestructura de paneles** — migrar la interfaz actual a un
   sistema de paneles independientes basado en QSplitter.
2. **Árbol de carpetas** — panel izquierdo de navegación como mecanismo
   principal para explorar la biblioteca.
3. **Navegación completa desde el árbol** — reemplazar progresivamente
   el botón "Seleccionar carpeta".
4. **Tarjetas expandibles** — mostrar entre 20 y 30 previews por video
   al expandir una tarjeta.
5. **Ordenamientos del catálogo** — permitir ordenar por nombre,
   duración, resolución, codec, tamaño o fecha.
6. **Organización** — favoritos, etiquetas y funciones relacionadas.

------------------------------------------------------------------------

# Prioridad inmediata

-   ~~Opción de incluir o excluir subcarpetas en el escaneo.~~ Implementada
    con persistencia de la preferencia entre ejecuciones.
-   Paginación completa automática del catálogo — scroll infinito,
    búsqueda en SQL desde la interfaz y ordenamiento configurable. La
    carga manual de una página adicional con el botón "Cargar más" ya
    existe.
-   Deduplicación de nombres repetidos en el plan de sincronización.
-   Persistencia de preferencias generales de configuración — más allá
    de la última carpeta seleccionada, que ya se persiste.

------------------------------------------------------------------------

# Experiencia de usuario

-   ~~Barra de progreso.~~ Implementada.
-   ~~Selección visual de filas (simple, Ctrl+clic y Shift+clic).~~ Implementada.
    Incluye acciones mediante menú contextual (abrir, abrir carpeta, copiar ruta,
    copiar rutas de los seleccionados, abrir carpetas de los seleccionados),
    restauración automática de la selección tras reconstruir tarjetas y selección
    por rango con Shift+clic basada en ancla y orden visible.
-   Cancelación de tareas.
-   Reanudación de trabajos.
-   Configuración persistente.
-   Mejor navegación entre videos.
-   Tarjeta expandible — cada tarjeta podrá expandirse temporalmente
    para mostrar aproximadamente entre 20 y 30 previews del mismo
    video, permitiendo inspeccionar visualmente el contenido sin
    reproducirlo. El doble clic continuará reservado para abrir el
    video.
    -   Desplazamiento horizontal de previews mediante rueda del mouse
        cuando existan más previews que espacio disponible. La
        conveniencia de mostrar o no una barra horizontal se evaluará
        mediante pruebas de usabilidad.

------------------------------------------------------------------------

# Calidad de miniaturas

-   Selección inteligente de fotogramas.
-   Evitar pantallas negras.
-   Evitar fundidos.
-   Evitar créditos.
-   Evitar imágenes repetidas.
-   ~~Cantidad configurable de miniaturas.~~ Implementada mediante combo box 3/5/7/9
    con persistencia y actualización inmediata de la interfaz.

------------------------------------------------------------------------

# Infraestructura futura

-   Sistema de paneles independientes y configurables — infraestructura
    base que permitirá agregar, quitar y reorganizar paneles sin
    rediseñar la aplicación.
-   Panel izquierdo de navegación con árbol de carpetas como mecanismo
    principal para explorar la biblioteca.
-   Panel de propiedades — metadatos del video seleccionado.
-   Panel de favoritos — acceso rápido a videos marcados.
-   Panel de etiquetas — organización mediante etiquetas.
-   Panel de IA — clasificación, descripción y reconocimiento.
-   Posibilidad de incorporar nuevos paneles en el futuro sin
    modificar la arquitectura de paneles.

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
