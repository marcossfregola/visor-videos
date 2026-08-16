# ROADMAP

## Objetivo

Este documento reúne las funcionalidades previstas para el Visor de
Videos. No representa el estado actual del proyecto, sino la dirección
de desarrollo. El orden podrá cambiar según las decisiones
arquitectónicas.

> **Estado (Beta 4):** la **Beta 3 quedó finalizada, funcionalmente cerrada y
> congelada sobre el código definitivo**, con su instalador generado y pendiente
> únicamente de la **validación manual integral** y su publicación (la Beta 2
> permanece como la última versión estable publicada). El desarrollo funcional
>    se reanudó en el **ciclo Beta 4** (rama `beta4`): las etapas **B4.1 —
> Exploración temporal interactiva y marcadores visuales**, **B4.2 —
> Persistencia de marcadores temporales por video**, **B4.3.1 — Motor de
> caché temporal versionada y reanudable**, **B4.3.2 — Cobertura rápida
> asíncrona integrada con la UI**, **B4.3.2 — Etapa 2: Densidad secundaria
> adaptativa**, **B4.3.3 — Ajustes de interacción y densidad manual**,
> **B4.4 — Reproducción de marcadores en VLC**, **B4.5 — Rendimiento de
> carga inicial (diagnóstico, eliminación de FFprobe redundante y
> reutilización de metadata en reescaneos)** y **B4.6 — Rendimiento de
> carga visual (diagnóstico y carga diferida de previews)** quedaron
> **completadas y aprobadas** (ver la sección "Beta 4").
> Adicionalmente se incorporó una mejora de diagnóstico (no una etapa
> formal): **identificación visible de versión/build** en la status bar de la
> ventana principal (`Beta 4 — B4.12`), para identificar rápidamente la build
> en ejecución en cualquier PC (p. ej. la notebook de validación).
> **Beta 4 CERRADA y aprobada (2026-08-10).** Build final **`Beta 4 — B4.12`** (commit técnico
> `198cdf533986b88c6e25dc0087722cf2b86e5f99`; instalador `VisorVideos_Beta4_Setup.exe`, SHA-256
> `730B4DAB1CD2F1F5CFDD184D2DC6FE80CF0481B8754080F0FF10CF991F89431F`), validada en la notebook
> objetivo (B4.11: validación manual amplia; B4.12: validación final corta). Suite integral
> posterior a las correcciones: **87 suites / 1570/1570 OK / 0 FAIL funcional**. **Beta 5
> CERRADA internamente (cierre formal 2026-08-15, rama `beta5`):** commit técnico principal
> `969efcd9d71e78c1ca538bfa238a3e27f1484d9e`; instalador interno validado
> `VisorVideos_Beta5_ValidacionFinal_Setup.exe` (SHA-256
> `F40ACF41FE7D3931FF042AC718B6D2805460AE380092E9E782A918C42A650133`), aprobado en la notebook
> objetivo; identidad definitiva **`Beta 5 — B5.0`**. Etapas **B5.1–B5.9** completadas más los
> pulidos finales (drag de creación, edición de extremos, scroll local de previews). **Sin
> distribución pública; sin merge a `main`; sin GitHub Release** (ver la sección "Beta 5").

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
- La Beta 3 quedó **completa y congelada**: todas las mejoras aprobadas del
  alcance **A–E** (incluidas las ampliaciones posteriores A6–A10), el **Bloque
  de trabajo 4** (catálogo por selección de carpetas) y las correcciones finales
  fueron implementadas, verificadas y cerradas.

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

- Modo selección. **Implementada (Etapa B3.12).**
- Checks por fila. **Implementada (Etapa B3.12).**
- Copiar. **Implementada (Etapa B3.14).**
- Pegar. **Implementada (Etapa B3.15).**
- Eliminar. **Implementada (Etapa B3.16).**
- Resumen de selección. **Implementada (Etapa B3.11).**
- Atajos de teclado. **Implementada (Etapa B3.17).**
- Corrección técnica del Bloque B (punto I1 de la auditoría). **Completada (Etapa B3.18).**
  Captura de la carpeta al inicio de la resincronización incremental de Pegar/Eliminar
  (override `_carpeta_sincronizacion` consumido por `_iniciar_sincronizacion`), eliminando
  la condición de carrera detectada en la auditoría del Bloque B sin modificar el
  comportamiento normal del pipeline.

### C. Progreso

- Barra de progreso real. **Implementada (Etapas B3.20–B3.23).**
- Cantidad de videos procesados. **Implementada (Etapas B3.20–B3.23).**
- Porcentaje. **Implementada (Etapas B3.20–B3.23).**
- Cancelación del escaneo — **diferida**: no formó parte del alcance aprobado
  de la Beta 3 (no es una mejora aprobada) y no se incluye en el cierre;
  permanece abierta para etapas futuras.

#### Orden de implementación del Bloque C (aprobado en B3.19)

