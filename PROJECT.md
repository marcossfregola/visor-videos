# PROJECT — Visor de Videos

## Identidad

Visor de Videos es una aplicacion de escritorio para Windows orientada a explorar, organizar y analizar grandes colecciones de videos mediante fotogramas representativos (miniaturas y previews) sin necesidad de abrir cada archivo.

## Proposito

El proposito central es permitir identificar rapidamente el contenido de un video: que contiene, como es, y donde esta, con inspeccion visual como mecanismo principal. La aplicacion carga un catalogo desde una o mas carpetas, lo mantiene en SQLite y lo presenta como tarjetas navegables con miniaturas, previews y metadatos.

## Filosofia

- La exploracion visual es la funcion principal del producto; la reproduccion es secundaria.
- Las previews son el elemento principal de interaccion con el contenido.
- Adobe Bridge es una referencia conceptual, no una interfaz a copiar; el espacio de trabajo evoluciona hacia paneles configurables con navegacion persistente.
- El crecimiento se realiza mediante pequenas mejoras acumulativas, evitando redisenos completos.
- Funcionalidad antes que estetica: densidad visual, velocidad de navegacion y calidad de fotogramas pesan mas que un reproductor sofisticado.

## Objetivos

- Facilitar la identificacion visual de grandes colecciones de videos.
- Mantener un catalogo de metadatos consistente y sincronizado con el disco.
- Conservar una interfaz fluida con trabajo pesado fuera del hilo principal.
- Preservar los datos del usuario como prioridad absoluta.

## Alcance vigente (Beta 9 — cerrada y publicada `v9.0-beta`)

Producto evolucionado hasta **Beta 9 — Exploración visual avanzada** (B9.0–B9.9 + hover desactivable, cerrada y publicada `v9.0-beta`/`origin/beta9`; Beta 8 cerrada y publicada `v8.0-beta`/`e851c7c` como baseline):

- Exploración temporal interactiva (B4.1–B4.3), persistencia marcadores/segmentos (B4.2, B5), clasificación por color (B6.3) y resumen colapsado (B6.4) reubicado sobre miniaturas en B9.8 (P18 simplificado).
- Filtros estructurados y ordenamiento configurable (B6.5, B6.2).
- Exportación de material: extracción de un segmento (B6.7), lote (B6.9), unión (B6.10) con motor `nombres.py` (B6.8).
- Trazabilidad de videos derivados e integración robusta (B6.11–B6.12).
- Organización de archivos (Beta 7 B7.1–B7.13): renombrado individual/masivo, mover/copiar/eliminar por lote, crear carpetas, modo Organización/Explorer con doble panel y drag & drop.
- **Beta 8 — Identidad e integridad del catálogo (B8.1–B8.4 cerradas):** `video_id` autoridad lógica, `ruta_normalizada` (`abspath+normpath+normcase`) autoridad física `UNIQUE(ruta_normalizada)`, `nombre` no único (homónimos `AAAA.mp4` en `A/B` con `video_id` distinto), cache normal `v<id>`, `preparar_registros_basicos` con `basename`, navegación `MADRE/A/B` y descarte lecturas obsoletas por generación.
- **Beta 9 — Exploración visual avanzada (B9.0 `8fe1054` → B9.9 `03fd856` + hover desactivable `41216a1`, cerrada y publicada `v9.0-beta`):** tarjetas fijadas persistentes durante la vista (múltiples fijadas; colapsar manualmente desfija), Densidad como única autoridad temporal `Auto/15/30/60/120/200`, vistas Dinámica/Tira/Reducida/Ajustada; Tira virtualizada horizontal con anotaciones temporales y marcadores/segmentos; Reducida sin scroll horizontal propio; Ajustada en grilla responsive virtualizada/acotada; doble clic temporal exacto en Tira/Reducida/Ajustada (P23); columna de datos estable con elipsis (P09); autorepaint/retries acotados P06 con correcciones B9.9 (pending agotado filtrado y stale por `video_id+version+request_id`); P18 solo reubicación de barra resumen B6.4 sobre miniaturas; hover ampliado desactivable con sentinel `0` persistente.

## Alcance base (heredado)

