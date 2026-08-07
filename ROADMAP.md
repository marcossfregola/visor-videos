# ROADMAP

## Objetivo

Este documento reúne las funcionalidades previstas para el Visor de
Videos. No representa el estado actual del proyecto, sino la dirección
de desarrollo. El orden podrá cambiar según las decisiones
arquitectónicas.

> **Estado (Beta 3):** quedó **aprobado el alcance de la Beta 3** (Etapa
> B3.0, exclusivamente documental). El proyecto está listo para comenzar la
> implementación de los bloques de trabajo **A–E** definidos en la sección
> "Bloque de trabajo 3 — Beta 3". El Bloque de trabajo 2 (Centro de
> Navegación) quedó completado y aprobado.

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
- **Etapa 2.3** — Navegación completa del árbol. **Implementada.**
- **Etapa 2.4** — Selección de la carpeta actual. **Implementada.**
- **Etapa 2.5** — Persistencia del árbol (carpeta seleccionada y estado
  de expansión). **Implementada.**
- **Etapa 2.6** — Escaneo automático al seleccionar carpeta (preferencia
  independiente de "Incluir subcarpetas"). **Implementada.**
- **Etapa 2.7** — Integración con el pipeline existente de escaneo.
  **Implementada (etapa de verificación).**
- **Etapa 2.8** — Integración con "Incluir subcarpetas" (cuatro
  combinaciones posibles). **Implementada.**
- **Etapa 2.9** — Indicadores visuales de carpetas escaneadas.
  **Implementada.**
- **Etapa 2.10** — Filtrado del catálogo desde el árbol.

**Estado:** El Bloque de trabajo 2 quedó **completado** (Etapas 2.1 a 2.9,
incluida la verificación de la Etapa 2.7) y el Centro de Navegación fue
aprobado. La **Etapa 2.10** (filtrado del catálogo desde el árbol) queda
**diferida** y **no forma parte del alcance de la Beta 3**; se retomará en
una etapa posterior.

---

# Bloque de trabajo 3 — Beta 3

## Objetivo general

Implementar las mejoras aprobadas que surgieron durante la fase de uso real
de la Beta 2, organizadas en bloques de trabajo pequeños, verificables y
acumulativos, priorizando la exploración visual y sin adelantar
funcionalidades fuera del alcance acordado.

## Filosofía de la Beta 3

- Mantiene la filosofía del producto (`VISION_PRODUCTO.md`): la **exploración
  visual** es el objetivo principal y la **reproducción** permanece como
  función secundaria.
- Se implementan **pequeñas mejoras acumulativas**, sin rediseños completos ni
  cambios arquitectónicos que todavía no existen.
- Las preferencias nuevas que surjan de la Beta 3 se **persistirán
  automáticamente** siguiendo el patrón existente.
- Ninguna mejora del alcance aprobado está aún implementada; el desarrollo
  comenzará tras la aprobación de esta etapa.

## Alcance

La Beta 3 cubre **exclusivamente** las mejoras aprobadas de los bloques de
implementación **A–E**. Las funcionalidades no incluidas en esos bloques
quedan **expresamente excluidas** (ver sección "Funcionalidades excluidas").
No se implementará ninguna mejora fuera de este alcance.

## Bloques de implementación

### A. Experiencia visual

- Tiempo sobre las miniaturas. **Implementada (Etapa B3.1).**
- Duración simplificada. **Implementada (Etapa B3.2).**
- Tamaño configurable de miniaturas. **Implementada (Etapa B3.3).**
- Vista ampliada al posar el mouse. **Implementada (Etapa B3.4).**
- Preferencias relacionadas con miniaturas. **Implementada (Etapa B3.5).**
- Tamaño "Muy grande" (512×288) — ampliación del tamaño configurable.
  **Implementada (Etapa B3.6).**
- Tamaño configurable de la vista ampliada (factores 1.2/1.6/2.0/2.5, default 1.6) —
  ampliación de A4. **Implementada (Etapa B3.7).**
- Generación automática de previews faltantes al aumentar la cantidad configurada —
  ampliación de A1. **Implementada (Etapa B3.8).** Al incrementar la cantidad (p. ej.
  3→5), la aplicación genera únicamente las previews inexistentes en segundo plano y
  actualiza las tarjetas afectadas, sin volver a escanear; al disminuir solo oculta.