| Etapa | Contenido |
| --- | --- |
| B3.20 | **Infraestructura de progreso** — señal `progreso` en `TareaBase` y `tarea_progreso` en `GestorTareas`, reenvío por `_RelayTarea` con token `_vigente`, helper `reportar_progreso`; cambio aditivo sin modificar `ejecutar()` ni el comportamiento visible. **Implementada (Etapa B3.20).** |
| B3.21 | **Progreso real del pipeline de escaneo** — usar la infraestructura en la cadena principal (tamaños, FFprobe, miniaturas, guardado, sincronización, recarga). **Implementada (Etapa B3.21):** progreso real en tamaños, FFprobe, miniaturas y guardado mediante **callbacks opcionales** en las funciones puras de `escanear_videos` (sin Qt ni bucles movidos a las tareas); escaneo, sincronización y recarga permanecen indeterminados por decisión. La barra pasa a determinada durante esas etapas. |
| B3.22 | **Progreso de Copiar, Pegar y Eliminar** — reutilizar la misma infraestructura, sin lógica paralela. **Implementada (Etapa B3.22):** callbacks opcionales `on_progreso` en `copiar_archivos`, `pegar_archivos` y `eliminar_archivos`; las tres tareas pasan `self.reportar_progreso`; `gestor_operaciones.tarea_progreso` se conecta al mismo handler `_al_progreso_pipeline`; exclusión mutua entre operaciones y pipeline en handlers y habilitación de botones. |
| B3.23 | **Pulido visual del sistema de progreso** — consistencia barra ↔ mensajes de estado, evitar mensajes pisados, unificar comportamiento visual. **Implementada (Etapa B3.23):** formato detallado `"{etapa} %v de %m (%p%)"` con los placeholders nativos de `QProgressBar` (nombre de etapa + "N de M" + porcentaje), aplicado una sola vez por etapa en `_al_progreso_pipeline`; `_mostrar_progreso` guarda `_texto_progreso` y reinicia `_progreso_detallado`; las etapas sin emisión (escaneo, sincronización, recarga) siguen indeterminadas con texto simple. Sin cambios en tareas ni infraestructura. |
| B3.24 | **Limpieza técnica** — deuda que continúe siendo necesaria (`_pipeline_activo`, helpers repetidos, etc.). **No implementada:** diferida fuera del cierre de la Beta 3. |
| B3.25 | **Feedback de previews** — diferido; solo si continúa aportando valor tras el resto del Bloque C. **Descartado** del cierre de la Beta 3. |

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
| C1 | Barra de progreso real | C | Implementada (B3.20–B3.23) |
| C2 | Cantidad de videos procesados | C | Implementada (B3.20–B3.23) |
| C3 | Porcentaje | C | Implementada (B3.20–B3.23) |
| D1 | Reinicio de indicadores de carpetas escaneadas | D | Diferida (no forma parte del cierre) |
| D2 | Persistencia de nuevas preferencias | D | Implementada |
| E1 | Apertura del video desde una preview | E | Implementada (preexistente: doble clic sobre la tarjeta) |

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
de la tabla anterior (todas en estado **"Implementada"**, con la corrección técnica
B3.18 incluida), con el orden de implementación
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
| 4 | **Escaneo de la selección** — `iniciar_escaneo` soporta los tres modos; pipeline sobre la unión de la selección; progreso "carpeta N de M". **Implementada (Etapa 4):** `iniciar_escaneo(carpetas=None)` acepta una lista y encadena el pipeline existente **una vez por carpeta** (cola secuencial `_cola_carpetas_escaneo`), con deduplicación de carpetas y modo tradicional idéntico. |
| 5 | **Sincronización multicarpeta** — reconciliación **por cada carpeta del alcance** con protección de las demás raíces del mismo alcance; indicadores por carpeta. **Implementada (Etapa 5):** eliminado por completo `_omite_sincronizacion`; `_alcance_sincronizacion` (mismo conjunto efectivo que la cola de escaneo); sincronización **por ruta** en modo multicarpeta (`detectar_diferencias(..., carpetas_protegidas=...)` con `_es_subcarpeta`), de modo que una carpeta no elimina registros de otras raíces del alcance y el modo tradicional (una carpeta) permanece idéntico; **normalización del alcance efectivo** cuando "Incluir subcarpetas" está activado (se eliminan las raíces descendientes redundantes contenidas en otra del alcance, con `_alcance_efectivo`/`_ruta_contiene`, comparación robusta con `os.path.commonpath`); transición correcta A → A+B → A. Sin cambios de esquema SQLite. |
| 6 | **Selector de modo (unificación del alcance)** — reemplazo del checkbox "Incluir subcarpetas" por un único selector de alcance. **Implementada (Etapa 6):** `QComboBox` con tres modos — "Solo carpeta actual", "Carpeta actual y todas las subcarpetas" y "Selección personalizada" (que reutiliza la infraestructura del Bloque 4 y activa el modo de selección del árbol) — como **única fuente de verdad** del alcance; persistencia (`modo_alcance`) y **migración retrocompatible** desde el booleano `incluir_subcarpetas`; el checkbox anterior queda únicamente como **adaptador de compatibilidad oculto** (no visible; sincronizado con el modo). Sin cambios en el motor de escaneo ni en la sincronización. |
| 7 | **Auditoría integral del Bloque 4 y cierre funcional de la Beta 3** — UX, escala, regresiones integrales. **Completada (Etapa 7):** auditoría final del Bloque 4 con la batería completa de suites; se detectó y corrigió la regresión de `_duracion_valida` (`duracion > 0`, la duración 0 es inválida) introducida en la refinación de la Etapa 5; se incorporó la verificación integrada de transiciones de modo; la **Beta 3 queda funcionalmente cerrada** (congelada sobre el código definitivo). Posteriormente se reconstruyó la infraestructura oficial de empaquetado (`instalador.iss` + `EMPACADO.md`) y se generó el instalador definitivo; resta únicamente la **validación manual integral**. |

