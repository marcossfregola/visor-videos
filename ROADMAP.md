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
   sistema de paneles independientes basado en QSplitter. **Implementado.**
2. **Centro de navegación (panel izquierdo)** — el panel izquierdo pasa
   a ser el centro de navegación permanente de la aplicación, con una
   estructura que permita incorporar progresivamente distintos orígenes
   de navegación sin rediseñar la interfaz.
3. **Navegación por sistema de archivos (Este equipo)** — representar
   el sistema de archivos real (Este equipo → Discos → Carpetas) como
   mecanismo principal para explorar la biblioteca, reemplazando
   progresivamente el botón "Seleccionar carpeta".
4. **Tarjetas expandibles** — mostrar entre 20 y 30 previews por video
   al expandir una tarjeta.
5. **Ordenamientos del catálogo** — permitir ordenar por nombre,
   duración, resolución, codec, tamaño o fecha.
6. **Organización** — favoritos, etiquetas y funciones relacionadas.

---

# Estructura objetivo del centro de navegación

```
📚 Catálogo

🖥 Este equipo
    Discos
        Carpetas

────────────────────

⭐ Favoritos

🏷 Etiquetas

📂 Colecciones

🕒 Recientes

🎬 Últimos escaneos
```

En las primeras etapas de desarrollo **solamente** se implementará el
nodo **Este equipo**. Los nodos Favoritos, Etiquetas, Colecciones,
Recientes y Últimos escaneos forman parte únicamente de la **visión
futura** y no deben implementarse todavía. La arquitectura del panel
deberá permitir agregarlos más adelante sin rediseñar la interfaz.

---

# Bloque de trabajo 2 — Navegación por sistema de archivos

Plan de implementación del bloque de trabajo actual. Cada etapa es
pequeña, verificable y acumulativa:

- **Etapa 2.1** — Reemplazar el placeholder del panel izquierdo por el
  árbol. Mostrar únicamente "Este equipo" y los discos. Sin navegación.
  **Implementada.**
- **Etapa 2.2** — Expandir discos y mostrar carpetas. **Implementada.**
- **Etapa 2.3** — Navegación completa del árbol.
- **Etapa 2.4** — Selección de la carpeta actual.
- **Etapa 2.5** — Persistencia del árbol (carpeta seleccionada y estado
  de expansión).
- **Etapa 2.6** — Escaneo automático al seleccionar carpeta (preferencia
  independiente de "Incluir subcarpetas").
- **Etapa 2.7** — Integración con el pipeline existente de escaneo.
- **Etapa 2.8** — Integración con "Incluir subcarpetas" (cuatro
  combinaciones posibles).
- **Etapa 2.9** — Indicadores visuales de carpetas escaneadas.
- **Etapa 2.10** — Filtrado del catálogo desde el árbol.

---

# Prioridad inmediata

-   ~~Opción de incluir o excluir subcarpetas en el escaneo.~~ Implementada
    con persistencia de la preferencia entre ejecuciones.
-   ~~Infraestructura de paneles (QSplitter).~~ Implementada.
-   ~~Árbol de carpetas en el panel izquierdo.~~ Implementadas las Etapas 2.1 y
    2.2 (árbol con "Este equipo", discos y carpetas con carga diferida); el
    bloque de trabajo 2 continúa.
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
    rediseñar la aplicación. **Implementado (QSplitter).**
-   Panel izquierdo de navegación como **centro de navegación
    permanente** con estructura extensible (Catálogo, Este equipo,
    Favoritos, Etiquetas, Colecciones, Recientes, Últimos escaneos).
    Solo **Este equipo** se implementa en las primeras etapas.
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