- Pulido técnico del Bloque A. **Completado (Etapa B3.9).** Mejoras internas sin
  funcionalidades nuevas: acotado de los pixmaps originales retenidos en memoria
  (límite 1280, sin releer disco ni regenerar, calidad preservada), transición limpia
  del popup entre miniaturas distintas, helper reutilizable `_duracion_valida` y
  eliminación de constantes realmente muertas.
- Opción "Desactivado" para la vista ampliada (ampliación de A4). **Implementada
  (Etapa B3.14a).** En el retardo de la vista ampliada se agrega el valor discreto
  "Desactivado" (`-1`): con él nunca se inicia el timer ni aparece el popup al posar el
  mouse; volver a cualquier retardo reactiva la funcionalidad. Persistido con la
  infraestructura existente (configs anteriores compatibles; inválido → 400 ms).
- Tamaños grandes de la vista ampliada (3.0x y 3.5x) — ampliación de A7.
  **Implementada (Etapa B3.14b).** El factor máximo pasa a ser 3.5x (puede ocupar
  prácticamente toda la pantalla, acotado por `_posicion_vista`); sin tratamiento
  especial para los nuevos factores (infraestructura por datos; default 1.6).

### B. Selección y operaciones

- Modo selección.
- Checks por fila.
- Copiar.
- Pegar. **Implementada (Etapa B3.15).**
- Eliminar. **Implementada (Etapa B3.16).**
- Resumen de selección.
- Atajos de teclado. **Implementada (Etapa B3.17).**
- Corrección técnica del Bloque B (punto I1 de la auditoría). **Completada (Etapa B3.18).**
  Captura de la carpeta al inicio de la resincronización incremental de Pegar/Eliminar
  (override `_carpeta_sincronizacion` consumido por `_iniciar_sincronizacion`), eliminando
  la condición de carrera detectada en la auditoría del Bloque B sin modificar el
  comportamiento normal del pipeline.

### C. Progreso

- Barra de progreso real.
- Cantidad de videos procesados.
- Porcentaje.
- Cancelación del escaneo — **pendiente de evaluación técnica**; no es una
  mejora aprobada.

#### Orden de implementación del Bloque C (aprobado en B3.19)

| Etapa | Contenido |
| --- | --- |
| B3.20 | **Infraestructura de progreso** — señal `progreso` en `TareaBase` y `tarea_progreso` en `GestorTareas`, reenvío por `_RelayTarea` con token `_vigente`, helper `reportar_progreso`; cambio aditivo sin modificar `ejecutar()` ni el comportamiento visible. **Implementada (Etapa B3.20).** |
| B3.21 | **Progreso real del pipeline de escaneo** — usar la infraestructura en la cadena principal (tamaños, FFprobe, miniaturas, guardado, sincronización, recarga). **Implementada (Etapa B3.21):** progreso real en tamaños, FFprobe, miniaturas y guardado mediante **callbacks opcionales** en las funciones puras de `escanear_videos` (sin Qt ni bucles movidos a las tareas); escaneo, sincronización y recarga permanecen indeterminados por decisión. La barra pasa a determinada durante esas etapas. |
| B3.22 | **Progreso de Copiar, Pegar y Eliminar** — reutilizar la misma infraestructura, sin lógica paralela. **Implementada (Etapa B3.22):** callbacks opcionales `on_progreso` en `copiar_archivos`, `pegar_archivos` y `eliminar_archivos`; las tres tareas pasan `self.reportar_progreso`; `gestor_operaciones.tarea_progreso` se conecta al mismo handler `_al_progreso_pipeline`; exclusión mutua entre operaciones y pipeline en handlers y habilitación de botones. |
| B3.23 | **Pulido visual del sistema de progreso** — consistencia barra ↔ mensajes de estado, evitar mensajes pisados, unificar comportamiento visual. **Implementada (Etapa B3.23):** formato detallado `"{etapa} %v de %m (%p%)"` con los placeholders nativos de `QProgressBar` (nombre de etapa + "N de M" + porcentaje), aplicado una sola vez por etapa en `_al_progreso_pipeline`; `_mostrar_progreso` guarda `_texto_progreso` y reinicia `_progreso_detallado`; las etapas sin emisión (escaneo, sincronización, recarga) siguen indeterminadas con texto simple. Sin cambios en tareas ni infraestructura. |
| B3.24 | **Limpieza técnica** — deuda que continúe siendo necesaria (`_pipeline_activo`, helpers repetidos, etc.). |
| B3.25 | **Feedback de previews** — diferido; solo si continúa aportando valor tras el resto del Bloque C. |