---

# Prioridad inmediata

-   ~~Opción de incluir o excluir subcarpetas en el escaneo.~~ Implementada.
    El antiguo checkbox "Incluir subcarpetas" fue reemplazado por el **selector
    de alcance** — "Solo carpeta actual" / "Carpeta actual y todas las
    subcarpetas" / "Selección personalizada" — como única fuente de verdad
    (Bloque de trabajo 4, Etapa 6).
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
-   ~~Persistencia de preferencias generales de configuración~~ — más allá
    de la última carpeta seleccionada, que ya se persiste. **Implementada**
    durante la Beta 3 (tamaño de miniaturas, retardo y factor de la vista
    ampliada, modo de alcance y selección de carpetas, entre otras).

------------------------------------------------------------------------

# Experiencia de usuario

-   ~~Barra de progreso.~~ Implementada.
-   ~~Selección visual de filas (simple, Ctrl+clic y Shift+clic).~~ Implementada.
    Incluye acciones mediante menú contextual (abrir, abrir carpeta, copiar ruta,
    copiar rutas de los seleccionados, abrir carpetas de los seleccionados),
    restauración automática de la selección tras reconstruir tarjetas y selección
    por rango con Shift+clic basada en ancla y orden visible.
-   Cancelación de tareas — la **cancelación del escaneo** quedó **diferida**:
    no formó parte del alcance aprobado de la Beta 3 y no se incluye en el
    cierre; permanece abierta para etapas futuras.
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

------------------------------------------------------------------------

# Beta 4

La Beta 4 recoge las mejoras y correcciones detectadas durante la validación manual
y el uso real de la Beta 3, priorizando la **inspección rápida de videos largos**
para localizar qué fragmentos sirven y cuáles pueden descartarse. El ciclo se
desarrolla sobre la rama `beta4` (punto de partida: cierre de la Beta 3).

## Secuencia de etapas

1. **B4.1 — Exploración temporal interactiva y marcadores visuales.** **Completada.**
   Tarjeta expandible con **superficie temporal** que representa la duración completa
   del video (0–100 %): marcador móvil que acompaña al cursor, tiempo de la posición,
   preview existente más cercana al instante y **preview móvil** que acompaña
   horizontalmente al cursor. Múltiples **marcadores temporales libres** (tiempo real +
   marca visual + miniatura fijada, con solapamiento permitido) y eliminación individual
   con clic derecho. Sin persistencia todavía (responsabilidad de B4.2).
2. **B4.2 — Persistencia de marcadores temporales por video.** **Completada.** Los
   marcadores se guardan **permanentemente en SQLite** (tabla `marcadores_video`: `id`,
   `video_id`, `tiempo`, con el índice `idx_marcadores_video_video_id_tiempo`), relacionados
   mediante **`videos.id`**; reaparecen entre sesiones, pueden eliminarse permanentemente y
   recuperan su representación visual con las previews disponibles. Sin cascade automático.
   Política de conservación: reescaneo del mismo registro, cambios de metadatos y reemplazo
   silencioso del mismo registro conservan los marcadores; si el registro del video desaparece
   los marcadores **no** se eliminan automáticamente (pueden quedar huérfanos; la reasociación
   por nombre/ruta o de movidos/renombrados es futura). La carga desde SQLite se trata como
   snapshot potencialmente antiguo y se reconcilia contra el estado local optimista, sin
   perder altas/bajas pendientes.