- Exploracion y navegacion visual de colecciones de videos en Windows.
- Catalogo SQLite con escaneo, metadatos (FFprobe), miniaturas/previews (FFmpeg) y sincronizacion incremental.
- Operaciones seguras de archivos: copiar, pegar, mover, renombrar, crear carpetas y eliminar a Papelera de reciclaje (operaciones por lote y drag & drop desde B7).
- Configuracion persistente de preferencias del usuario.

## No-alcance

- No es un editor de video tradicional con timeline.
- No es un reproductor como centro del producto.
- No realiza borrado permanente de archivos como operacion del producto.
- No compite con Premiere, Resolve u otros editores profesionales.

## Principios de producto

- **Actualizacion parcial:** modificar solo el componente afectado; evitar reconstrucciones completas que pierdan estado, scroll o seleccion.
- **Reutilizacion de cache:** reutilizar miniaturas y previews validas; no regenerar con FFmpeg informacion ya disponible.
- **Preferencias persistentes:** persistir automaticamente las opciones estables del usuario (carpeta, escaneo automatico, cantidad de previews, tamanos, vista ampliada, modo de alcance).
- **Navegacion permanente:** el arbol de navegacion y la seleccion de carpetas forman parte del contexto central.
- **Seguridad de datos:** nunca sobrescribir silenciosamente, nunca borrar sin autorizacion; ante la duda, preservar.
- **Incrementalidad:** las operaciones no deben provocar reescaneos completos innecesarios.
- **Identidad lógica preservada:** las operaciones físicas conservan la identidad lógica del video y sus relaciones con marcadores/segmentos/derivados.

## Decisión definitiva de alcance — uso exclusivamente personal

**Visor de Videos es una aplicación de uso exclusivamente personal del propietario.** No existe intención de distribuir la aplicación públicamente ni convertirla en un producto para terceros. Esta decisión es definitiva y no temporal.

- La distribución pública de la aplicación queda **FUERA DE ALCANCE**.
- Publicar instaladores/binarios para terceros queda **FUERA DE ALCANCE**.
- El empaquetado/instalador (`PyInstaller` + `Inno Setup`) es secundario y opcional, solo como herramienta de comodidad personal del propietario.
- No se dedicará trabajo adicional al instalador salvo pedido explícito del propietario.
- La validación completa instalación/desinstalación/reinstalación **no es requisito** para cerrar betas ni continuar el desarrollo.
- Beta 8 puede definirse independientemente del instalador.
- Esta decisión se refiere a la distribución de la aplicación, **no a la visibilidad del repositorio GitHub**, que permanece **PUBLIC** por decisión separada.

Prioridades vigentes: funcionalidad, UX, exploración visual, rendimiento, integridad de datos y mantenibilidad.

## Direccion futura vigente

- Espacio de trabajo de paneles independientes y configurables (infraestructura base QSplitter ya implementada; doble panel B7.11).
- Centro de navegacion permanente con estructura extensible (catalogo, sistema de archivos, favoritos, etiquetas, colecciones, recientes, ultimos escaneos).
- Organización ya implementada (Beta 7); favoritos/etiquetas/puntuaciones y administración avanzada (detección de duplicados) quedan como dirección a planificar en BACKLOG.
- Las ideas no comprometidas viven en `BACKLOG.md`; el trabajo decidido en `ROADMAP.md`.

## Stack conceptual

- Windows.
- Python 3.13.
- PySide6 (Qt 6).
- SQLite (catalogo).
- FFmpeg y FFprobe (fotogramas y metadatos).
- Inno Setup 6 (instalador por usuario).

## Estado operativo

El estado actual, el historial y la arquitectura vigente se documentan en `STATUS.md`, `HISTORIAL_PROYECTO.md` y `ARCHITECTURE.md` respectivamente. Este documento no mezcla estado operativo. Beta 9 cerrada y publicada en `beta9`/`origin/beta9` + tag anotado `v9.0-beta` (último commit técnico B9.9 `03fd856` previo al cierre; hover `41216a1`; identidad `Beta 9 - B9.9`); baseline publicado `origin/beta8` + `v8.0-beta` `e851c7c`; sin GitHub Release ni instalador público; próximo foco Beta 10.