### D. Navegación

- Reinicio de indicadores de carpetas escaneadas.
- Persistencia de nuevas preferencias.

### E. Integración con el reproductor

- Apertura del video desde una preview (doble clic sobre una miniatura).

## Mejoras aprobadas

Mejoras aprobadas para la Beta 3, en correspondencia con los bloques:

1. **A1 — Tiempo sobre las miniaturas** (Bloque A).
2. **A2 — Duración simplificada** (Bloque A).
3. **A3 — Tamaño configurable de miniaturas** (Bloque A).
4. **A4 — Vista ampliada al posar el mouse** (Bloque A).
5. **A5 — Preferencias relacionadas con miniaturas** (Bloque A).
6. **B1 — Modo selección** (Bloque B).
7. **B2 — Checks por fila** (Bloque B).
8. **B3 — Copiar** (Bloque B).
9. **B4 — Pegar** (Bloque B).
10. **B5 — Eliminar** (Bloque B).
11. **B6 — Resumen de selección** (Bloque B).
12. **B7 — Atajos de teclado** (Bloque B).
13. **C1 — Barra de progreso real** (Bloque C).
14. **C2 — Cantidad de videos procesados** (Bloque C).
15. **C3 — Porcentaje** (Bloque C).
16. **D1 — Reinicio de indicadores de carpetas escaneadas** (Bloque D).
17. **D2 — Persistencia de nuevas preferencias** (Bloque D).
18. **E1 — Apertura del video desde una preview** (Bloque E).

La **cancelación del escaneo** (Bloque C) queda **pendiente de evaluación
técnica** y **no forma parte de las mejoras aprobadas** de la Beta 3.

## Funcionalidades expresamente excluidas de la Beta 3

Quedan fuera del alcance de la Beta 3 y no se implementarán en ella:

- Favoritos, etiquetas, colecciones, recientes y últimos escaneos
  (organización del catálogo).
- Tarjetas expandibles (entre 20 y 30 previews por video al expandir).
- Ordenamientos del catálogo (por nombre, duración, resolución, codec, tamaño
  o fecha).
- Paginación completa automática (scroll infinito, búsqueda en SQL desde la
  interfaz y ordenamiento configurable).
- Deduplicación de nombres repetidos en el plan de sincronización.
- Filtrado del catálogo desde el árbol (Etapa 2.10 del Bloque de trabajo 2),
  diferida a una etapa posterior.
- Calidad de miniaturas avanzada (selección inteligente de fotogramas, evitar
  pantallas negras, fundidos, créditos e imágenes repetidas).
- Panel de propiedades, panel de favoritos, panel de etiquetas y panel de IA.
- Administración (detección de archivos movidos, renombrado masivo,
  organización automática y detección de duplicados).
- IA (descripción y clasificación de videos, reconocimiento de escenas, OCR,
  reconocimiento de rostros y objetos, plugins o extensiones y múltiples
  vistas del catálogo).

## Tabla de seguimiento de las mejoras

| ID | Mejora | Bloque | Estado |
| --- | --- | --- | --- |
| A1 | Tiempo sobre las miniaturas | A | Implementada |
| A2 | Duración simplificada | A | Implementada |
| A3 | Tamaño configurable de miniaturas | A | Implementada |
| A4 | Vista ampliada al posar el mouse | A | Implementada |
| A5 | Preferencias relacionadas con miniaturas | A | Implementada |
| A6 | Tamaño "Muy grande" (ampliación de A3) | A | Implementada |
| A7 | Tamaño configurable de la vista ampliada (ampliación de A4) | A | Implementada |
| A8 | Generación automática de previews faltantes (ampliación de A1) | A | Implementada |
| A9 | Desactivar la vista ampliada (ampliación de A4) | A | Implementada |
| A10 | Tamaños grandes de la vista ampliada (ampliación de A7) | A | Implementada |
| B1 | Modo selección | B | Implementada |
| B2 | Checks por fila | B | Implementada |
| B3 | Copiar | B | Implementada |
| B4 | Pegar | B | Implementada |
| B5 | Eliminar | B | Implementada |
| B6 | Resumen de selección | B | Implementada |
| B7 | Atajos de teclado | B | Implementada |
| C1 | Barra de progreso real | C | Pendiente |
| C2 | Cantidad de videos procesados | C | Pendiente |
| C3 | Porcentaje | C | Pendiente |
| D1 | Reinicio de indicadores de carpetas escaneadas | D | Pendiente |
| D2 | Persistencia de nuevas preferencias | D | Pendiente |
| E1 | Apertura del video desde una preview | E | Pendiente |