3. **B4.3 — Caché densa de exploración temporal.** Mejorar la resolución visual del scrubbing
   reemplazando la dependencia de las pocas previews normales por una **caché específica de
   fotogramas temporales** (fotogramas de exploración densa). Se divide en dos subetapas:
   - **B4.3.1 — Motor de caché temporal versionada y reanudable.** **Completada.** Motor de
     disco en `exploracion_cache.py` (nuevo): estructura
     `miniaturas/exploracion/<video_id>/<version_fingerprint>/` (`meta.json` + `f{ms:010d}.jpg`);
     **versiones aisladas** por *fingerprint* de metadatos baratos (ruta normalizada + tamaño +
     `mtime_ns` + duración; SHA-256 reducido a 16 hex; **no** es hash de contenido);
     **reanudación** de generaciones incompletas (escritura atómica temporal → `os.replace`;
     un JPEG presente está completo; p. ej. 8/20 reutiliza 8 y genera 12); **invalidación no
     destructiva** (un cambio del fingerprint crea una versión distinta; nada se borra
     automáticamente; `meta.json` solo se escribe al completar); **un FFmpeg por fotograma**
     (`-ss` + `-frames:v 1`) como **mecanismo actual de validación**, que **no será
     necesariamente el final** desde la UI. Sin UI, sin SQLite (`videos`, `marcadores_video`,
   `biblioteca.db` intactos) y sin acoplamiento con `escanear_videos`. Suites: B4.3.1
      **29/29** y regresiones B4.1 **28/28**, B4.2 **17/17**, previews **16/16**, smoke OK.
    - **B4.3.2 — Cobertura rápida asíncrona integrada con la UI (Etapa 1).** **Completada.** La
      tarjeta consume el motor de B4.3.1 con una **tarea asíncrona dedicada**
      (`TareaExploracionDensa`) que genera los **`FOTOGRAMAS_INICIALES = 15`** prioritarios y
      emite **resultados parciales progresivos** (`QImage` decodificada en el worker; conversión
      final a `QPixmap` en la GUI). **Fallback a las previews normales** mientras no hay caché y
      **mejora progresiva**; `mouseMove` con selección **exclusivamente en RAM**; imagen mostrada
      = la **más cercana** entre preview normal y densa (la preview normal gana el empate);
      **cancelación cooperativa**; **aislamiento A→B**; **colapso que libera las referencias
      densas de RAM**; **reexpansión que reutiliza la caché** (sin regenerar); los **marcadores**
      conservan su tiempo/id y mejoran visualmente. **Validación visual manual A–G aprobada por
      Marcos** en el PC de desarrollo y validada en la **notebook objetivo** (expansión y scrub
      correctos con un video real de ~56 min). Suites: B4.3.2 **20/20** y regresiones verdes.
    - **B4.3.2 — Etapa 2: Densidad secundaria adaptativa.** **Completada.** Tras el **benchmark de
      estrategias** sobre un video de 56 min (individual ≈7 s; batch por orden de cobertura ≈41 s
      → descartado; batch cronológico ≈10.5 s; pasada uniforme ≈10.8 s sin ventaja suficiente),
      por **decisión de producto** se adoptó la **generación individual y secuencial: un FFmpeg
      por objetivo, sin batch, sin paralelismo**. Los **15 prioritarios** se mantienen exactamente
      como en la Etapa 1 y la **fase secundaria** completa hasta el objetivo de densidad
      `objetivo_total_densidad(duración)` = `clamp(max(15, ceil(duración/30 s)), 15, 200)` —
      valores **provisionales** (30 s / mín 15 / máx 200), centralizados en `exploracion_cache.py`
      para exponerlos/configurarlos después, **sin controles visibles por ahora**. La fase
      secundaria solo arranca cuando termina la fase rápida (**sin solapamiento**), reutiliza los
      JPEG ya existentes (nunca regenera los presentes), es **progresiva** (`resultado_parcial`
      en ambas fases), **reanudable** y **cancelable** de forma cooperativa (cambiar/colapsar
      detiene la continuación; lo ya generado queda reutilizable). **Medidas de referencia en el
      PC de desarrollo** (video de ~56 min; no garantizan igualdad en la notebook): primer
      fotograma prioritario ≈**0.10 s**; **15 prioritarios ≈1.13 s**; primer secundario (16.º)
      ≈1.21 s (después de la fase rápida); **total 112 ≈8.39 s**; reexpansión con caché completa
      ≈**0.08 s sin regenerar**; scrub en RAM sin problema perceptible. **Notebook:** la Etapa 1
      ya fue validada en el hardware objetivo (i7-7500U / 16 GB RAM / 940MX) con un video real de
      ~56 min; la **Etapa 2** debe recibir una **comprobación visual sencilla** posterior
      (confirmar que la densidad secundaria no perjudica la fluidez); **NO se requiere una
      campaña adicional de benchmarks exhaustivos**. Suites: `prueba_exploracion_densidad_b432.py`
      **12/12** y regresiones verdes.
    - **B4.3.3 — Ajustes de interacción y densidad manual.** **Completada.** (A) **Prioridad
      visual dinámica**: durante el hover la preview dinámica queda **por encima** de las
      miniaturas fijas de marcadores (`raise_()` al mover el puntero; `lower()` al salir de la
      superficie); los marcadores conservan tiempo/id y su eliminación por clic derecho sigue
      funcionando; un marcador nunca tapa el instante que se está explorando. (B) **Densidad
      manual**: control `Auto | 15 | 30 | 60 | 120 | 200` en la tarjeta expandida; los valores
      manuales son el **total objetivo independiente de la duración** (video de 30 s: Auto → 15,
      manual 60 → 60, manual 120 → 120) — permite inspección fina de clips cortos; siempre los
      **15 prioritarios primero** y luego se completa hasta el total solicitado. **Aumentar**
      reutiliza lo existente (15→60 reutiliza 15 y genera 45; 60→120 reutiliza 60 y genera 60);
      **disminuir** no borra disco ni regenera (la RAM/UI se limita al conjunto objetivo
      `tiempos_objetivo(duración, cantidad_actual)`; la caché puede contener un **superset** y la
      tarea emite/decodifica solo el subconjunto permitido); **volver a Auto** recalcula el
      objetivo automático y conserva los extras de disco. Valor **por tarjeta/sesión** (persiste
      en colapso/reexpansión; vuelve a Auto si se reconstruye por recarga), **sin SQLite ni
      persistencia en `configuracion.json`** (la persistencia futura queda separada). Generación
      individual/secuencial en background, un solo FFmpeg activo, mouseMove exclusivamente RAM,
      colapso libera RAM y la caché permanece en disco. **B4.3 queda funcionalmente muy avanzada**;
      **no se declara la Beta 4 completa todavía**. Suites: `prueba_exploracion_b433.py` **22/22**
      y regresiones verdes.
