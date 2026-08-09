# VISIÓN DE PRODUCTO — Visor de Videos

Este documento reúne las decisiones estratégicas, de producto y de diseño
que no pertenecen a la arquitectura técnica ni al estado del desarrollo.
Se actualiza mediante el cierre estratégico de hilos de trabajo (ver
`REGLAS_PROYECTO.md`, §13).

---

## Filosofía del producto

- El Visor de Videos evoluciona desde un **explorador profesional basado
  en fotogramas representativos** hacia un **entorno de trabajo
  especializado para explorar, organizar y analizar grandes colecciones
  de videos**.
- La **exploración visual** continúa siendo el objetivo principal del
  producto.
- La **reproducción** permanece como una función secundaria respecto de
  la exploración.
- No debe evolucionar hacia un editor de video tradicional.
- Las **previews** constituyen el principal elemento de interacción con
  el contenido.
- La inspiración conceptual proviene de aplicaciones como Adobe Bridge,
  sin intentar copiar su interfaz.
- La interfaz evolucionará hacia un **sistema de paneles independientes
  y configurables**, permitiendo al usuario organizar su espacio de
  trabajo.
- El crecimiento se realizará mediante **pequeñas mejoras acumulativas**,
  evitando rediseños completos que requieran refundar la arquitectura.

---

## Principios de diseño

Estos principios guían permanentemente las decisiones de implementación:

- **Actualización parcial.** Siempre que sea técnicamente posible, la
  interfaz debe actualizar únicamente el componente afectado, sin
  reconstruir partes no modificadas.
- **Evitar reconstrucciones completas** cuando una actualización parcial
  sea suficiente.
- **Reutilizar la caché** antes de regenerar información que ya existe.
- **Evitar operaciones costosas** cuando exista una alternativa
  equivalente más eficiente.
- **Persistir automáticamente** las preferencias del usuario cuando
  resulte razonable hacerlo.
- **Priorizar la exploración visual** sobre la reproducción en todas
  las decisiones de producto.

---

## Interacción con previews

Ideas registradas para etapas futuras:

- Elegir manualmente uno o varios fotogramas para reemplazar previews
  automáticas.
- Permitir fijar previews manuales para impedir su regeneración
  automática.
- Doble clic sobre una preview para reproducir el video desde ese
  instante.
- Utilizar VLC como reproductor preferente para funciones avanzadas
  relacionadas con previews.
- Seleccionar dos previews para reproducir únicamente el segmento
  comprendido entre ambas.
- Incorporar una opción configurable para ampliar y reproducir una
  preview al posar el mouse.

---

## Marcadores temporales como función de navegación

Decisión de producto (cerrada en la validación de la B4.1):

- Los **marcadores temporales** son una **función permanente de navegación
  del producto**, no exclusivamente puntos de corte.
- Un marcador representa un **instante significativo dentro de un video**,
  un punto al que el usuario quiera regresar días o meses después.
- Deberán permitir, en etapas futuras, **iniciar reproducción desde el
  marcador** y actuar como **destino seleccionable durante la reproducción**
  para saltar exactamente a ese instante (navegación entre marcadores
  durante la reproducción).
- Los marcadores se asocian a los videos del catálogo de forma **permanente**:
  desde la **B4.2** se persisten en SQLite (`marcadores_video`, relacionados
  mediante `videos.id`) y reaparecen entre sesiones; pueden eliminarse
  permanentemente y recuperan su representación visual con las previews
  disponibles.
- Los mismos puntos podrán participar posteriormente en **selección A/B,
  loops, selección de fragmentos o corte/unión**, pero eso es otra función:
  el marcador conserva su significado de navegación.
- **Conservación de datos del usuario**: la persistencia es deliberadamente
  no destructiva — si el registro del video desaparece, los marcadores **no**
  se eliminan automáticamente (pueden quedar huérfanos) y su **reasociación**
  a archivos movidos/renombrados (o por nombre/ruta) es una **función
  futura**, para evitar pérdida automática de datos creados por el usuario.

---

## Herramientas futuras

- Recorte de videos utilizando previews como puntos de inicio y fin.
- Unión de múltiples videos.
- Mantener como criterio general herramientas de edición basadas en
  escenas y previews, evitando interfaces complejas de línea de tiempo
  siempre que sea posible.
