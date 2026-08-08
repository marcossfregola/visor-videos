# VISIÓN DE PRODUCTO — Visor de Videos

> **DOCUMENTO HISTÓRICO (sustituido durante la adopción documental).** La fuente oficial vigente de identidad, visión, alcance y principios del producto es `PROJECT.md`. Este documento se conserva únicamente como referencia histórica; su contenido puede estar desactualizado y no debe usarse para determinar el estado vigente.

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

## Herramientas futuras

- Recorte de videos utilizando previews como puntos de inicio y fin.
- Unión de múltiples videos.
- Mantener como criterio general herramientas de edición basadas en
  escenas y previews, evitando interfaces complejas de línea de tiempo
  siempre que sea posible.