4. **B4.4 — Reproducción de marcadores en VLC.** **Completada.** Los marcadores temporales son
   una **función permanente de navegación del producto** (no exclusivamente puntos de corte):
   representan un instante significativo al que el usuario quiera regresar.
   - **Etapa 1 — Inspección y prototipo técnico (playlist).** **Completada.** Validación física
     con **VLC 3.0.23** (`C:\Program Files\VideoLAN\VLC\vlc.exe`) de la estrategia **playlist
     pura**: una entrada por marcador con `#EXTVLCOPT:start-time=<segundos>`; los botones
     **Siguiente/Anterior visibles de VLC recorren los marcadores**; marcadores consecutivos del
     mismo archivo fluidos (sin negro/parpadeo perceptible); `--loop` correcto; controles
     normales intactos. Se descartó HTTP/telnet/libVLC para esta integración.
   - **Etapa 2 — Integración mínima "Reproducir marcadores en VLC".** **Completada.** El Visor
     permite **seleccionar uno o varios videos** y ejecutar **"Reproducir marcadores en VLC"**
     (menú contextual, habilitada con selección): lee los marcadores persistentes (B4.2) y
     genera una playlist temporal `.m3u` con **una entrada por marcador**
     (`#EXTVLCOPT:start-time`, **precisión decimal**, p. ej. `12.437`), en el **orden visible
     actual del catálogo** y con los marcadores de cada video en **orden cronológico
     ascendente**; abre **VLC una única vez** con la playlist completa. Videos sin marcadores →
     **diálogo por ocasión**: **Omitir videos sin marcadores** / **Reproducir desde el inicio
     (00:00)** / **Cancelar** (sin persistir la elección; si todos carecen y se elige Omitir, no
     abre VLC e informa que no hay marcadores). Archivos inexistentes → **omitidos con aviso**,
     sin borrar marcadores ni registros. VLC ausente → mensaje claro, sin instalar ni buscar
     discos. Playlists temporales `visor_marcadores_*.m3u` en el directorio temporal del sistema
     con encoding **UTF-8** (espacios, acentos y Unicode) y **limpieza propia antes de cada
     reproducción** (solo patrón propio, sin tocar archivos ajenos ni subdirectorios; una
     playlist bloqueada se conserva y se continúa; no se borra la recién lanzada). Sin HTTP, sin
     python-vlc/libVLC, sin automatización de teclas/botones, sin loop automático. **B4.4 queda
     completada; no se declara la Beta 4 completa todavía.** Evoluciones futuras (no
     implementadas): **iniciar reproducción desde el marcador**, ser **destino seleccionable
     durante la reproducción** y evaluar la UX de **múltiples instancias de VLC**. Suites:
      `prueba_reproduccion_marcadores_b44.py` **24/24** y regresiones verdes.