## Bloque B — Selección y operaciones (plan aprobado, Etapa B3.10)

### Objetivo

Ampliar la selección del catálogo con un **modo de selección dedicado** (checks por
fila), un **resumen del estado de la selección**, **operaciones de archivos** sobre
los seleccionados (copiar, pegar y eliminar) y **atajos de teclado**, manteniendo
intacto el comportamiento del modo normal.

### Orden de implementación

| Etapa | Contenido |
| --- | --- |
| B3.11 | **Resumen de selección** (B6) — "n de m seleccionados", sincronizado con la selección y el filtro. **Implementada (Etapa B3.11).** |
| B3.12 | **Modo selección + Checks por fila** (B1 + B2) — toggle en la barra que activa checks por fila sincronizados con la selección; el modo normal no cambia. **Implementada (Etapa B3.12).** |
| B3.13 | **Atajos básicos** (B7, parcial) — Ctrl+A (todo lo visible) y Esc (salir del modo selección). **Implementada (Etapa B3.13).** |
| B3.14 | **Copiar** (B3) — copiar los archivos de video seleccionados a una carpeta destino (diálogo), en segundo plano, sin sobrescribir. **Implementada (Etapa B3.14).** |
| B3.15 | **Pegar** (B4) — pegar en la carpeta actual los archivos copiados internamente, con confirmación de colisión. **Implementada (Etapa B3.15).** |
| B3.16 | **Eliminar** (B5) — mover a la Papelera de reciclaje (nunca borrado permanente) con confirmación y resumen. **Implementada (Etapa B3.16).** |
| B3.17 | **Atajos de operaciones** (B7, parcial) — Ctrl+C / Ctrl+V / Supr vinculados a Copiar/Pegar/Eliminar. **Implementada (Etapa B3.17).** |
| B3.18 | **Corrección técnica del Bloque B** — capturar la carpeta en la resincronización incremental de Pegar/Eliminar (override `_carpeta_sincronizacion`). **Implementada (Etapa B3.18).** |

### Dependencias

- **Checks por fila** dependen del **modo selección**.
- El **resumen** depende únicamente del estado interno de selección (ya existente y
  validado); se implementa primero para verificar ese modelo antes de incorporar los
  checks.
- **Pegar** depende de la semántica de **Copiar**.
- Los **atajos de operaciones** dependen de **Copiar/Pegar/Eliminar**.

### Decisiones congeladas

- **Copiar** = copiar archivos físicos.
- **Pegar** = portapapeles interno de la aplicación.
- **Eliminar** = mover únicamente a la Papelera de reciclaje.
- Todas las operaciones de archivos se ejecutan **en segundo plano**.
- El **modo selección no modifica** el comportamiento del modo normal.

### Excluidos del Bloque B

Renombrado masivo, favoritos, etiquetas, organización automática, detección de
duplicados, filtros avanzados y apertura del video desde previews.

### Seguimiento

La tabla de seguimiento del Bloque B es la correspondiente a las mejoras **B1–B7**
de la tabla anterior (todas en estado "Pendiente"), con el orden de implementación
indicado arriba.

---

# Bloque de trabajo 4 — Catálogo por selección de carpetas

## Objetivo

