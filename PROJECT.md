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

## Alcance vigente (Beta 7 — B7.13 cerrada y publicada)

Producto evolucionado hasta:

- Exploración temporal interactiva (B4.1–B4.3): superficie temporal 0-100%, marcadores temporales y caché densa de exploración.
- Persistencia de marcadores y segmentos por video (B4.2, B5).
- Clasificación visual por color de marcadores/segmentos (B6.3) y resumen colapsado (B6.4).
- Filtros estructurados y ordenamiento configurable del catálogo (B6.5, B6.2).
- Exportación de material: extracción de un segmento (B6.7), lote de segmentos (B6.9), unión de segmentos (B6.10) con motor de nombres reutilizable (B6.8).
- Trazabilidad de videos derivados e integración robusta (B6.11–B6.12) con validación de reescaneo preservando metadatos.
- Organización de archivos (Beta 7 B7.1–B7.13): renombrado individual y masivo (motor `nombres.py`), mover/copiar/eliminar por lote, crear carpetas, modo Organización/Explorer con doble panel, navegación destino, objetivo drop estable y drag & drop interno con prevalidación atómica y actualización vía recarga paginada B7.8.

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

El estado actual, el historial y la arquitectura vigente se documentan en `STATUS.md`, `HISTORIAL_PROYECTO.md` y `ARCHITECTURE.md` respectivamente. Este documento no mezcla estado operativo.