5. **B4.5 — Rendimiento de carga inicial.** **Completada (Etapa 1: diagnóstico; Etapa 2:
   eliminación de FFprobe redundante; Etapa 3: reutilización de metadata).** La demora perceptible de Marcos con carpetas de ~121
   videos (carga inicial, procesamiento y miniaturas normales) se investigó **sin tocar la
   exploración temporal B4.3**.
   - **Etapa 1 — Diagnóstico del cuello de botella.** **Completada.** Con un dataset temporal de
     121 videos funcionales (hardlinks de los videos reales de muestra) y base/caché temporales,
     se midió el costo por etapa del pipeline normal de catálogo/miniaturas en la PC de
     desarrollo: escaneo y tamaños despreciables; **FFprobe de metadata ~4.5 s (121 procesos,
     secuenciales)**; **miniaturas normales ~12.3 s** (121 FFmpeg + **121 FFprobe internos**);
     **previews normales ~38.6 s** (363 FFmpeg + **363 FFprobe internos**); SQLite y lectura
     despreciables; UI ~1.5 s (construcción de tarjetas + QPixmap en el hilo principal). El
     reescaneo con caché caliente re-ejecuta los **121 FFprobe de metadata de forma redundante**
     (~4.6 s de ~4.9 s). **Cuello dominante: FFmpeg+FFprobe de las previews normales (~70 % del
     tiempo en frío)**; secundarios: FFprobe redundante del reescaneo y el doble proceso
     (FFprobe interno por cada FFmpeg). Sin cambios de producción.
   - **Etapa 2 — Eliminar FFprobe redundante en generación normal de imágenes.** **Completada.**
     `generar_miniatura` y `generar_preview` aceptan `duracion_segundos=None`: si la duración es
     válida la usan sin ejecutar FFprobe interno (mismo cálculo temporal y mismo FFmpeg); si no,
     conservan el fallback FFprobe anterior. `asegurar_miniaturas` y `generar_previews_faltantes`
     aceptan un mapa de duraciones; `TareaMiniaturas`/`TareaPreviewsProgresivas` lo propagan; la
     interfaz lo construye desde `TareaFFprobe` (miniaturas) y desde la tarjeta (previews). En
     frío con 121 videos: **484 FFprobe internos → 0** (121 miniaturas + 363 previews), mismos
     484 FFmpeg; total backend **~55.6 s → ~37.1 s** (miniaturas 12.3→7.9 s, previews 38.6→24.8 s)
     como medición de la PC de desarrollo (no extrapolable a la notebook). Sin cambios de
     cantidad, posiciones, calidad, progresividad, lotes, caché, paralelismo ni FFmpeg. Suites:
     `prueba_optimizacion_ffprobe_b452.py` **14/14** y regresiones verdes.
    - **Próxima etapa registrada (no iniciada): B4.5 — Etapa 3 — evitar el FFprobe de metadata en
      reescaneos de videos sin cambios** (el reescaneo caliente ≈4.9 s con ~93 % en FFprobe). No
      se diseñó ni implementó todavía el criterio de reutilización.
    - **Etapa 3 — Reutilizar metadata en reescaneos de videos sin cambios.** **Completada.**
      Criterio barato **`ruta normalizada + tamano_bytes + mtime_ns`** (sin hash de contenido):
      se reutilizan `duracion_segundos`/`ancho`/`alto`/`codec_video` con **0 FFprobe** solo si
      existe registro previo por nombre, `mtime_ns` no es NULL, la ruta normalizada coincide, el
      tamaño coincide, el `mtime_ns` coincide y la metadata persistida es válida. Fuerzan FFprobe:
      archivo nuevo, registro sin `mtime_ns`, ruta/tamaño/`mtime_ns` cambiados o metadata inválida.
      Migración aditiva e idempotente `videos.mtime_ns INTEGER NULL`; bases antiguas hacen FFprobe
      en la primera pasada y se rellenan. `obtener_tamanos_archivos` obtiene tamaño+`mtime_ns` con
      **un `os.stat` por archivo**; `listar_registros_por_nombres` hace la consulta por lote
      (una SELECT, sin consultas por video); `TareaFFprobe` clasifica y solo probea lo necesario;
      `guardar_videos` persiste `mtime_ns`. Reescaneo caliente de 121 videos: **121 FFprobe → 0**,
      backend **~4.9 s → ~0.1–0.5 s** (referencia de PC de desarrollo). Verificación empírica con
      10 archivos físicos independientes (10 inodos): **10 → 0 → 1 → 0**. `video_id` y marcadores
      intactos; cambio de ruta fuerza FFprobe conservando la identidad por nombre/upsert. Riesgo
      residual aceptado (mismo ruta+tamaño+mtime_ns con contenido distinto); sin hash. Suites:
      `prueba_reutilizacion_metadata_b453.py` **20/20** y regresiones verdes. **B4.5 queda
      completada en sus Etapas 1-3; no se declara la Beta 4 completa todavía.**
6. **B4.6 — Rendimiento de carga visual.** **Completada (Etapa 1: diagnóstico; Etapa 2: carga
   diferida de previews cacheadas).** El objetivo es que la interfaz quede utilizable antes de
   terminar de cargar las previews.
   - **Etapa 1 — Diagnóstico de construcción/población de tarjetas.** **Completada.** Con 100
     tarjetas/300 previews cacheadas se descompuso el costo de la carga visual: construcción de
     widgets ~0.42 s (dominada por `_construir_exploracion`); `miniatura_principal` ~0.05 s (un
     `os.listdir` por tarjeta, O(n×m)); **`_crear_tarjetas` cargaba y escalaba las 300 previews de
     golpe (0.74 s caliente / ~3.5 s frío)**; bloqueo síncrono total 1.4–4.4 s; `_reemplazar_tarjetas`
     re-decodificaba las mismas previews; RAM ~+690 MB por la retención de pixmaps originales. Sin
     cambios de producción.
   - **Etapa 2 — Carga diferida de previews cacheadas.** **Completada.** `_crear_tarjetas`/
     `_agregar_tarjetas`/`_reemplazar_tarjetas` ya **no** cargan previews cacheadas: las tarjetas
     parten con textos + miniatura principal + placeholders; las previews (existentes o faltantes)
     se incorporan **progresivamente** mediante la tubería existente `_programar_previews` →
     `_timer_previews` → `_encolar_previews` → `TareaPreviewsProgresivas` →
     `generar_previews_faltantes` → `_aplicar_previews` → `actualizar_previews`. Con caché completa:
     **0 FFmpeg**; con faltantes: generación FFmpeg normal conservada. `Tarjeta._previews_completas`
     (estado interno, no persistido) decide si una tarjeta entra a la cola. Protección de resultados
     tardíos en `_aplicar_previews` (carpeta del video del resultado vs tarjeta actual; cambio A→B
     sin imágenes cruzadas ni crash). Ajuste de integración: `_reconstruir_previews_exploracion`
     cae a las previews cacheadas en disco si las etiquetas aún no las tienen (consecuencia
     necesaria del diferido; no modifica el motor B4.3 ni scrub ni densidad ni marcadores). Medición
     (100 tarjetas/300 previews, PC de desarrollo): `_crear_tarjetas(100)` **0.69–0.85 s** (antes
     1.4–4.4 s); tarjetas visibles ~0.72 s; primera preview ~1.0 s; **300 previews completas ~2.1 s**;
     máximo bloqueo continuo **~0.7 s**; lotes ~20–30 ms; reemplazo ~0.73 s sin recargar previews de
     golpe. **La interfaz es utilizable antes de terminar de cargar las previews.** Pendientes
     separados, sin implementar: retención de pixmaps originales/RAM (~+690 MB), `_construir_exploracion`
     en tarjetas colapsadas, reconciliación de `_reemplazar_tarjetas` y `miniatura_principal` con
     `os.listdir`. Suites: `prueba_carga_visual_b462.py` **9/9** y regresiones verdes. **B4.6
     completada en sus Etapas 1-2; no se declara la Beta 4 completa todavía.**