Permitir que el catálogo se construya a partir de **múltiples carpetas seleccionadas por el
usuario** (p. ej. las primeras 20/50/100 de cientos de carpetas numeradas), con la experiencia
de uso como prioridad absoluta. El modelo aprobado: la selección se almacena **siempre como un
conjunto de rutas** (los intervalos son solo una forma rápida de construirla) y conviven dos
conceptos: **carpeta activa** (navegación/abrir) y **carpetas seleccionadas** (para formar el
catálogo). El checkbox "Incluir subcarpetas" evoluciona a un selector de modo ("Solo carpeta
actual" / "Carpeta actual y todas las subcarpetas" / "Selección personalizada…").

## Decisiones aprobadas

- Selección interna siempre por rutas (nunca intervalos); "Seleccionar hasta aquí" es una
  operación principal (primeras N de colecciones numeradas).
- Modo dedicado de selección de carpetas; carpeta activa ≠ carpetas seleccionadas.
- Herramientas de selección rápida: Seleccionar todas, Deseleccionar todas, Primeras N,
  Últimas N, Desde X hasta Y, Invertir; menú contextual (Seleccionar/Deseleccionar: esta,
  hasta aquí, desde aquí hasta el final); Shift+clic como complemento.
- Pendiente de resolver antes del escaneo multicarpeta: deduplicación de nombres de archivo
  entre carpetas (`nombre` UNIQUE), clave de orden natural, semántica de cascada.

## Orden de implementación

| Etapa | Contenido |
| --- | --- |
| 1 | **Infraestructura de selección** — conjunto de rutas (única fuente de verdad), persistencia en configuración, restauración al iniciar con descarte de rutas inexistentes, API `seleccionar`/`deseleccionar`/`alternar`/`limpiar`/`seleccionar_todas`/`obtener_seleccion`. Sin árbol, sin UI, sin cambios en escaneo/SQLite/pipeline. **Implementada.** |
| 2-3 | **Modo de selección en el árbol + herramientas de selección rápida** — entrega conjunta (Etapas 2 y 3). Modo de selección (toggle) con checks por nodo que reflejan `SeleccionCarpetas`, estado "seleccionada" distinto de "activa", sin alterar navegación ni carpeta activa; acciones masivas (Seleccionar todas del nivel, Deseleccionar todas, Invertir nivel) y menú contextual (Seleccionar/Deseleccionar: hasta aquí, desde aquí hasta el final). Las acciones materializan rutas en el conjunto, sin intervalos ni estructuras paralelas. **Implementada (entrega conjunta Etapas 2-3).** |
| 4 | **Escaneo de la selección** — `iniciar_escaneo` soporta los tres modos; pipeline sobre la unión de la selección; progreso "carpeta N de M". Requiere resolver la deduplicación de nombres. |
| 5 | **Sincronización de la selección** — reconciliación por carpeta del alcance; indicadores por carpeta. |
| 6 | **Selector de modo** — reemplazo del checkbox "Incluir subcarpetas" con migración retrocompatible. |
| 7 | **Auditoría final** — UX, escala, regresiones integrales. |

---

# Prioridad inmediata

-   ~~Opción de incluir o excluir subcarpetas en el escaneo.~~ Implementada
    con persistencia de la preferencia entre ejecuciones.
-   ~~Infraestructura de paneles (QSplitter).~~ Implementada.
-   ~~Árbol de carpetas en el panel izquierdo.~~ Implementadas las Etapas 2.1 a
    2.9 (árbol con "Este equipo", discos, carpetas con carga diferida,
    selección funcional, integración con la carpeta activa, persistencia,
    escaneo automático al seleccionar, verificación de la paridad de
    subcarpetas, preferencia independiente de escaneo automático con las
     cuatro combinaciones e indicadores visuales de carpetas escaneadas). El
     bloque de trabajo 2 queda **completado**; el desarrollo funcional se
     retoma con la implementación de la Beta 3 (ver Bloque de trabajo 3).
-   Paginación completa automática del catálogo — scroll infinito,
    búsqueda en SQL desde la interfaz y ordenamiento configurable. La
    carga manual de una página adicional con el botón "Cargar más" ya
    existe.
-   Deduplicación de nombres repetidos en el plan de sincronización.
-   Persistencia de preferencias generales de configuración — más allá
    de la última carpeta seleccionada, que ya se persiste. **Prevista en la
    Beta 3** (Bloque de trabajo 3, Bloque D — "Persistencia de nuevas
    preferencias").

------------------------------------------------------------------------

# Experiencia de usuario

-   ~~Barra de progreso.~~ Implementada.
-   ~~Selección visual de filas (simple, Ctrl+clic y Shift+clic).~~ Implementada.
    Incluye acciones mediante menú contextual (abrir, abrir carpeta, copiar ruta,
    copiar rutas de los seleccionados, abrir carpetas de los seleccionados),
    restauración automática de la selección tras reconstruir tarjetas y selección
    por rango con Shift+clic basada en ancla y orden visible.
-   Cancelación de tareas — la **cancelación del escaneo** está **pendiente de
    evaluación técnica** en la Beta 3 (Bloque de trabajo 3, Bloque C); no es
    una mejora aprobada.
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
