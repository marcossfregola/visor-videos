# VISIÓN DE PRODUCTO — Visor de Videos

Este documento reúne las decisiones estratégicas, de producto y de diseño
que no pertenecen a la arquitectura técnica ni al estado del desarrollo.
Se actualiza mediante el cierre estratégico de hilos de trabajo (ver
`REGLAS_PROYECTO.md`, §13).

---

## Filosofía del producto

- El Visor de Videos debe mantenerse como un **explorador profesional
  basado en fotogramas representativos**.
- No debe evolucionar hacia un editor de video tradicional.
- Las **previews** constituyen el principal elemento de interacción con
  el contenido.

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