7. **Selección A/B, loops, fragmentos y edición.** **Posterior**, sin adelantar implementación.
   Los mismos puntos podrán participar en **selección A/B**, **loops**, **selección de
   fragmentos** o **corte/unión** como otra función, conservando su significado de navegación.
8. **Detección de archivos movidos / reasociación de marcadores huérfanos.** **Futura.**
   Detectar archivos movidos o renombrados y reasociar los marcadores que queden huérfanos
   (hoy los marcadores no se eliminan automáticamente si el registro del video desaparece, y
   no se intenta reasociar por nombre o ruta).

---

# Beta 5

La Beta 5 se desarrolla sobre la rama `beta5` (punto de partida: cierre de la Beta 4,
`v4.0-beta`). **B5.0 — Planificación y congelamiento del alcance inicial** quedó **cerrada
formalmente** (2026-08-13): etapa exclusivamente documental, sin implementación funcional.
**Beta 5 CERRADA internamente (2026-08-15):** etapas **B5.1–B5.9** completadas y aprobadas, más
los pulidos finales de interacción (creación por drag, edición de extremos A/B con handle/feedback
visual, corrección de press sostenido + drag, mejoras de visibilidad de segmentos y scroll
horizontal local de previews). Commit técnico principal
`969efcd9d71e78c1ca538bfa238a3e27f1484d9e`; instalador interno validado
`VisorVideos_Beta5_ValidacionFinal_Setup.exe`; identidad **`Beta 5 — B5.0`**. **Sin
distribución pública; sin merge a `main`; sin GitHub Release.**

## Alcance inicial

Beta 5 comienza con **cuatro bloques iniciales**. Estos cuatro bloques **no constituyen
necesariamente el alcance definitivo**: una vez completados se realizará una **auditoría de
producto** y se decidirá: **A.** cerrar Beta 5; o **B.** incorporar nuevos bloques. No se declara
desde ahora que estos bloques sean toda Beta 5.

### BLOQUE A — Entrada temporal a VLC

Doble clic sobre una preview/instante temporal → **abrir VLC** y reproducir el video **desde ese
instante exacto**. Debe **conservarse el doble clic existente** de la tarjeta/video (apertura con
la aplicación predeterminada).

### BLOQUE B — Segmentos A–B

Nuevo concepto independiente: **SEGMENTO** = `video_id` + inicio **A** + fin **B**, con **A < B**.
Decisión estratégica obligatoria: **MARCADOR ≠ SEGMENTO** — el marcador significa *"un instante
interesante"* y el segmento *"un intervalo interesante"*; **no** se convierten los marcadores en
puntos de inicio/fin especiales. Ambos conceptos pueden compartir un mismo instante temporal pero
siguen siendo **objetos independientes**. La arquitectura deberá permitir agregar en el futuro
datos adicionales al segmento (nombre, orden, activación, categoría) **sin implementarlos ahora**.

### BLOQUE C — Reproducción de segmento

Reproducir A→B **una sola vez** y reproducir A→B **en bucle**. La investigación B5.0 demostró
que VLC **3.0.23** admite `start-time`, `stop-time`, valores decimales y playlist de una entrada;
el bucle **no** usa el A–B interactivo nativo de VLC, sino conceptualmente
`start-time + stop-time + --loop` sobre una playlist de una entrada (sujeto a validación durante
la implementación real).

### BLOQUE D — Secuencia automática de segmentos

Reproducir listas como **A→B, C→D, E→F** automáticamente: VLC reproduce A hasta B, salta a C,
reproduce C hasta D, salta a E, reproduce E hasta F y termina, **sin que el usuario pulse
"Siguiente"**. B5.0 demostró físicamente (VLC 3.0.23) que esto es posible con una **playlist de
varias entradas del mismo archivo** con `start-time` y `stop-time`. Es conceptualmente distinto de
la reproducción de marcadores de Beta 4 (que exige avance manual).

## Evidencia técnica VLC de B5.0 (probado vs. hipótesis)

**Probado físicamente** (VLC 3.0.23, video real de 12 s, PC de desarrollo):

- **Inicio**: `start-time` funciona por CLI y dentro de M3U (`#EXTVLCOPT:start-time`; ya usado en
  producción desde B4.4).
- **Fin**: `stop-time` funciona por CLI, dentro de M3U (`#EXTVLCOPT:stop-time`) y con tiempos
  decimales (p. ej. `1.5` → `3.25`).
