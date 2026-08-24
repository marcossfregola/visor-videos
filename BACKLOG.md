# BACKLOG — Visor de Videos

Ideas futuras, posibilidades y mejoras **no comprometidas**. Separacion obligatoria: `BACKLOG = quiza`, `ROADMAP = decidido`. Nada de esto es trabajo prometido; pasa a desarrollo solo con una etapa aprobada.

> **Reconciliado post-Beta 7:** los elementos promovidos a `ROADMAP.md` Beta 8–11 se marcan como promovidos para evitar duplicación. Ver `ROADMAP.md` como autoridad decidida.

## Previews y calidad visual

- Seleccion inteligente de fotogramas: evitar pantallas negras, fundidos, creditos y fotogramas repetidos; elegir escenas mas informativas. (Origen: `ROADMAP.md` historico, Legacy Handoff 10.1.)
- Eleccion manual de previews: elegir uno o varios fotogramas, reemplazar previews automaticas y fijarlas para evitar regeneracion. (Origen: `VISION_PRODUCTO.md`, Legacy Handoff 10.2.)
- ~~Tarjetas expandibles: expandir temporalmente una tarjeta para mostrar 20-30 previews, con desplazamiento horizontal con rueda del mouse. (Origen: `ROADMAP.md`, Legacy Handoff 10.7.)~~ — **Promovido a ROADMAP Beta 9 P01 (tarjetas expandidas con muchas más previews).**
- Calidad visual adicional: evitar negros/fundidos/creditos/repetidas en miniaturas. (Origen: `ROADMAP.md`.)

## Reproduccion e interaccion

- ~~Reproduccion desde preview: doble clic sobre una preview para abrir el video desde ese instante. (Origen: `VISION_PRODUCTO.md`, Legacy Handoff 10.3.)~~ — **Promovido a ROADMAP Beta 9 P23.**
- VLC como reproductor avanzado preferido para funciones relacionadas con previews. (Origen: `VISION_PRODUCTO.md`, Legacy Handoff 10.4.)
- Reproducir el segmento entre dos previews seleccionadas. (Origen: `VISION_PRODUCTO.md`, Legacy Handoff 10.5.)
- Hover con ampliacion y reproduccion configurable. (Origen: Legacy Handoff 10.6; la ampliacion ya esta implementada.) — **PROMOVIDO: ampliación/flicker/configuración de ampliación → ROADMAP Beta 9 P07/P08. SIGUE EN BACKLOG: reproducción configurable mediante hover.**
- Reanudacion de trabajos y mejor navegacion entre videos. (Origen: `ROADMAP.md` historico.)

## Herramientas de manipulacion

- Recorte de videos usando previews como puntos de inicio y fin. (Origen: `VISION_PRODUCTO.md`, Legacy Handoff 10.8.)
- Union de multiples videos. (Origen: `VISION_PRODUCTO.md`, Legacy Handoff 10.8.) — **PROMOVIDO: unión/exportación de SEGMENTOS multivideo → ROADMAP Beta 11 P21. SIGUE EN BACKLOG: unión general de videos completos/arbitrarios (sin editor timeline tradicional).**
- Mantener el modelo basado en escenas/previews, sin editor de timeline tradicional. (Origen: `PROJECT.md`.)

## Organizacion y navegacion

- Favoritos, etiquetas, puntuaciones, carpetas virtuales, filtros avanzados y busqueda avanzada. (Origen: `ROADMAP.md`, Legacy Handoff 10.9.) — **PROMOVIDO a ROADMAP: carpetas favoritas → Beta 10 P12. SIGUEN EN BACKLOG: etiquetas; puntuaciones; carpetas virtuales; filtros avanzados; búsqueda avanzada.**
- Colecciones, recientes y ultimos escaneos como nodos del centro de navegacion. (Origen: `ROADMAP.md` historico, Legacy Handoff 10.9.) — **PROMOVIDO a ROADMAP: recientes → Beta 10 P13. SIGUEN EN BACKLOG: colecciones; últimos escaneos como nodo/criterio de navegación.**

## Administracion

- Deteccion de archivos movidos. (Origen: `ROADMAP.md`, Legacy Handoff 10.10.)
- ~~Renombrado masivo.~~ **Implementado en Beta 7 (B7.7 `TareaRenombrarMasivo` con motor `nombres.py`)** — reubicado fuera de backlog.
- Organización automática. (Origen: `ROADMAP.md`, Legacy Handoff 10.10.) — **futura / no implementada**; Beta 7 implementó modo Organización/Explorer manual y operaciones de archivos por lote con drag & drop (base reutilizable en el futuro, pero no constituye automatización).
- Deteccion de duplicados. (Origen: `ROADMAP.md`, Legacy Handoff 10.10.)

## Infraestructura y futuro

- Panel de propiedades (metadatos del video seleccionado). (Origen: `ROADMAP.md` historico.)
- Panel de favoritos y panel de etiquetas. (Origen: `ROADMAP.md` historico.)
- Panel de IA: clasificacion, descripcion y reconocimiento. (Origen: `ROADMAP.md` historico.)
- IA para descripcion y clasificacion automatica, reconocimiento de escenas, OCR, reconocimiento de rostros y objetos. (Origen: `ROADMAP.md` historico.)
- Plugins o extensiones y multiples vistas del catalogo. (Origen: `ROADMAP.md` historico.)
- Modulo de configuracion completo y cache formal de miniaturas/metadatos. (Origen: `ARCHITECTURE.md`, puntos de extension.)