- **Bucle**: playlist de una entrada con `start-time=A` + `stop-time=B` más `--loop` reproduce
  repetidamente A→B (confirmado mediante interfaz RC: ciclos `5→7` repetidos).
- **Secuencia**: playlist con tres entradas del mismo video (1→3, 5→7, 9→11) reprodujo
  automáticamente los tres segmentos y terminó sin intervención (~6.5 s ≈ 6 s de contenido).

**Pendiente de validación durante la implementación**: notebook objetivo (versión de VLC y
drivers distintos); precisión frame-exacta de los límites A/B (salto por keyframes); `stop-time`
sin `start-time` (segmento desde 0); `#EXTVLCOPT:loop` por entrada (el bucle se logró con `--loop`
en línea de comandos).

## Higiene de procesos VLC (criterio técnico para pruebas)

- Cada VLC lanzado por una prueba debe **conservar su PID/handle** (`subprocess.Popen` /
  `Start-Process -PassThru`).
- La prueba debe cerrar **exclusivamente procesos propios**; **prohibido** matar globalmente
  `vlc.exe` (`taskkill /IM vlc.exe /F`).
- Cleanup mediante `finally`; **cierre normal primero**, `terminate`/`kill` solo como fallback;
  verificar que el proceso realmente terminó.
- **No cerrar una instancia VLC preexistente del usuario.**
- La investigación B5.0 detectó y corrigió un **residual** provocado por una prueba `--loop`
  (proceso huérfano al terminar el script controlador). Los scripts temporales de `%TEMP%`
  **no se incorporan al repositorio**.

## Modelo de segmentos (implementado en B5.1 y refinado en Beta 5)

Tabla independiente `segmentos_video`, campos `id`, `video_id`, `inicio`, `fin`; índice
`(video_id, inicio)`; reglas `video_id > 0`, `inicio >= 0`, `fin > inicio`; relación
conceptual mediante `video_id`; **misma política de orfandad que los marcadores** (sin CASCADE);
migración aditiva e idempotente. La edición de extremos A/B conserva el `id` mediante
`UPDATE` por id (tarea asíncrona, rollback en error).

## UX conceptual aprobada

- Creación de segmentos sobre la **exploración temporal existente** (previews/fotogramas como
  superficie de interacción); **sin timeline tradicional**.
- Banda visual A–B; **carga lazy por video**; **sin widgets pesados por cada segmento**.
- La interacción exacta de creación A/B podrá refinarse en B5.4 si las pruebas de usabilidad lo
  justifican; no se congelan detalles visuales innecesarios todavía.

## Rendimiento

- **NO** cargar segmentos de todos los videos al iniciar; **carga lazy al expandir la tarjeta**
  (mismo patrón que los marcadores).
- Dibujar las bandas en la **franja** en lugar de crear widgets por segmento.
- **Preservar la fluidez lograda en Beta 4**; sin dependencia de GPU.

## Plan de etapas B5.x

| Etapa | Objetivo |
| --- | --- |
| **B5.1** | Modelo SQLite y repositorio de segmentos (`segmentos_video`). |
| **B5.2** | Tareas asíncronas + carga lazy de segmentos. |
| **B5.3** | **Bloque A:** entrada temporal directa a VLC desde preview/franja. |
| **B5.4** | **Bloque B:** creación, representación visual (banda), persistencia y eliminación de segmentos. |
| **B5.5** | Robustez/persistencia/reconciliación de segmentos. |
| **B5.6** | **Bloque C-1:** reproducción simple A→B. |
| **B5.7** | **Bloque C-2:** bucle A→B. |
| **B5.8** | **Bloque D:** secuencia automática de segmentos. |
| **B5.9** | Auditoría integral de los cuatro bloques y decisión (cerrar Beta 5 / ampliar Beta 5). |

**Estado:** todas las etapas **B5.1–B5.9 están implementadas y aprobadas** (cierre interno
2026-08-15), junto con los pulidos finales de interacción. Las funciones fuera del alcance
inicial (nombres/notas/etiquetas, colores/categorías, panel/lista de marcadores y segmentos,
conversión marcador↔segmento, selección múltiple, snap, exportación, unión, secuencias
editables/reordenables, undo/redo, funciones avanzadas de la visión de producto) quedan como
**evolución futura**, sin implementar.

## Funciones fuera del alcance inicial

Excluidas por ahora: nombres de segmentos; etiquetas; puntuaciones; reordenamiento manual;
activar/desactivar segmentos; playlists persistentes de segmentos; exportación; recorte físico;
unión; creación de videos nuevos; línea de tiempo; IA. Pueden mantenerse como **evolución futura**.

## Riesgos conocidos

1. `stop-time` confirmado en VLC **3.0.23**; validar en la **notebook objetivo**.
2. Los límites A/B pueden **no ser frame-exactos** (búsqueda por keyframes).
3. `--loop` repite la **playlist completa**; para un segmento se usará una playlist de **una
   entrada**.
4. Configuraciones de **instancia única** de VLC a validar en integración.
5. Procesos VLC de pruebas: limpiar **por PID propio** (ver "Higiene de procesos VLC").
6. **No** cargar segmentos globalmente.
7. Orfandad tolerada igual que los marcadores.
8. Renombrado externo sigue **fuera de alcance**.
