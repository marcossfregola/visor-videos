# HISTORIAL DEL PROYECTO — Visor de Videos

Registro cronológico inmutable de cada etapa aprobada del proyecto.
Orden cronológico inverso (más reciente primero).

---

## 75. Eliminar archivos seleccionados enviándolos a la Papelera (Etapa B3.16)

- **Fecha:** 2026-08-07
- **Objetivo:** Implementar la eliminación segura de los archivos seleccionados
  enviándolos a la **Papelera de reciclaje de Windows** (nunca borrado permanente),
  manteniendo la interfaz fluida, reutilizando la infraestructura existente y
  minimizando el impacto arquitectónico.
- **Investigación (Papelera):** se evaluó `send2trash` (dependencia externa,
  descartada), `os.remove`/`shutil` (borrado permanente, prohibido por la filosofía del
  proyecto) y la **API nativa de Windows `SHFileOperationW` vía `ctypes`** — elegida por
  ser nativa, estable y sin dependencias nuevas.
- **Archivos creados:**
  - `prueba_eliminar_archivos.py` — 18 verificaciones: función pura (eliminación
    simple, individual, múltiple, archivo inexistente, archivo bloqueado, validación de
    tipos) e integración (habilitación del botón, cancelación sin tarea, eliminación en
    segundo plano, resumen, actualización incremental del catálogo, contador, selección
    restante, conservación del resto no eliminado).
- **Archivos modificados:**
  - `operaciones.py` — nueva función pura `eliminar_archivos(archivos)`: envía cada ruta
    a la Papelera con `SHFileOperationW` vía `ctypes` (`_SHFILEOPSTRUCTW` con
    `FO_DELETE` + `FOF_ALLOWUNDO`; `pFrom` con doble NUL), **una invocación por archivo**
    para aislar errores y continuar; **nunca borra permanentemente**; origen inexistente
    o archivo bloqueado → errores; devuelve `{"eliminados", "omitidos", "errores"}`.
    **Sin dependencias externas.**
  - `visor_videos.py` — botón "Eliminar…" con habilitación automática
    (`_actualizar_boton_eliminar`); `TareaEliminarArchivos(TareaBase)` reutilizando
    `gestor_operaciones` (despachador con rama "eliminar"); diálogo único de
    confirmación que indica la cantidad y que los archivos irán a la Papelera y podrán
    restaurarse ("Eliminar"/"Cancelar", default Cancelar; cancela → sin tarea); resumen
    "Eliminado: X — Omitidos: Y — Errores: Z"; **actualización incremental del catálogo**
    `_procesar_archivos_eliminados` (diferida con `QTimer.singleShot(0)` para que el
    resumen sea visible) que reutiliza el paso de sincronización existente
    (`TareaSincronizacionCatalogo`, detecta ausentes y los elimina) + recarga, **sin
    reescaneo completo** (sin FFprobe ni miniaturas).
  - `DOCUMENTO_TECNICO.md` — operación Eliminar, `eliminar_archivos` y la API nativa
    documentados.
  - `ROADMAP.md` — mejora B5 marcada como implementada.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual, hitos y próxima etapa
    actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Alternativa de actualización del catálogo:** incremental, reutilizando la
  sincronización existente (viable con cambios pequeños, sin romper la arquitectura; la
  interfaz no accede a SQLite directamente).
- **Pruebas:** `prueba_eliminar_archivos.py` 18/18; regresiones relevantes OK
  (`prueba_copiar_archivos.py` 15/15, `prueba_pegar_archivos.py` 15/15,
  `prueba_seleccion.py` 28/28, `prueba_modo_seleccion.py` 20/20,
  `prueba_resumen_seleccion.py` 17/17, `prueba_atajos_basicos.py` 13/13,
  `prueba_escaneo_interfaz.py` 36/36, `prueba_recarga_catalogo.py` 20/20,
  `prueba_sincronizacion_interfaz.py` 18/18, `prueba_guardar.py` 19/19,
  `prueba_seleccion_carpeta.py` 26/26, `prueba_carpeta_actual.py` 19/19,
  `prueba_pulido_bloque_a.py` 29/29, `prueba_lectura_paginada.py` 32/32,
  `prueba_filas_horizontales.py` 16/16, `prueba_interfaz_asincrona.py` 29/29,
  `prueba_smoke.py` OK).
- **Commit:** Aprobado y commiteado.
- **Resultado:** Eliminar disponible enviando a la Papelera (recuperable), en segundo
  plano, con confirmación, resumen y actualización incremental del catálogo; Copiar y
  Pegar intactos; sin atajos ni menú contextual nuevos.
- **Decisiones importantes:** Envío a la Papelera con API nativa de Windows
  (`SHFileOperationW` vía `ctypes`), sin dependencias externas. Confirmación default
  "Cancelar" (seguridad). El resumen es visible antes de que la sincronización lo
  reemplace (diferido).

---

## 74. Pegar archivos copiados en la carpeta actual (Etapa B3.15)

- **Fecha:** 2026-08-07
- **Objetivo:** Agregar la operación **Pegar** reutilizando la infraestructura de
  Copiar (B3.14): portapapeles interno de la aplicación, botón "Pegar…", operación en
  segundo plano, detección de colisiones (nunca sobrescribir), resumen final y
  resincronización incremental únicamente de los archivos pegados.
- **Archivos creados:**
  - `prueba_pegar_archivos.py` — 15 verificaciones: función pura (pegado simple,
    múltiple, omisión de existentes, origen inexistente, validaciones de tipo y
    destino) e integración (habilitación del botón, pegado en segundo plano, resumen,
    resincronización incremental con incorporación de los pegados, colisiones
    Omitir/Cancelar sin sobrescribir, portapapeles vacío y carpeta inválida).
- **Archivos modificados:**
  - `operaciones.py` — nueva función pura `pegar_archivos(archivos, destino)`: copia
    con `shutil.copy2` a `destino` (por `basename`), omite destinos existentes (nunca
    sobrescribe), registra errores por archivo y continúa; devuelve
    `{"copiados", "omitidos", "errores"}`. Sin Qt.
  - `visor_videos.py` — portapapeles interno `self._portapapeles` (alimentado en
    `_al_resultado_copia`); botón "Pegar…" con habilitación automática
    (`_actualizar_boton_pegar`); `TareaPegarArchivos(TareaBase)` reutilizando
    `gestor_operaciones` con despachador `_al_resultado_operaciones`/`_al_error_operaciones`;
    diálogo único de colisión con botones "Omitir"/"Cancelar" (si cancela no inicia
    tarea); resumen "Pegado: X — Omitidos: Y — Errores: Z" en `estado_escaneo`;
    **resincronización incremental** `_procesar_archivos_pegados(nombres)`: reutiliza
    la cadena existente (tamaños → FFprobe → miniaturas → guardado → sincronización →
    recarga) fijando `videos_detectados` a los archivos pegados, sin reescaneo completo.
  - `DOCUMENTO_TECNICO.md` — operación Pegar y `pegar_archivos` documentados.
  - `ROADMAP.md` — mejora B4 marcada como implementada.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual, hitos y próxima etapa
    actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Investigación de resincronización:** el pipeline existente opera sobre
  `videos_detectados`, por lo que **es viable reutilizarlo solo para los archivos
  pegados** con cambios pequeños y sin romper la arquitectura: se fija la lista a los
  nombres pegados y se arranca la cadena en el paso "tamaños" con un `TareaEscaneo`
  portador de `.carpeta` (no iniciado). Los pasos caros (FFprobe, miniaturas) se limitan
  a los pegados; la sincronización reconcilia la carpeta (no-op en pegado limpio).
- **Alternativa implementada:** **incorporación incremental únicamente de los archivos
  pegados** (sin reescaneo completo).
- **Pruebas:** `prueba_pegar_archivos.py` 15/15; regresiones relevantes OK
  (`prueba_copiar_archivos.py` 15/15, `prueba_seleccion.py` 28/28,
  `prueba_modo_seleccion.py` 20/20, `prueba_resumen_seleccion.py` 17/17,
  `prueba_atajos_basicos.py` 13/13, `prueba_escaneo_interfaz.py` 36/36,
  `prueba_recarga_catalogo.py` 20/20, `prueba_sincronizacion_interfaz.py` 18/18,
  `prueba_guardar.py` 19/19, `prueba_filas_horizontales.py` 16/16,
  `prueba_pulido_bloque_a.py` 29/29, `prueba_interfaz_asincrona.py` 29/29,
  `prueba_lectura_paginada.py` 32/32, entre otras).
- **Commit:** Aprobado y commiteado.
- **Resultado:** Pegar disponible con portapapeles interno, sin sobrescribir existentes
  y con resincronización acotada a los archivos pegados; Copiar intacto; sin atajos ni
  menú contextual nuevos.
- **Decisiones importantes:** Colisión → solo "Omitir"/"Cancelar" (nunca sobrescribir).
  El portapapeles persiste hasta un nuevo Copiar o el cierre de la aplicación (semántica
  de portapapeles; el pegado repetido queda a criterio del usuario). Copiar no se
  modifica; su resultado solo alimenta el portapapeles.

---

## 73. Tamaños grandes para la vista ampliada (Etapa B3.14b)

- **Fecha:** 2026-08-06
- **Objetivo:** Agregar dos factores adicionales (3.0x y 3.5x) para la vista ampliada,
  permitiendo que ocupe prácticamente toda la pantalla, sin modificar el mecanismo
  existente ni el criterio proporcional (tamaño de miniatura × factor).
- **Archivos creados:**
  - `prueba_tamano_vista_ampliada_grande.py` — 28 verificaciones: presencia de 3.0x y
    3.5x (UI y configuración), persistencia y compatibilidad (configs anteriores
    válidas; inválido → 1.6), restauración desde configuración (3.5; inválido → 1.6),
    cálculo del tamaño del popup (3.0/3.5 sobre Mediano; 3.5 sobre los cuatro tamaños
    de miniatura) y acotado a pantalla con 3.5 sobre Muy grande.
- **Archivos modificados:**
  - `configuracion.py` — `FACTORES_VALIDOS_VISTA_AMPLIADA = (1.2, 1.6, 2.0, 2.5, 3.0, 3.5)`.
  - `visor_videos.py` — `FACTORES_VISTA_AMPLIADA` y `TEXTOS_FACTOR_VISTA_AMPLIADA` con
    `3.0x`/`3.5x` (el combo del diálogo y `preparar` se llenan/computan por datos; sin
    tratamiento especial para los nuevos factores). El máximo pasa a ser 3.5x; la vista
    ampliada puede ocupar prácticamente toda la pantalla, siempre acotada por
    `_posicion_vista`. Default 1.6; configs anteriores compatibles.
  - `prueba_tamano_vista_ampliada.py` — **contrato actualizado con autorización expresa**
    de la auditoría: se eliminó `3.0` de los casos inválidos y las aserciones de "último
    válido" pasan de `2.5` a `3.5` (nuevo máximo); el round-trip incluye 3.0/3.5. Sin
    cambios en ninguna otra comprobación.
  - `DOCUMENTO_TECNICO.md` — factores 1.2–3.5 documentados en `VistaAmpliada`,
    `PreferenciasDialog` y `configuracion.py`.
  - `ROADMAP.md` — ampliación A10 incorporada al Bloque A como implementada.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual, hitos y próxima etapa
    actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Pruebas:** `prueba_tamano_vista_ampliada_grande.py` 28/28;
  `prueba_tamano_vista_ampliada.py` 38/38 (tras la actualización de contrato),
  `prueba_vista_ampliada.py` 24/24, `prueba_vista_ampliada_desactivada.py` 20/20,
  `prueba_preferencias_miniaturas.py` 31/31, `prueba_tamano_miniaturas.py` 32/32,
  `prueba_tamano_muy_grande.py` 27/27, `prueba_smoke.py` OK.
- **Resultado:** La vista ampliada admite factores hasta 3.5x (puede ocupar
  prácticamente toda la pantalla), integrados por datos sin tratamiento especial y con
  el acotado a pantalla funcionando igual que antes; default 1.6 y compatibilidad total
  con configuraciones anteriores.
- **Commit:** "Agregar tamaños grandes para la vista ampliada (Etapa B3.14b)"
- **Decisiones importantes:**
  1. **Integración por datos**: solo se ampliaron `FACTORES_VALIDOS_VISTA_AMPLIADA`,
     `FACTORES_VISTA_AMPLIADA` y `TEXTOS_FACTOR_VISTA_AMPLIADA`; sin lógica nueva.
  2. **Criterio proporcional intacto**: ampliación = tamaño de miniatura × factor.
  3. **Acotado a pantalla sin cambios**: `_posicion_vista` sigue limitando el popup a la
     geometría disponible.
  4. **Contrato de la suite actualizado** (autorizado): 3.0 deja de ser inválido y el
     "último válido" pasa a 3.5.

---

## 72. Opción para desactivar la vista ampliada (Etapa B3.14a)

- **Fecha:** 2026-08-06
- **Objetivo:** Permitir desactivar completamente la vista ampliada al posar el mouse,
  agregando la opción "Desactivado" en el combo del retardo de la vista ampliada: con
  ella nunca se inicia el timer ni aparece el popup (mover el mouse no produce ninguna
  acción), manteniendo intacto el resto de la funcionalidad.
- **Archivos creados:**
  - `prueba_vista_ampliada_desactivada.py` — 20 verificaciones: persistencia y
    compatibilidad del valor `-1` (default 400 ante ausencia/inválido); restauración
    desde configuración; con "Desactivado" **no se inicia el timer**, **no se fija
    pendiente** y **el popup nunca aparece** (incluso recorriendo previews y disparando
    el timeout); volver desde "Desactivado" a 400 ms reactiva el timer y el popup;
    aplicar "Desactivado" con el popup visible lo oculta.
- **Archivos modificados:**
  - `configuracion.py` — `-1` agregado a `RETARDOS_VALIDOS_VISTA_AMPLIADA`
    (representación interna de "Desactivado"); configs anteriores (0/250/400/600)
    compatibles; inválido → default 400 ms.
  - `visor_videos.py` — `RETARDOS_VISTA_AMPLIADA = (-1, 0, 250, 400, 600)` y
    `TEXTOS_RETARDO_VISTA_AMPLIADA = ("Desactivado", "Inmediato", "250 ms", "400 ms",
    "600 ms")`; `self._retardo_vista_ampliada` conserva el valor vigente (en la
    restauración solo se fija el intervalo si no es `-1`); `_aplicar_retardo_vista_ampliada`
    con `-1` detiene el timer y oculta un popup visible; `_al_vista_solicitada` retorna de
    inmediato con `-1`. Sin eliminar clases ni timers; sin tocar el resto de la
    funcionalidad.
  - `DOCUMENTO_TECNICO.md` — opción "Desactivado" documentada en `VistaAmpliada`,
    `PreferenciasDialog` y `configuracion.py`.
  - `ROADMAP.md` — ampliación A9 incorporada al Bloque A como implementada.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual, hitos y próxima etapa
    actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Pruebas:** `prueba_vista_ampliada_desactivada.py` 20/20; regresiones
  `prueba_vista_ampliada.py` 24/24, `prueba_preferencias_miniaturas.py` 31/31,
  `prueba_tamano_vista_ampliada.py` 35/35, `prueba_tamano_miniaturas.py` 32/32,
  `prueba_tamano_muy_grande.py` 27/27, `prueba_cantidad_previews.py` 14/14,
  `prueba_previews_automaticas.py` 22/22, `prueba_smoke.py` OK.
- **Resultado:** La opción "Desactivado" impide por completo la vista ampliada (sin
  timer ni popup) y volver a cualquier retardo la reactiva; se persiste con la
  infraestructura existente y las configuraciones anteriores siguen siendo compatibles.
- **Commit:** "Agregar opción para desactivar la vista ampliada (Etapa B3.14a)"
- **Decisiones importantes:**
  1. **Representación discreta `-1`**: sigue el patrón existente de
     `configuracion.py`; aditivo y sin migración.
  2. **Guarda en el punto de entrada**: `_al_vista_solicitada` retorna de inmediato con
     `-1`; no se tocan clases, timers ni el resto del mecanismo.
  3. **Ocultado inmediato**: aplicar "Desactivado" con un popup visible lo oculta.
  4. **Reactivación**: volver a cualquier retardo restaura el intervalo y el flujo
     normal.

---

## 71. Copia de archivos seleccionados (Etapa B3.14)

- **Fecha:** 2026-08-06
- **Objetivo:** Implementar la operación "Copiar" para los videos seleccionados: copiar
  los archivos físicos a una carpeta elegida por el usuario, en segundo plano, sin
  sobrescribir y con un resumen final. Sin Pegar, Eliminar ni atajos.
- **Archivos creados:**
  - `prueba_copiar_archivos.py` — 15 verificaciones: función pura (copia simple y
    múltiple, omitido si existe, errores por archivo y continúa, nombres anidados con
    subdirectorios, validaciones `TypeError`/`ValueError`); integración (botón habilitado
    con selección, la tarea emite el resumen por `tarea_resultado`, archivos copiados,
    resumen visible en `estado_escaneo`, interfaz no bloqueada con gestores
    independientes, cancelación del diálogo sin copia, clic sin selección sin efecto).
- **Archivos modificados:**
  - `operaciones.py` — incorporado a la arquitectura (conserva `sumar`): función pura
    `copiar_archivos(origen, archivos, destino)` con `shutil.copy2`, creación de
    subdirectorios para nombres anidados, omisión de destinos existentes (nunca
    sobrescribe), errores por archivo y resumen `{"copiados", "omitidos", "errores"}`.
  - `visor_videos.py` — `import operaciones` y `TareaBase` en el import de `tareas`;
    `TareaCopiarArchivos(TareaBase)` (glue); tercer gestor **`gestor_operaciones**`
    (independiente del pipeline y de previews; conectado a `_al_resultado_copia`/
    `_al_error_copia`; cerrado en `closeEvent`); botón "Copiar…" en la barra con
    `_actualizar_boton_copiar` (habilitado con selección + carpeta válida + gestor
    inactivo, conectado a `_actualizar_resumen_seleccion` y `_actualizar_botones_carpeta`);
    `_iniciar_copia` (aborta sin selección/carpeta; `getExistingDirectory`; cancelar no
    copia), `_al_resultado_copia` (oculta la barra y muestra "Copiado: X — Omitidos: Y —
    Errores: Z") y `_al_error_copia`. Sin atributos de estado permanentes (el resumen se
    emite por señal y el slot actualiza la interfaz). Sin cambios en menú contextual,
    atajos, SQLite ni pipeline.
  - `DOCUMENTO_TECNICO.md` — operación Copiar, `operaciones.py` y árbol de directorios
    actualizados; `operaciones.py` sale de la lista de "módulos ajenos".
  - `ROADMAP.md` — mejora B3 marcada como implementada; orden B3.14 marcado.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual, hitos y próxima etapa
    actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Pruebas:** `prueba_copiar_archivos.py` 15/15; regresiones `prueba_modo_seleccion.py`
  20/20, `prueba_resumen_seleccion.py` 17/17, `prueba_seleccion.py` 28/28,
  `prueba_shift_clic.py` 28/28, `prueba_seleccion_visual.py` OK,
  `prueba_restauracion_seleccion.py` 15/15, `prueba_filas_horizontales.py` 16/16,
  `prueba_recarga_catalogo.py` 20/20, `prueba_atajos_basicos.py` 13/13,
  `prueba_smoke.py` OK. Ejecución manual del flujo real en entorno controlado: copia de un
  archivo, copia múltiple (omitido + error), destino con archivos existentes (omitido sin
  sobrescribir), cancelación del diálogo, interfaz fluida (gestor principal no bloqueado),
  resumen final correcto (5/5).
- **Resultado:** El usuario puede copiar los archivos de video seleccionados a una carpeta
  elegida, en segundo plano, sin bloquear la interfaz ni sobrescribir archivos, con un
  resumen final visible (copiados/omitidos/errores). El catálogo no se resincroniza (la
  copia exporta a otra carpeta).
- **Commit:** "Implementar copia de archivos seleccionados (Etapa B3.14)"
- **Decisiones importantes:**
  1. **Lógica pura en `operaciones.py`** y tarea "pegamento" en `visor_videos.py`
     (restringido `tareas_videos.py`).
  2. **Tercer `GestorTareas`** dedicado a operaciones de archivos (no interfiere con el
     pipeline ni con las previews).
  3. **Sin sobrescribir** y **errores por archivo** con continuidad.
  4. **Sin estado permanente**: el resumen se emite por la señal `tarea_resultado` y el
     slot actualiza directamente la interfaz (modificación arquitectónica de la
     auditoría: sin `self.ultimo_resumen_copia`).

---

## 70. Atajos básicos de selección (Etapa B3.13)

- **Fecha:** 2026-08-06
- **Objetivo:** Implementar los atajos básicos de selección: **Ctrl+A** (seleccionar
  todas las tarjetas visibles, respetando el filtro) y **Esc** (salir del Modo
  Selección), sin operaciones sobre archivos.
- **Archivos creados:**
  - `prueba_atajos_basicos.py` — 13 verificaciones: Ctrl+A sin filtro (todas las
    visibles), con filtro (solo visibles; una oculta ya seleccionada no cuenta en el
    resumen), repetido (idempotente), con foco en la búsqueda (selecciona el texto del
    campo, no las tarjetas), con foco en un checkbox del modo (selecciona todas y marca
    checks); Esc con modo activo (sale, oculta checks, conserva selección), con modo
    inactivo (sin cambios), con foco en la búsqueda; consistencia.
- **Archivos modificados:**
  - `visor_videos.py` — imports `QShortcut`/`QKeySequence`; `_atajo_ctrl_a`
    (Ctrl+A) y `_atajo_esc` (Esc) sobre la ventana; `_atajo_seleccionar_todo` (guarda
    `busqueda.hasFocus()` → `selectAll()` o `_seleccionar_todo_visible`),
    `_seleccionar_todo_visible` (itera `self.visibles`, `add` + `_marcar_tarjeta`,
    cierra con `_actualizar_resumen_seleccion`) y `_atajo_salir_modo_seleccion` (si
    modo activo → `boton_modo_seleccion.setChecked(False)`).
  - `DOCUMENTO_TECNICO.md` — atajos básicos documentados.
  - `ROADMAP.md` — B3.13 marcada en el orden del Bloque B (B7 parcial; B7 queda
    Pendiente hasta B3.17).
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual, hitos y próxima etapa
    actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Pruebas:** `prueba_atajos_basicos.py` 13/13; regresiones `prueba_modo_seleccion.py`
  20/20, `prueba_resumen_seleccion.py` 17/17, `prueba_seleccion.py` 28/28,
  `prueba_shift_clic.py` 28/28, `prueba_seleccion_visual.py` OK,
  `prueba_restauracion_seleccion.py` 15/15, `prueba_filas_horizontales.py` 16/16,
  `prueba_recarga_catalogo.py` 20/20, `prueba_smoke.py` OK. Ejecución real de
  `visor_videos.py` con `biblioteca.db` y `QTest` (eventos reales de teclado): Ctrl+A sin
  filtro (24 de 24), con filtro (solo visibles), con foco en la búsqueda (sin tocar
  tarjetas), con foco en un checkbox; Esc con modo activo (sale, oculta checks, conserva
  24 de 24) y con modo inactivo; consistencia check↔selección, cierre limpio (exit 0).
- **Resultado:** Ctrl+A selecciona únicamente las tarjetas visibles (respetando el
  filtro) reutilizando `_marcar_tarjeta`; Esc sale del Modo Selección ocultando solo los
  checks y conservando la selección y el resumen. Se preserva el comportamiento del
  buscador (`QLineEdit`) y `_nombres_seleccionados` sigue siendo la única fuente de
  verdad.
- **Commit:** "Implementar atajos básicos de selección (Etapa B3.13)"
- **Decisiones importantes:**
  1. **`QShortcut`** sobre la ventana principal (contexto `WindowShortcut`).
  2. **Sin interferencia con la búsqueda**: con foco en el `QLineEdit`, Ctrl+A replica
     su `selectAll()` y no selecciona tarjetas.
  3. **Solo visibles**: `_seleccionar_todo_visible` itera `self.visibles`; las tarjetas
     ocultas por el filtro no se seleccionan (y una ya seleccionada no cuenta en el
     resumen mientras esté oculta).
  4. **Esc no destructivo**: solo oculta los checks; selección y resumen intactos.

---

## 69. Modo selección con checks por fila (Etapa B3.12)

- **Fecha:** 2026-08-06
- **Objetivo:** Introducir un modo específico para operaciones sobre múltiples archivos:
  toggle "Modo selección" en la barra principal y un checkbox por tarjeta (visible solo
  en modo activo), con sincronización completa entre el checkbox y `_nombres_seleccionados`,
  reutilizando `_marcar_tarjeta()` como punto central. Sin Copiar/Pegar/Eliminar/atajos.
- **Archivos creados:**
  - `prueba_modo_seleccion.py` — 20 verificaciones: checkbox oculto por defecto;
    mostrar/set con `blockSignals` (sin señal de retorno); toggle real emite
    `seleccion_check`; modo activo/desactivo (aparición/desaparición de checks);
    sincronización check↔selección en simple/Ctrl/Shift; deselección y selección vía
    checkbox (borde y resumen); sin reentrada (una sola incorporación); restauración
    tras recarga con modo activo; búsqueda; consistencia invariante.
- **Archivos modificados:**
  - `visor_videos.py` — `Tarjeta`: `QCheckBox` (`_check`) en el índice 0 del layout
    raíz (oculto por defecto), señal `seleccion_check(nombre, marcado)`,
    `mostrar_check(visible)`, `set_check(marcado)` (con `blockSignals`) y
    `_al_check_cambiar` (usa `self._check.isChecked()`). `VisorVideos`:
    `boton_modo_seleccion` (checkable) en la barra, `_modo_seleccion`,
    `_al_cambiar_modo_seleccion` (solo alterna visibilidad de checks), `_al_check_tarjeta`
    (muta `_nombres_seleccionados` y llama `_marcar_tarjeta`); `_marcar_tarjeta` agrega
    `tarjeta.set_check(valor)`; `_crear_tarjetas`/`_agregar_tarjetas` conectan la señal
    y aplican el modo. `_nombres_seleccionados` sigue siendo la única fuente de verdad;
    el resumen (B3.11) no cambia.
  - `DOCUMENTO_TECNICO.md` — Modo Selección + checks documentado (con la nota de
    `isChecked()`).
  - `ROADMAP.md` — mejoras B1 y B2 marcadas como implementadas; orden B3.12 marcado.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual, hitos y próxima etapa
    actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Corrección durante la implementación:** `_al_check_cambiar` compara con
  `self._check.isChecked()` en lugar de `estado == Qt.Checked` (semántica enum/int de
  PySide6); sin esta corrección la reentrada desmarcaba el checkbox y el estado se
  interpretaba invertido.
- **Pruebas:** `prueba_modo_seleccion.py` 20/20; regresiones `prueba_resumen_seleccion.py`
  17/17, `prueba_seleccion.py` 28/28, `prueba_shift_clic.py` 28/28,
  `prueba_seleccion_visual.py` OK, `prueba_restauracion_seleccion.py` 15/15,
  `prueba_filas_horizontales.py` 16/16, `prueba_recarga_catalogo.py` 20/20,
  `prueba_smoke.py` OK, `prueba_cantidad_previews.py` 14/14,
  `prueba_previews_automaticas.py` 22/22, `prueba_vista_ampliada.py` 24/24,
  `prueba_tiempo_previews.py` 35/35, `prueba_tamano_miniaturas.py` 32/32,
  `prueba_tamano_muy_grande.py` 27/27, `prueba_tamano_vista_ampliada.py` 35/35,
  `prueba_preferencias_miniaturas.py` 31/31. Ejecución real de `visor_videos.py` con
  `biblioteca.db`: modo activo/desactivo, checks visibles/ocultos, sincronización en
  simple/Ctrl/Shift, deselección vía check, recarga con restauración y modo activo,
  búsqueda, consistencia check↔selección verificada en todo el flujo, cierre limpio
  (exit 0).
- **Resultado:** El Modo Selección con checks por fila queda implementado con
  sincronización bidireccional centralizada en `_marcar_tarjeta`, `blockSignals` para
  evitar reentradas y `_nombres_seleccionados` como única fuente de verdad; activar o
  desactivar el modo conserva la selección y el resumen.
- **Commit:** "Implementar modo selección con checks por fila (Etapa B3.12)"
- **Decisiones importantes:**
  1. **Un solo punto de sincronización**: `_marcar_tarjeta` (toda mutación de selección)
     actualiza el check; el check emite `seleccion_check` → `_al_check_tarjeta`. Sin
     segunda lógica de selección.
  2. **`blockSignals`**: evita reentradas en la sincronización estado→check.
  3. **Modo no destructivo**: activar/desactivar solo alterna visibilidad de checks;
     selección y resumen intactos.
  4. **Corrección `isChecked()`**: por la semántica enum/int de PySide6.

---

## 68. Resumen permanente de selección (Etapa B3.11)

- **Fecha:** 2026-08-06
- **Objetivo:** Brindar un indicador permanente del estado de la selección ("X de Y
  seleccionados") basado únicamente en las tarjetas visibles, reutilizando la
  infraestructura existente de selección; sin checks, modo selección ni operaciones
  sobre archivos.
- **Archivos creados:**
  - `prueba_resumen_seleccion.py` — 17 verificaciones: estado inicial (0 de 5);
    selección simple, Ctrl (agregar/quitar), Shift (rango), deselección y limpieza;
    búsqueda/filtro (solo visibles); "Cargar más" (105 videos: 0 de 100 → 1 de 100 →
    1 de 105); reconstrucción del catálogo y restauración de la selección; el resumen
    refleja solo las visibles.
- **Archivos modificados:**
  - `visor_videos.py` — `resumen_seleccion` (QLabel en la barra de búsqueda) y
    `_actualizar_resumen_seleccion()` (método único y centralizado: X = visibles
    seleccionadas, Y = tarjetas visibles). Se invoca desde dos puntos de enganche que
    cubren todos los cambios: `_marcar_tarjeta` (selección simple/Ctrl/Shift,
    deselección, restauración) y `filtrar` (búsqueda, carga inicial, "Cargar más",
    reconstrucción), más el cierre de `_limpiar_seleccion`. Sin cambios de
    comportamiento de selección ni de layout.
  - `DOCUMENTO_TECNICO.md` — `_actualizar_resumen_seleccion` / `resumen_seleccion`
    documentados.
  - `ROADMAP.md` — mejora B6 marcada como implementada; orden B3.11 marcado como
    implementado.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual, hitos y próxima etapa
    actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Pruebas:** `prueba_resumen_seleccion.py` 17/17; regresiones `prueba_seleccion_visual.py`
  OK, `prueba_shift_clic.py` 28/28, `prueba_seleccion.py` 28/28,
  `prueba_restauracion_seleccion.py` 15/15, `prueba_filas_horizontales.py` 16/16,
  `prueba_recarga_catalogo.py` 20/20, `prueba_pagina_siguiente.py` 20/20,
  `prueba_lectura_paginada.py` 32/32, `prueba_escaneo_interfaz.py` 36/36,
  `prueba_seleccion_carpeta.py` 26/26, `prueba_interfaz_asincrona.py` 29/29,
  `prueba_smoke.py` OK, `prueba_cantidad_previews.py` 14/14,
  `prueba_previews_automaticas.py` 22/22, `prueba_vista_ampliada.py` 24/24,
  `prueba_tiempo_previews.py` 35/35, `prueba_tamano_miniaturas.py` 32/32,
  `prueba_tamano_muy_grande.py` 27/27, `prueba_tamano_vista_ampliada.py` 35/35,
  `prueba_preferencias_miniaturas.py` 31/31, `prueba_previews_progresivas.py` 16/16,
  `prueba_duracion_simplificada.py` 23/23, `prueba_doble_clic.py` 14/14,
  `prueba_tamano_archivo.py` 15/15. Ejecución real de `visor_videos.py` con
  `biblioteca.db`: 0/24, 1/24, 3/24 (Ctrl), 3/24 (rango Shift), filtro solo visibles,
  recarga con restauración, limpieza 0/24, cierre limpio (exit 0).
- **Resultado:** La interfaz muestra permanentemente "X de Y seleccionados" con Y =
  tarjetas visibles y X = visibles seleccionadas, actualizado automáticamente ante
  selección (simple/Ctrl/Shift), búsqueda, carga inicial, "Cargar más", reconstrucción
  y limpieza, sin modificar el comportamiento de selección ni el layout.
- **Commit:** "Implementar resumen permanente de selección (Etapa B3.11)"
- **Decisiones importantes:**
  1. **Centralización**: un único método `_actualizar_resumen_seleccion()`; se
     actualiza desde los choke points existentes (`_marcar_tarjeta` y `filtrar`) más el
     cierre de `_limpiar_seleccion` — sin llamadas dispersas.
  2. **Solo tarjetas visibles**: nunca refleja el catálogo completo.
  3. **Sin cambios de comportamiento**: no toca la lógica de selección, el layout ni
     las operaciones futuras del Bloque B.

---

## 67. Planificación y congelamiento del alcance del Bloque B (Etapa B3.10)

- **Fecha:** 2026-08-06
- **Tipo:** Etapa **exclusivamente documental** de planificación y congelamiento del
  alcance del Bloque B — **sin cambios de código** ni implementación.
- **Objetivo:** Definir oficialmente el alcance del Bloque B (Selección y operaciones):
  revisar las funcionalidades previstas, fijar el orden óptimo de implementación,
  detectar dependencias y congelar el alcance antes de escribir código.
- **Orden oficial del Bloque B (aprobado con modificación de la auditoría):**
  - B3.11 — Resumen de selección (B6).
  - B3.12 — Modo selección + Checks por fila (B1 + B2).
  - B3.13 — Atajos básicos (B7 parcial).
  - B3.14 — Copiar (B3).
  - B3.15 — Pegar (B4).
  - B3.16 — Eliminar (B5).
  - B3.17 — Atajos de operaciones (B7 parcial).
  La auditoría reordenó las dos primeras etapas (resumen antes que modo+checks) para
  verificar el modelo interno de selección antes de incorporar una nueva interacción.
- **Decisiones congeladas:** Copiar = copiar archivos físicos; Pegar = portapapeles
  interno; Eliminar = mover a la Papelera de reciclaje (nunca borrado permanente);
  operaciones de archivos en segundo plano; el modo selección no modifica el modo
  normal.
- **Excluidos del Bloque B:** renombrado masivo, favoritos, etiquetas, organización
  automática, detección de duplicados, filtros avanzados y apertura del video desde
  previews.
- **Documentos actualizados:**
  - `ROADMAP.md` — nueva sección "Bloque B — Selección y operaciones" (objetivo, orden,
    dependencias, decisiones congeladas, excluidos y seguimiento B1–B7 Pendiente).
  - `ESTADO_PROYECTO.md` — fase actual, última etapa aprobada, hitos y próxima etapa
    (B3.11 Resumen de selección) actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Resultado:** El Bloque B queda planificado y con su alcance congelado, listo para
  comenzar la implementación de la Etapa B3.11 tras la aprobación de este cierre.
- **Commit:** "Planificar y congelar el alcance del Bloque B (Etapa B3.10)"
- **Decisiones importantes:**
  1. **Resumen primero**: verifica el modelo interno de selección (ya validado) antes
     de incorporar los checks (reduce riesgo de regresiones y simplifica auditorías).
  2. **Alcance acotado a la Beta 3**: sin funcionalidades fuera del plan aprobado.
  3. **Seguimiento por mejoras B1–B7**: la tabla principal ya las refleja en
     "Pendiente"; el plan solo define el orden (sin duplicar la tabla).

---

## 66. Pulido técnico del Bloque A (Etapa B3.9)

- **Fecha:** 2026-08-06
- **Tipo:** Etapa de **pulido técnico** — **sin funcionalidades nuevas**; mejoras
  internas de rendimiento, mantenimiento y experiencia de uso del Bloque A.
- **Objetivo:** Resolver deudas técnicas de bajo costo detectadas en la auditoría del
  Bloque A (acotar la retención de pixmaps originales en memoria, corregir la
  transición del popup, deduplicar el criterio de duración válida y eliminar
  constantes realmente muertas) sin modificar el comportamiento funcional esperado.
- **Archivos creados:**
  - `prueba_pulido_bloque_a.py` — 29 verificaciones: `_pixmap_acotado` (imágenes
    pequeñas idénticas, 1920×1080 → 1280×720, vacío intacto), evidencia de reducción
    de memoria (~56 %), el límite 1280 cubre la mayor salida (Muy grande × 2.5);
    previews y miniatura acotadas al cargar; `_duracion_valida` y overlay/duración
    intactos; transición limpia del popup (oculta al cambiar, muestra la nueva tras el
    retardo, misma imagen no oculta); constantes muertas eliminadas; vista ampliada
    sobre original acotado.
- **Archivos modificados:**
  - `visor_videos.py` — `LIMITE_ORIGINAL_MINIATURA = 1280` y `_pixmap_acotado(pixmap)`
    aplicados al almacenar `_pixmap_original` (previews) y `_miniatura_original`
    (miniatura principal); `_al_vista_solicitada` oculta de inmediato el popup al pasar
    a una miniatura distinta; helper `_duracion_valida(duracion)` reemplazando las dos
    ocurrencias duplicadas; eliminación de `ANCHO_PREVIEW`/`ALTO_PREVIEW` (constantes
    realmente muertas). `RETARDO_VISTA_AMPLIADA_MS` se conserva (lo usa una prueba).
  - `DOCUMENTO_TECNICO.md` — `_duracion_valida`, `_pixmap_acotado`, `LIMITE_ORIGINAL_MINIATURA`
    y la transición del popup documentados; constante `TAMANIO_LOTE_PREVIEWS` corregida.
  - `ROADMAP.md` — pulido técnico registrado en el Bloque A (sin funcionalidades nuevas).
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual (Bloque A finalizado
    funcional y técnicamente), hitos y próxima etapa (Bloque B) actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Pruebas:** `prueba_pulido_bloque_a.py` 29/29; regresiones `prueba_vista_ampliada.py`
  24/24, `prueba_tamano_miniaturas.py` 32/32, `prueba_tamano_muy_grande.py` 27/27,
  `prueba_tamano_vista_ampliada.py` 35/35, `prueba_tiempo_previews.py` 35/35,
  `prueba_previews_progresivas.py` 16/16, `prueba_cantidad_previews.py` 14/14,
  `prueba_previews_automaticas.py` 22/22, `prueba_preferencias_miniaturas.py` 31/31,
  `prueba_filas_horizontales.py` 16/16, `prueba_recarga_catalogo.py` 20/20,
  `prueba_pagina_siguiente.py` 20/20, `prueba_lectura_paginada.py` 32/32,
  `prueba_seleccion_visual.py` OK, `prueba_shift_clic.py` 28/28, `prueba_seleccion.py`
  28/28, `prueba_restauracion_seleccion.py` 15/15, `prueba_smoke.py` OK,
  `prueba_doble_clic.py` 14/14, `prueba_tamano_archivo.py` 15/15. Ejecución real de
  `visor_videos.py` con `biblioteca.db`: 4 tamaños, transición limpia del popup, vista
  ampliada sobre Muy grande ×2.5, overlays, sin regeneración (488 → 488), cierre limpio
  (exit 0).
- **Evidencia objetiva de reducción de memoria:** `_pixmap_acotado` de 1920×1080 →
  1280×720: de 8.294.400 a 3.686.400 bytes por imagen almacenada (~56 % menos). Las
  previews reales actuales ya son ≤1280, por lo que se conservan iguales; el ahorro
  aplica a fuentes de mayor resolución.
- **Resultado:** El Bloque A queda pulido técnicamente sin cambios funcionales visibles:
  menor memoria retenida (manteniendo el reescalado en memoria, sin releer disco ni
  regenerar, y preservando la calidad de todos los tamaños y de la vista ampliada),
  transición limpia del popup, criterio de duración centralizado y constantes muertas
  eliminadas.
- **Commit:** "Pulir técnicamente el Bloque A (Etapa B3.9)"
- **Decisiones importantes:**
  1. **Acotado sin perder calidad**: `LIMITE_ORIGINAL_MINIATURA = 1280` cubre
     exactamente la mayor salida (Muy grande 512 × factor 2.5); imágenes ≤ 1280 se
     conservan idénticas; se mantiene la filosofía "sin releer disco, sin regenerar".
  2. **Transición limpia del popup**: ocultar de inmediato al cambiar de miniatura
     (la misma imagen no oculta) evita la sensación de popup "pegado".
  3. **Helper `_duracion_valida`**: centraliza el criterio; sin cambio de
     comportamiento (verificado por regresiones).
  4. **Solo constantes realmente muertas**: se eliminaron `ANCHO_PREVIEW`/`ALTO_PREVIEW`;
     se conservó `RETARDO_VISTA_AMPLIADA_MS` por tener uso en pruebas.
  5. **Sin nuevas funcionalidades**: no se implementaron las mejoras diferidas
     (badge en la vista ampliada, PreferenciasDialog, infraestructura genérica,
     instante real de generación, slots dinámicos decrecientes, persistencia_carpeta).

---

## 65. Generación automática de previews faltantes al aumentar la cantidad (Etapa B3.8)

- **Fecha:** 2026-08-06
- **Objetivo:** Eliminar la fricción de volver a presionar "Escanear" al aumentar la
  cantidad de previews: al incrementar la cantidad, la aplicación detecta los índices
  faltantes, genera únicamente esas imágenes en segundo plano y actualiza las tarjetas
  afectadas, sin escanear de nuevo ni reconstruir la interfaz.
- **Archivos creados:**
  - `prueba_previews_automaticas.py` — 22 verificaciones: crecimiento dinámico de
    slots (3→5→9, disminuir solo oculta); slot nuevo con `eventFilter` y pixmap
    original; `aplicar_tamano` reescala también los slots nuevos; integración:
    3→5 genera solo [4,5], 5→7 solo [6,7], sin regenerar existentes, tarjeta crece y
    se actualiza, overlays presentes, selección y scroll conservados, sin escaneo ni
    pipeline, gestor inactivo, disminuir sin trabajo en segundo plano.
- **Archivos modificados:**
  - `visor_videos.py` — `Tarjeta.__init__` guarda `self._contenedor_imagenes`;
    `Tarjeta._asegurar_slots_previews(cantidad)` crea `PreviewConTiempo` adicionales
    (con `dimensiones_miniatura()`, `eventFilter`, insertados antes del `addStretch()`)
    sin reconstruir la tarjeta; `ajustar_previews` invoca el crecimiento;
    `_al_cambiar_cantidad_previews` llama `_programar_previews()` al final (reutiliza
    la cola y el gestor existentes; `generar_previews_faltantes` genera solo los
    índices inexistentes). Sin cambios en `escanear_videos.py`, `tareas_videos.py`,
    `configuracion.py` ni en el pipeline.
  - `DOCUMENTO_TECNICO.md` — `_encolar_previews` y el crecimiento dinámico de slots
    documentados (B3.8).
  - `ROADMAP.md` — ampliación A8 incorporada al Bloque A como implementada, con la
    nota explícita de que la generación es automática al incrementar la cantidad.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual, hitos y próxima etapa
    actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Pruebas:** `prueba_previews_automaticas.py` 22/22; regresiones
  `prueba_previews_progresivas.py` 16/16, `prueba_cantidad_previews.py` 14/14,
  `prueba_vista_ampliada.py` 24/24, `prueba_tiempo_previews.py` 35/35,
  `prueba_tamano_miniaturas.py` 32/32, `prueba_tamano_muy_grande.py` 27/27,
  `prueba_tamano_vista_ampliada.py` 35/35, `prueba_preferencias_miniaturas.py` 31/31,
  `prueba_recarga_catalogo.py` 20/20, `prueba_pagina_siguiente.py` 20/20,
  `prueba_lectura_paginada.py` 32/32, `prueba_filas_horizontales.py` 16/16,
  `prueba_seleccion_visual.py` OK, `prueba_shift_clic.py` 28/28, `prueba_seleccion.py`
  28/28, `prueba_restauracion_seleccion.py` 15/15, `prueba_smoke.py` OK,
  `prueba_doble_clic.py` 14/14, `prueba_tamano_archivo.py` 15/15. Ejecución manual del
  flujo real en entorno controlado (sin escribir en `miniaturas/` de producción):
  3→5 (solo [4,5]), 5→7 (solo [6,7]), 7→9 (solo [8,9]), disminuir a 3 sin trabajo,
  tarjetas actualizadas automáticamente, sin escaneo, selección y scroll conservados,
  fluidez ~155-185 ms, cierre limpio (exit 0).
- **Resultado:** La cantidad de previews pasa a comportarse de forma natural: al
  aumentar solo se generan las imágenes faltantes en segundo plano y se actualizan las
  tarjetas afectadas, sin escanear ni reconstruir; al disminuir solo se ocultan.
- **Commit:** "Agregar generación automática de previews faltantes al aumentar la cantidad (Etapa B3.8)"
- **Decisiones importantes:**
  1. **Reutilización total**: se usa la cola y el gestor existentes
     (`_cola_previews` + `gestor_previews` + `TareaPreviewsProgresivas`); sin segundo
     mecanismo ni duplicación de lógica.
  2. **Crecimiento sin reconstrucción**: `_asegurar_slots_previews` agrega slots
     `PreviewConTiempo` en el layout existente; se conservan selección, overlays,
     tamaño, vista ampliada y eventFilter.
  3. **Solo índices faltantes**: `generar_previews_faltantes` y `_encolar_previews`
     garantizan que nunca se regeneren ni sobrescriban previews existentes.
  4. **Disminuir = ocultar**: sin trabajo en segundo plano.
  5. **Sin escaneo**: no se toca `iniciar_escaneo` ni el pipeline del catálogo.

---

## 64. Tamaño configurable de la vista ampliada (Etapa B3.7)

- **Fecha:** 2026-08-06
- **Objetivo:** Permitir elegir el tamaño de la vista ampliada al posar el mouse sobre
  una miniatura, mediante factores discretos aplicados al tamaño de la miniatura,
  ampliando la infraestructura de B3.4 y B3.5 sin cambios estructurales.
- **Archivos creados:**
  - `prueba_tamano_vista_ampliada.py` — 35 verificaciones: persistencia y tolerancia
    (1.2/1.6/2.0/2.5; inválidos → default 1.6); `configurar_factor_vista_ampliada`;
    `preparar` con cada factor sobre miniatura mediana; diálogo default/mapeo; flujo
    aceptar/cancelar; restauración al iniciar; integración con selección/scroll;
    acotado a pantalla con factor 2.5.
- **Archivos modificados:**
  - `visor_videos.py` — `FACTOR_VISTA_AMPLIADA_ACTUAL` + `configurar_factor_vista_ampliada(f)`
    (valida `1.2/1.6/2.0/2.5`); `VistaAmpliada.preparar` usa el factor vigente
    (ampliación = tamaño de miniatura × factor); `PreferenciasDialog` con el segundo
    control "Tamaño de la vista ampliada" (`combo_factor_vista`,
    `factor_vista_seleccionado()`, `_indice_factor()`); `_aplicar_tamano_vista_ampliada`
    y restauración al iniciar. Sin cambios en pipeline, SQLite ni recursos.
  - `configuracion.py` — `CLAVE_TAMANO_VISTA_AMPLIADA`, `guardar_tamano_vista_ampliada`
    y `obtener_tamano_vista_ampliada` (default 1.6; aditivo, sin migración).
  - `DOCUMENTO_TECNICO.md` — `VistaAmpliada` y `PreferenciasDialog` actualizados; clave
    del factor documentada.
  - `ROADMAP.md` — ampliación A7 "Tamaño configurable de la vista ampliada" incorporada
    al Bloque A como implementada.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual, hitos y próxima etapa
    actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Pruebas:** `prueba_tamano_vista_ampliada.py` 35/35; regresiones
  `prueba_vista_ampliada.py` 24/24, `prueba_preferencias_miniaturas.py` 31/31,
  `prueba_tamano_miniaturas.py` 32/32, `prueba_tamano_muy_grande.py` 27/27,
  `prueba_tiempo_previews.py` 35/35, `prueba_filas_horizontales.py` 16/16,
  `prueba_cantidad_previews.py` 14/14, `prueba_recarga_catalogo.py` 20/20,
  `prueba_pagina_siguiente.py` 20/20, `prueba_seleccion_visual.py` OK,
  `prueba_shift_clic.py` 28/28, `prueba_seleccion.py` 28/28,
  `prueba_restauracion_seleccion.py` 15/15, `prueba_smoke.py` OK,
  `prueba_doble_clic.py` 14/14, `prueba_tamano_archivo.py` 15/15. Ejecución real de
  `visor_videos.py` con `biblioteca.db`: cuatro factores sobre miniatura mediana,
  factor 2.0 correcto sobre los cuatro tamaños de miniatura, acotado a pantalla con
  2.5, diálogo (aceptar aplica y persiste), persistencia tras reiniciar (2.5), sin
  regeneración (488 → 488), fluidez (~1-3 ms por factor), cierre limpio (exit 0).
- **Resultado:** El tamaño de la vista ampliada es configurable (factores
  1.2/1.6/2.0/2.5, default 1.6) desde el diálogo "Preferencias", con aplicación
  inmediata y persistencia sin migración; la ampliación continúa siendo proporcional
  al tamaño de la miniatura y el comportamiento por defecto es idéntico al previo.
- **Commit:** "Agregar tamaño configurable de la vista ampliada (Etapa B3.7)"
- **Decisiones importantes:**
  1. **Proporcionalidad mantenida**: ampliación = tamaño de miniatura × factor
     configurado; sin tamaños absolutos (decisión de la auditoría).
  2. **Solo configuración**: el factor pasa de constante a configurable sin cambios
     estructurales; se confirma la separación configuración/lógica de presentación.
  3. **Default 1.6**: comportamiento idéntico al previo si el usuario nunca cambia la
     preferencia; clave aditiva; inválido/inexistente → 1.6.

---

## 63. Tamaño "Muy grande" para las miniaturas (Etapa B3.6)

- **Fecha:** 2026-08-06
- **Objetivo:** Ampliar la funcionalidad de tamaño configurable (B3.3) agregando un
  cuarto tamaño "Muy grande" (512×288), integrado únicamente ampliando los datos de
  configuración, sin modificar la lógica principal ni el comportamiento de los tres
  tamaños existentes.
- **Archivos creados:**
  - `prueba_tamano_muy_grande.py` — 27 verificaciones: presets y default (los tres
    existentes intactos + muy_grande); mapeo texto↔clave; persistencia round-trip y
    compatibilidad (configuraciones anteriores válidas; inválido → "mediano"); cambio
    en memoria sin `QPixmap` nuevos; overlay y miniatura principal reescalados; vista
    ampliada 1.6× sobre Muy grande (819×460); integración con selección/scroll/
    persistencia/restauración.
- **Archivos modificados:**
  - `visor_videos.py` — `"muy_grande": (512, 288)` en `TAMANIOS_MINIATURAS`,
    `"muy_grande": "Muy grande"` en `TEXTO_TAMANO_MINIATURAS` y `"Muy grande"` en el
    combo de tamaño. Integración 100 % por datos (miniatura principal, previews,
    overlays, vista ampliada, persistencia y cambio inmediato derivados de
    `dimensiones_miniatura()`); sin refactor ni lógica específica.
  - `configuracion.py` — `"muy_grande"` agregado a `TAMANIOS_VALIDOS_MINIATURAS`;
    lecturas tolerantes: valores previos válidos, desconocido/inválido → "mediano".
  - `DOCUMENTO_TECNICO.md` — `TAMANIOS_MINIATURAS` actualizado a los cuatro presets.
  - `ROADMAP.md` — ampliación A6 "Tamaño Muy grande" incorporada al Bloque A como
    implementada.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual, hitos y próxima etapa
    actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Pruebas:** `prueba_tamano_muy_grande.py` 27/27; regresiones
  `prueba_tamano_miniaturas.py` 32/32, `prueba_vista_ampliada.py` 24/24,
  `prueba_tiempo_previews.py` 35/35, `prueba_preferencias_miniaturas.py` 31/31,
  `prueba_cantidad_previews.py` 14/14, `prueba_previews_progresivas.py` 16/16,
  `prueba_filas_horizontales.py` 16/16, `prueba_recarga_catalogo.py` 20/20,
  `prueba_pagina_siguiente.py` 20/20, `prueba_seleccion_visual.py` OK,
  `prueba_shift_clic.py` 28/28, `prueba_seleccion.py` 28/28,
  `prueba_restauracion_seleccion.py` 15/15, `prueba_smoke.py` OK,
  `prueba_doble_clic.py` 14/14, `prueba_tamano_archivo.py` 15/15. Ejecución real de
  `visor_videos.py` con `biblioteca.db`: los cuatro tamaños (146/180/225/288), cambio
  inmediato (Muy grande ~36 ms, sin degradación perceptible), selección y scroll
  conservados, vista ampliada 1.6× (819×460), sin regeneración de miniaturas
  (488 → 488), persistencia tras reiniciar (Muy grande), cierre limpio (exit 0).
- **Resultado:** El tamaño "Muy grande" (512×288) queda integrado al Bloque A; la
  incorporación confirmó que la arquitectura de B3.3 está desacoplada y preparada
  para crecer (solo se ampliaron los datos de configuración).
- **Commit:** "Agregar tamaño 'Muy grande' para las miniaturas (Etapa B3.6)"
- **Decisiones importantes:**
  1. **Integración por datos**: cuatro adiciones (preset, texto, combo, conjunto
     válido); sin refactor ni lógica específica para el nuevo tamaño.
  2. **Comportamiento intacto de los tamaños existentes**: "Mediano" sigue siendo el
     default; configuraciones previas compatibles; inválido → "mediano".
  3. **Mismo mecanismo de B3.3**: escalado solo en memoria, sin regenerar ni releer
     disco (verificado: 0 `QPixmap` nuevos).

---

## 62. Preferencias relacionadas con miniaturas (Etapa B3.5)

- **Fecha:** 2026-08-06
- **Objetivo:** Centralizar el retardo de la vista ampliada como preferencia de
  miniaturas, con un diálogo de preferencias accesible desde la barra principal, sin
  mover ni alterar los controles de uso frecuente (Previews y Tamaño), y aplicando el
  nuevo valor de forma inmediata sin reinicio ni reconstrucción.
- **Alcance modificado por la auditoría:** la inspección original proponía trasladar
  los combos Previews y Tamaño al diálogo; la auditoría **rechazó ese traslado** (son
  de uso frecuente durante la exploración) y aprobó mantenerlos con acceso directo en
  la barra, dejando el diálogo únicamente para el retardo.
- **Archivos creados:**
  - `prueba_preferencias_miniaturas.py` — 31 verificaciones: persistencia y tolerancia
    (0/250/400/600; inválidos → default 400); diálogo con valores discretos; combos
    Previews/Tamaño preservados; aplicación inmediata y persistencia; flujo
    aceptar/cancelar (patcheando `exec`); restauración al iniciar; vista ampliada con
    el retardo configurado; selección y scroll conservados.
- **Archivos modificados:**
  - `configuracion.py` — `CLAVE_RETARDO_VISTA_AMPLIADA = "retardo_vista_ampliada_ms"`,
    `guardar_retardo_vista_ampliada(ms, ruta_config)` (valida `0/250/400/600`) y
    `obtener_retardo_vista_ampliada(ruta_config)` (default 400; aditivo, sin
    migración).
  - `visor_videos.py` — `PreferenciasDialog(QDialog)` (solo retardo, "Inmediato/250/400/
    600 ms"); botón "Preferencias…" en `fila_carpeta` junto a Previews/Tamaño;
    `_abrir_preferencias` (modal; Aceptar aplica) y `_aplicar_retardo_vista_ampliada(ms)`
    (persiste y hace `_timer_vista_mostrar.setInterval(ms)`); el intervalo inicial se
    toma de la configuración. Sin cambios en los controles existentes ni en pipeline,
    SQLite ni miniaturas.
  - `DOCUMENTO_TECNICO.md` — `PreferenciasDialog` y la clave del retardo documentados;
    `VistaAmpliada` actualizada (retardo configurable).
  - `ROADMAP.md` — mejora A5 marcada como implementada.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual (Bloque A completo),
    hitos y próxima etapa actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Pruebas:** `prueba_preferencias_miniaturas.py` 31/31; regresiones
  `prueba_cantidad_previews.py` 14/14, `prueba_tamano_miniaturas.py` 32/32,
  `prueba_vista_ampliada.py` 24/24, `prueba_tiempo_previews.py` 35/35,
  `prueba_filas_horizontales.py` 16/16, `prueba_recarga_catalogo.py` 20/20,
  `prueba_pagina_siguiente.py` 20/20, `prueba_seleccion_visual.py` OK,
  `prueba_shift_clic.py` 28/28, `prueba_seleccion.py` 28/28,
  `prueba_restauracion_seleccion.py` 15/15, `prueba_persistencia_subcarpetas.py` 10/10,
  `prueba_smoke.py` OK, `prueba_doble_clic.py` 14/14, `prueba_tamano_archivo.py` 15/15.
  Ejecución real de `visor_videos.py` con `biblioteca.db`: apertura del diálogo, cambio
  de retardo aplicado y persistido, cancelar conserva el valor, persistencia tras
  reiniciar, Previews (5→3→5) y Tamaño (Grande 225) funcionando, selección y scroll
  conservados, cierre limpio (exit 0).
- **Resultado:** El retardo de la vista ampliada es una preferencia configurable desde
  el botón "Preferencias…" (diálogo modal) con valores discretos, aplicada de inmediato
  y persistida con la infraestructura existente; los controles Previews y Tamaño
  permanecen con acceso directo en la barra principal. Con esto el **Bloque A —
  Experiencia visual queda completo** (B3.1 a B3.5).
- **Commit:** "Agregar preferencias relacionadas con miniaturas (Etapa B3.5)"
- **Decisiones importantes:**
  1. **Acceso directo para uso frecuente**: Previews y Tamaño permanecen en la barra
     (decisión de la auditoría); el diálogo concentra solo el retardo.
  2. **Aplicación inmediata**: `_aplicar_retardo_vista_ampliada` persiste y ajusta el
     timer sin reinicio, sin reconstrucción, sin tocar selección/scroll.
  3. **Compatibilidad**: clave aditiva; default 400 ms ante ausencia o valor inválido.
  4. **Infraestructura única**: se reutiliza el patrón de `configuracion.py` (clave +
     guardar/obtener + escritura atómica); el diálogo está preparado para incorporar
     más preferencias sin rediseñar la ventana principal.

---

## 61. Vista ampliada al posar el mouse sobre una miniatura (Etapa B3.4)

- **Fecha:** 2026-08-06
- **Objetivo:** Mostrar una vista ampliada (~1.6× del tamaño configurado) al posar el
  mouse sobre la miniatura principal o cualquier preview, con una única instancia de
  popup por ventana, reutilizando exclusivamente los pixmaps ya cargados en memoria
  (sin lecturas de disco, sin procesos externos, sin regeneración ni reescaneo).
- **Archivos creados:**
  - `prueba_vista_ampliada.py` — 24 verificaciones: instancia única y aislada de la
    tarjeta (el popup no es hijo de la tarjeta, no rompe helpers de test); reutilización
    del pixmap original sin construir `QPixmap` nuevos; retardo (pendiente sin mostrar,
    visible al vencer) y cancelación/ocultado al salir; miniatura principal y previews
    con el mismo comportamiento (emiten el pixmap original); ocultado por scroll y por
    reconstrucción del catálogo; posicionamiento acotado a pantalla; tamaño ~1.6×;
    integración con catálogo.
- **Archivos modificados:**
  - `visor_videos.py` — `VistaAmpliada(QFrame)` (flags `Qt.ToolTip | Frameless |
    StaysOnTop`, `QLabel` interno, `preparar()` que reutiliza y `ocultar()`);
    `RETARDO_VISTA_AMPLIADA_MS = 400`, `RETARDO_OCULTAR_VISTA_MS = 150`,
    `FACTOR_VISTA_AMPLIADA = 1.6`; `Tarjeta` instala `installEventFilter(self)` sobre
    `_imagen_miniatura` y las previews y emite `vista_solicitada(pixmap_original)` /
    `vista_abandonada()`; `VisorVideos` crea el popup único, los timers single-shot de
    mostrar/ocultar, conecta el scrollbar y `_reemplazar_tarjetas`, y maneja
    `_mostrar_vista_diferida` / `_ocultar_vista` / `_posicion_vista` (offset respecto
    del cursor y acotado a la pantalla). Sin cambios de SQLite, pipeline, FFprobe ni
    miniaturas.
  - `DOCUMENTO_TECNICO.md` — `VistaAmpliada` y el mecanismo de la etapa documentados.
  - `ROADMAP.md` — mejora A4 marcada como implementada.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual, hitos y próxima etapa
    actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Pruebas:** `prueba_vista_ampliada.py` 24/24; regresiones `prueba_tiempo_previews.py`
  35/35, `prueba_tamano_miniaturas.py` 32/32, `prueba_filas_horizontales.py` 16/16,
  `prueba_previews_progresivas.py` 16/16, `prueba_seleccion_visual.py` OK,
  `prueba_shift_clic.py` 28/28, `prueba_seleccion.py` 28/28,
  `prueba_restauracion_seleccion.py` 15/15, `prueba_cantidad_previews.py` 14/14,
  `prueba_recarga_catalogo.py` 20/20, `prueba_pagina_siguiente.py` 20/20,
  `prueba_lectura_paginada.py` 32/32, `prueba_smoke.py` OK, `prueba_doble_clic.py` 14/14,
  `prueba_tamano_archivo.py` 15/15. Ejecución real de `visor_videos.py` con
  `biblioteca.db`: 24 tarjetas, popup tras el retardo, ocultado por salida/scroll/
  reconstrucción, funcionamiento sobre miniatura principal y previews, **0 lecturas de
  disco**, sin parpadeos, sin regeneración de miniaturas (348 → 348), cierre limpio
  (exit 0).
- **Resultado:** Al posar el mouse sobre la miniatura principal o una preview, tras un
  retardo configurable se muestra una vista ampliada que reutiliza el pixmap original
  en memoria; desaparece automáticamente al salir, al hacer scroll, al reconstruirse el
  catálogo o al cerrar; el popup es único y se reutiliza en toda la sesión.
- **Commit:** "Agregar vista ampliada al posar el mouse sobre una miniatura (Etapa B3.4)"
- **Decisiones importantes:**
  1. **Popup único por ventana**: nunca se crea ni destruye por hover; `preparar()`
     reutiliza si ya muestra el mismo pixmap (sin parpadeos).
  2. **Reutilización en memoria**: amplía `_miniatura_original` / `_pixmap_original`
     (verificado: 0 `QPixmap` nuevos durante el flujo).
  3. **Comportamiento idéntico** para miniatura principal y previews (un único
     `eventFilter` por tarjeta).
  4. **Sin popup colgado**: ocultado por salida (retardo corto), scroll, reconstrucción
     y cierre; posicionamiento con offset y acotado a pantalla.
  5. **Correcciones de implementación**: (1) se reubicó la instalación de los
     `eventFilter` de las previews (se instalaban antes de crearlas); (2) se eliminó la
     referencia textual a FFmpeg del docstring para respetar la separación
     arquitectónica verificada por `prueba_filas_horizontales.py` T15 (AST sin
     ffmpeg/ffprobe en la interfaz). Ambas aprobadas por la auditoría.

---

## 60. Tamaño configurable de miniaturas (Etapa B3.3)

- **Fecha:** 2026-08-06
- **Objetivo:** Permitir elegir el tamaño de visualización de las imágenes de la
  tarjeta (Pequeño / Mediano / Grande) con cambio inmediato, escalando **solo en
  memoria** los pixmaps ya cargados, sin regenerar miniaturas, sin FFmpeg, sin
  relectura de disco, sin reescaneo y sin modificar el layout.
- **Archivos creados:**
  - `prueba_tamano_miniaturas.py` — 32 verificaciones: presets y default mediano;
    mapeo texto↔clave; persistencia round-trip y fallback a "mediano" (incluido
    valor almacenado inválido); cambio de tamaño **sin crear `QPixmap` nuevos**
    (reescalado de los originales ya cargados); overlay de B3.1 conservado y
    renderizado en los tres tamaños; integración con `VisorVideos` (cambio
    inmediato, selección y scroll conservados, sin escaneo, persistencia).
- **Archivos modificados:**
  - `visor_videos.py` — presets `TAMANIOS_MINIATURAS` (pequeno 260×146, mediano
    320×180 default, grande 400×225), `configurar_tamano_miniaturas`,
    `dimensiones_miniatura`, `texto_tamano_miniaturas` y `clave_tamano_miniaturas`;
    miniatura principal y previews escalan con `dimensiones_miniatura()`;
    `PreviewConTiempo` guarda `_pixmap_original` y añade `reajustar()` (reescala en
    memoria y actualiza alturas, también de placeholders); `Tarjeta` guarda
    `_imagen_miniatura`/`_miniatura_original`/`_recuadro_sin_miniatura` y añade
    `aplicar_tamano()`; combo "Tamaño" en `fila_carpeta`, handler
    `_al_cambiar_tamano_miniaturas` y restauración con `blockSignals` (evita escribir
    configuración en el arranque). Sin cambios de SQLite, pipeline, FFprobe ni
    miniaturas.
  - `configuracion.py` — `CLAVE_TAMANIO_MINIATURAS`, `guardar_tamano_miniaturas` y
    `obtener_tamano_miniaturas` (default y fallback "mediano"; mismo patrón atómico).
  - `DOCUMENTO_TECNICO.md` — presets/helpers, `PreviewConTiempo` (reajustar),
    `Tarjeta` (aplicar_tamano) y `configuracion.py` (tamano_miniaturas) documentados.
  - `ROADMAP.md` — mejora A3 marcada como implementada.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual, hitos, deuda técnica
    y próxima etapa actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Pruebas:** `prueba_tamano_miniaturas.py` 32/32; regresiones
  `prueba_filas_horizontales.py` 16/16, `prueba_previews_progresivas.py` 16/16,
  `prueba_cantidad_previews.py` 14/14, `prueba_tiempo_previews.py` 35/35,
  `prueba_seleccion_visual.py` OK, `prueba_shift_clic.py` 28/28, `prueba_seleccion.py`
  28/28, `prueba_restauracion_seleccion.py` 15/15, `prueba_recarga_catalogo.py` 20/20,
  `prueba_pagina_siguiente.py` 20/20, `prueba_persistencia_subcarpetas.py` 10/10,
  `prueba_smoke.py` OK, `prueba_tamano_archivo.py` 15/15, `prueba_doble_clic.py` 14/14.
  Ejecución real de `visor_videos.py` con `biblioteca.db`: 24 tarjetas, cambio
  inmediato Pequeño/Mediano/Grande, selección y scroll conservados, overlays
  posicionados (verificación por píxeles), persistencia tras reinicio (Grande),
  sin regeneración de miniaturas (348 → 348), cierre limpio (exit 0).
- **Observación (deuda técnica preexistente):** durante la etapa se detectó que
  `prueba_persistencia_carpeta.py` **T11 y T16** fallan (18/20). Se verificó que la
  falla **existe en HEAD limpio** (anterior a B3.3) y **no es atribuible a esta
  etapa**: los tests asumen que iniciar sin preferencias no crea `configuracion.json`,
  pero la restauración de `escaneo_automatico` (default `True`, Etapa 2.8) escribe el
  archivo en el arranque. Clasificada como **deuda técnica** para una futura etapa
  específica; no se corrigió en B3.3.
- **Resultado:** El tamaño de las imágenes de la tarjeta es configurable entre
  Pequeño, Mediano (default) y Grande, con cambio inmediato que reutiliza los pixmaps
  en memoria (sin regenerar, sin FFmpeg, sin relectura de disco, sin reescaneo),
  conservando selección, scroll y overlays, y con la preferencia persistida.
- **Commit:** "Agregar tamaño configurable de miniaturas (Etapa B3.3)"
- **Decisiones importantes:**
  1. **Escalado solo en memoria**: se reutilizan los pixmaps ya cargados
     (`_pixmap_original` por preview y `_miniatura_original` de la tarjeta); verificado
     por prueba objetiva (0 construcciones nuevas de `QPixmap` durante el cambio).
  2. **Tres presets discretos**: Pequeño/Mediano/Grande (default Mediano); sin
     deslizador ni tamaños personalizados; layout, separación y scroll intactos.
  3. **Cambio inmediato no destructivo**: sin reescaneo, sin reconstrucción; se
     conservan selección, scroll y overlays.
  4. **Restauración sin escrituras**: `blockSignals` en el arranque evita crear la
     configuración sin necesidad (compatibilidad con el contrato de persistencia).
  5. **Persistencia reutilizando la infraestructura existente**: clave
     `tamano_miniaturas`, default y fallback "mediano".

---

## 59. Duración simplificada en las tarjetas (Etapa B3.2)

- **Fecha:** 2026-08-06
- **Objetivo:** Simplificar la presentación de la duración en las tarjetas aplicando
  el criterio aprobado —`m:ss` (menos de una hora), `h:mm:ss` (una hora o más) y
  "No disponible" (duración inexistente o inválida)— como representación visual,
  sin alterar el valor numérico almacenado.
- **Archivos creados:**
  - `prueba_duracion_simplificada.py` — 23 verificaciones: formato `m:ss`/`h:mm:ss`
    (5, 41.07, 65, 15:42, 1:00:00, 1:01:01, 2:35:18); tarjeta con duración válida y
    Resolución/Codec/Miniaturas intactos; "No disponible" ante duración None/0/-5/
    bool/texto; integración con `VisorVideos` (corto, varios minutos, una hora o más
    y desconocida).
- **Archivos modificados:**
  - `visor_videos.py` — el campo "Duración" de `Tarjeta` se presenta con
    `formatear_tiempo(duracion)` (reutiliza la función de B3.1, sin funciones nuevas
    ni lógica duplicada): `m:ss`/`h:mm:ss` y `"No disponible"` cuando la duración no
    existe o no es válida. Cambio solo de presentación: `duracion_segundos` permanece
    numérico (REAL); sin cambios de SQLite, esquema, consultas, pipeline, FFprobe ni
    miniaturas.
  - `prueba_filas_horizontales.py` y `prueba_recarga_catalogo.py` — aserción de
    duración actualizada al nuevo contrato visual (`"5"` → `"0:05"`).
  - `DOCUMENTO_TECNICO.md` — `formatear_tiempo` y `Tarjeta` actualizados con la
    duración simplificada (B3.2).
  - `ROADMAP.md` — mejora A2 marcada como implementada.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual, hitos y próxima etapa
    actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Pruebas:** `prueba_duracion_simplificada.py` 23/23; regresiones
  `prueba_filas_horizontales.py` 16/16, `prueba_recarga_catalogo.py` 20/20,
  `prueba_smoke.py` OK, `prueba_tiempo_previews.py` 35/35, `prueba_cantidad_previews.py`
  14/14, `prueba_previews_progresivas.py` 16/16, `prueba_pagina_siguiente.py` 20/20,
  `prueba_seleccion_visual.py` OK, `prueba_shift_clic.py` 28/28, `prueba_seleccion.py`
  28/28, `prueba_restauracion_seleccion.py` 15/15, `prueba_tamano_archivo.py` 15/15,
  `prueba_doble_clic.py` 14/14. Ejecución real de `visor_videos.py` con `biblioteca.db`:
  duraciones reales correctas (23/23) y casos representativos (pocos segundos,
  varios minutos, una hora o más, desconocida), cierre limpio (exit 0).
- **Resultado:** La duración de cada tarjeta se muestra legiblemente con `m:ss` /
  `h:mm:ss`, o "No disponible" cuando corresponde; el valor `duracion_segundos`
  permanece numérico y no se tocaron SQLite, esquema, consultas, pipeline, FFprobe
  ni miniaturas.
- **Commit:** "Simplificar la duración mostrada en las tarjetas (Etapa B3.2)"
- **Decisiones importantes:**
  1. **Reutilización**: se reutiliza `formatear_tiempo()` de B3.1 (m:ss / h:mm:ss,
     `None` ante inválido); no se creó una segunda función de formato.
  2. **Representación visual únicamente**: el texto es efímero de la interfaz; la
     lógica interna sigue trabajando con segundos (REAL).
  3. **"No disponible"**: si la duración no existe o no es válida (None, 0, negativo,
     bool, texto) se muestra "No disponible".
  4. **Ajuste de pruebas por contrato**: `prueba_filas_horizontales.py` y
     `prueba_recarga_catalogo.py` actualizaron su aserción de duración al nuevo
     formato (cambio intencional de representación).

---

## 58. Tiempo sobre las miniaturas de preview (Etapa B3.1)

- **Fecha:** 2026-08-06
- **Objetivo:** Mostrar sobre cada preview el instante temporal de su fotograma, derivado
  exclusivamente de la duración almacenada en el catálogo, con un overlay puramente visual
  y el menor impacto posible sobre la arquitectura.
- **Archivos creados:**
  - `prueba_tiempo_previews.py` — 35 verificaciones: formateador (None/bool/negativo/texto,
    0, 41.07, 65.4, 3600, 3723); derivación por índice con N=3/5/7/9; Tarjeta con duración
    válida (overlay por preview y textos 0:25/0:50/1:15 para 100 s); duración None/0/-5/texto/
    bool sin overlay; ruta inexistente sin overlay y placeholder conservado; regresión
    `ajustar_previews` 3/5/7/9; integración con `VisorVideos` (duración desde catálogo y
    duración NULL sin overlay).
- **Archivos modificados:**
  - `visor_videos.py` — `PreviewConTiempo(QLabel)`: overlay exclusivamente visual del
    instante sobre cada preview (mismo widget por slot, mismo pixmap escalado y mismo layout;
    fondo semitransparente oscuro `rgba(0,0,0,150)` + texto claro; sin overlay si no hay
    tiempo); `formatear_tiempo(segundos)` ("m:ss"/"h:mm:ss", `None` ante duración inválida);
    `Tarjeta` guarda `_duracion`; `_colocar_preview` deriva el instante con
    `calcular_tiempo_preview(duracion, indice + 1)`. Sin FFprobe adicional, sin pipeline, sin
    esquema SQLite ni persistencia de tiempos.
  - `DOCUMENTO_TECNICO.md` — `PreviewConTiempo`, `formatear_tiempo` y `Tarjeta` actualizados;
    §9 con la observación arquitectónica para la futura apertura del video desde una preview.
  - `ROADMAP.md` — mejora A1 marcada como implementada.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, fase actual, hitos y próxima etapa actualizados.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Pruebas:** `prueba_tiempo_previews.py` 35/35; regresiones `prueba_previews_progresivas.py`
  16/16, `prueba_cantidad_previews.py` 14/14, `prueba_filas_horizontales.py` 16/16,
  `prueba_smoke.py` OK, `prueba_tamano_archivo.py` 15/15, `prueba_lectura_paginada.py` 32/32,
  `prueba_pagina_siguiente.py` 20/20, `prueba_recarga_catalogo.py` 20/20,
  `prueba_seleccion_visual.py` OK, `prueba_shift_clic.py` 28/28, `prueba_seleccion.py` 28/28,
  `prueba_restauracion_seleccion.py` 15/15. Ejecución real de `visor_videos.py` con
  `biblioteca.db` y `miniaturas/` reales: 24 tarjetas con overlays correctos, cantidades
  3/5/7/9 aplicadas, verificación por píxeles del overlay, cierre limpio (exit 0).
- **Resultado:** Cada preview muestra el instante temporal de su fotograma, derivado
  exclusivamente de la duración del catálogo; con duración desconocida o inválida no se
  dibuja ningún overlay. El overlay es únicamente visual (sin cambios de layout, tamaños,
  scroll, pipeline, SQLite ni recursos).
- **Commit:** "Implementar tiempo sobre las miniaturas de preview (Etapa B3.1)"
- **Decisiones importantes:**
  1. **Derivación en visualización**: el instante se calcula con la función existente
     `calcular_tiempo_preview(duración, índice)` en tiempo de render, sin FFprobe adicional,
     sin persistir tiempos ni modificar el esquema.
  2. **Overlay exclusivamente visual**: un `QLabel` por slot con `pixmap()` conservado (mismo
     contrato y tamaño), lo que no altera layout, tamaños ni scroll.
  3. **Sin valores por defecto**: si la duración es `None` o inválida no se dibuja el overlay.
  4. **Observación para el futuro (Bloque E)**: al implementar la apertura del video desde una
     preview, el instante deberá provenir del instante real usado al generar el fotograma, no
     de un recálculo.

---

## 57. Aprobación del alcance de la Beta 3 (Etapa B3.0)

- **Fecha:** 2026-08-06
- **Tipo:** Etapa **exclusivamente documental** de planificación y
  congelamiento del alcance de la Beta 3 — **sin cambios de código** ni
  implementación de funcionalidades.
- **Objetivo:** Definir y aprobar oficialmente el alcance de la Beta 3 a
  partir de las mejoras recopiladas durante la fase de uso real de la Beta 2,
  y congelarlo como base de las etapas siguientes.
- **Contexto:** Finalizó la **fase de recopilación de mejoras** del uso real
  de la Beta 2 y quedó **aprobado el alcance de la Beta 3**. No se modificó
  ningún archivo de producción ni se implementó funcionalidad alguna: la
  etapa es exclusivamente de planificación.
- **Documentos actualizados:**
  - `ROADMAP.md` — nueva sección "Bloque de trabajo 3 — Beta 3": objetivo
    general, filosofía, alcance, bloques de implementación A–E, mejoras
    aprobadas, funcionalidades expresamente excluidas y tabla de seguimiento
    (todas en estado "Pendiente"); nota de estado del encabezado y referencias
    cruzadas actualizadas para mantener la coherencia.
  - `ESTADO_PROYECTO.md` — fase actual y próxima etapa actualizadas (finalizó
    la recopilación de mejoras, el alcance de la Beta 3 quedó aprobado y el
    proyecto está listo para comenzar su implementación); nuevo hito de la
    Etapa B3.0. Sin cambios en el último commit aprobado y sin marcar ninguna
    mejora como implementada.
  - `DOCUMENTO_TECNICO.md` — §9 (dirección futura) actualizado: la Beta 3 se
    desarrollará siguiendo el plan de trabajo aprobado, sin introducir
    cambios arquitectónicos que todavía no existen.
  - `HISTORIAL_PROYECTO.md` — este documento (registro de la etapa).
- **Alcance de la etapa:** planificación y definición del alcance de la Beta
  3. **Sin modificaciones de código, sin implementación de funcionalidades y
  sin adelantar funcionalidades excluidas del alcance.**
- **Resultado:** El alcance de la Beta 3 quedó aprobado y congelado; el plan
  de trabajo (objetivo, bloques, mejoras aprobadas, funcionalidades excluidas
  y tabla de seguimiento) servirá como base para las etapas de implementación
  siguientes.
- **Commit:** pendiente de aprobación (etapa documental, sin commit).
- **Decisiones importantes:**
  1. **Congelamiento del alcance**: la Beta 3 se implementará únicamente con
     las mejoras aprobadas en esta etapa; las funcionalidades excluidas no
     forman parte de su alcance.
  2. **Etapa exclusivamente documental**: no hubo modificaciones de código; el
     plan de trabajo queda registrado como referencia para las etapas
     siguientes.

---

## 56. Cierre y congelamiento de la Beta 2 (fase de pruebas reales)

- **Fecha:** 2026-08-06
- **Tipo:** Cierre de fase y congelamiento de versión — **sin cambios de código** (documentación).
- **Objetivo:** Congelar la Beta 2 del Visor de Videos: dejar una versión documentada y lista para
  distribuir e instalar en distintas computadoras para comenzar la fase de uso real.
- **Contexto:** El **Bloque de trabajo 2** (Centro de Navegación) quedó **completado** y aprobado
  (Etapas 2.1 a 2.9, incluida la verificación de la Etapa 2.7). El núcleo funcional del proyecto
  está estabilizado y el divisor del `QSplitter` funciona correctamente (la llamada redundante
  `splitter.handle(1).setCursor(Qt.SplitHCursor)` fue eliminada durante la limpieza del bloque).
- **Documentos actualizados:**
  - `ESTADO_PROYECTO.md` — fase actual actualizada a Beta 2 congelada en fase de pruebas reales;
    nuevo hito de cierre del Bloque 2; próxima etapa pasa a ser la **validación de la Beta 2** (con
    desarrollo pausado) y la Etapa 2.10 se retomará al finalizar la validación.
  - `ROADMAP.md` — nota de estado en el encabezado (desarrollo funcional pausado durante la
    validación de la Beta 2, solo correcciones por uso); Bloque de trabajo 2 marcado como
    **completado**; Etapa 2.10 queda pendiente de la validación.
  - `DOCUMENTO_TECNICO.md` — sección 9 (dirección futura) con la nota de estado de la Beta 2:
    sin nuevas funcionalidades durante la validación, solo correcciones por uso.
- **Alcance de la fase:** durante la validación de la Beta 2 **no se implementarán funcionalidades
  nuevas**; únicamente se corregirán errores detectados mediante el uso real en distintas
  computadoras.
- **Resultado:** La Beta 2 queda congelada y documentada como lista para distribuir e instalar,
  dando inicio a la fase de uso real.
- **Commit:** pendiente de aprobación (cierre documental del Bloque de trabajo 2).
- **Decisiones importantes:**
  1. **Congelamiento funcional**: no se agregan funcionalidades durante la validación de la Beta 2;
     el desarrollo se reanudará al finalizar la validación.
  2. **Solo correcciones por uso**: los únicos cambios admitidos durante la fase serán correcciones
     de errores detectados mediante el uso.

---

## 55. Indicadores visuales de carpetas escaneadas (Etapa 2.9)

- **Fecha:** 2026-08-06
- **Objetivo:** Mostrar un indicador visual en el árbol para identificar las carpetas que ya fueron
  escaneadas e incorporadas al catálogo, únicamente visual, manteniendo el árbol completamente
  desacoplado de SQLite y reutilizando la información del pipeline de escaneo.
- **Archivos creados:**
  - `prueba_indicador_escaneado.py` — 14 verificaciones: enum de estados; carpeta nunca escaneada
    (`SIN_ESCANEAR` + ícono nulo) y ya escaneada (`ESCANEADA` + ícono); `ROL_ESTADO` almacena `int`
    (no `QIcon`); marcar no altera selección/expansión/`carpeta_actual()`/hijos; carga diferida
    (marcar antes de expandir → el nodo nace `ESCANEADA`); AST sin `sqlite3`/`conectar_bd` en el
    árbol; flujo real (escaneo → nodo `ESCANEADA`).
- **Archivos modificados:**
  - `arbol_navegacion.py` — `EstadoNodo(IntEnum)` (SIN_ESCANEAR/ESCANEADA/PARCIAL/CAMBIOS_PENDIENTES/
    ERROR; solo se usan los dos primeros); `ROL_ESTADO = Qt.UserRole + 4`; `_carpetas_escaneadas`;
    método público `marcar_carpeta_escaneada(ruta)`; `_estado_de` / `_aplicar_indicador` /
    `_icono_para` (guardan solo el valor del estado y calculan el ícono con `QStyle.SP_DialogApplyButton`); se aplica al crear nodos (discos y carpetas, incluida la carga diferida). El árbol no conoce
    SQLite ni el catálogo.
  - `visor_videos.py` — `self.carpetas_escaneadas = set()`; en `_al_resultado_sincronizacion` agrega la
    carpeta escaneada (`resultado["diferencias"]["carpeta"]`) y llama
    `self.arbol_navegacion.marcar_carpeta_escaneada(carpeta)`. Sin consultas nuevas.
  - `DOCUMENTO_TECNICO.md` — `EstadoNodo`, `ROL_ESTADO` e indicadores documentados; `visor` y
    `_al_resultado_sincronizacion` actualizados; dirección futura, árbol de directorios y **problema 14
    en §8** (deuda técnica del estado por sesión).
  - `ESTADO_PROYECTO.md` — última etapa aprobada, hitos, deuda técnica y próxima etapa actualizados.
  - `ROADMAP.md` — Etapa 2.9 marcada como implementada.
- **Pruebas:** `prueba_indicador_escaneado.py` 14/14; regresiones `prueba_arbol_navegacion.py` OK,
  `prueba_expansion_carpetas.py` 35/35, `prueba_seleccion_arbol.py` 25/25, `prueba_escaneo_arbol.py`
  11/11, `prueba_escaneo_automatico.py` 19/19, `prueba_subcarpetas_arbol.py` 15/15,
  `prueba_carpeta_actual.py` 19/19, `prueba_persistencia_arbol.py` 15/15, `prueba_escaneo_interfaz.py`
  36/36, `prueba_smoke.py` OK. Ejecución real de `visor_videos.py`: escaneo de `C:\prueba\videos_prueba`
  → el nodo pasa de `SIN_ESCANEAR` (0) a `ESCANEADA` (1) con ícono presente; cierre limpio (`exit 0`).
- **Resultado:** El árbol muestra un indicador visual en las carpetas escaneadas (actualizado al
  completar cada escaneo, incluida la carga diferida), sin alterar la navegación, la selección ni la
  expansión, y sin acceder a SQLite.
- **Commit:** "Agregar indicadores visuales de carpetas escaneadas en el arbol (Etapa 2.9)"
- **Decisiones importantes:**
  1. **API preparada para crecer**: `EstadoNodo` (IntEnum) con cinco estados (solo se usan dos) y
     mapeo visual centralizado en `_icono_para(estado)`; los datos del nodo guardan solo el valor
     (`ROL_ESTADO`), nunca `QIcon`.
  2. **Desacoplamiento total**: el árbol recibe un conjunto de rutas (`marcar_carpeta_escaneada`); no
     consulta SQLite ni conoce el catálogo. El dato proviene del resultado del pipeline de escaneo.
  3. **Solo visual**: marcar una carpeta no modifica selección, expansión ni navegación.
  4. **Carga diferida compatible**: el indicador se aplica al crear cada nodo por pertenencia al
     conjunto.

---

## 54. Preferencia independiente de escaneo automático al seleccionar carpeta (Etapa 2.8)

- **Fecha:** 2026-08-06
- **Objetivo:** Incorporar una preferencia independiente "Escaneo automático al seleccionar carpeta"
  que decide si seleccionar una carpeta desde el Centro de Navegación inicia inmediatamente un
  escaneo o simplemente establece la carpeta activa, soportando las cuatro combinaciones con "Incluir
  subcarpetas" y manteniendo el flujo manual del botón "Escanear carpeta".
- **Archivos creados:**
  - `prueba_escaneo_automatico.py` — 19 verificaciones: persistencia (guardar True/False), default
    `True`, config antigua sin la clave → `True`, valor no-booleano → `True`, restauración de la
    casilla y persistencia inmediata al cambiar; gating árbol/diálogo con la preferencia ON/OFF;
    botón "Escanear carpeta" idéntico con preferencia ON y OFF; cuatro combinaciones (escaneo
    automático × subcarpetas) con resultados reales.
- **Archivos modificados:**
  - `configuracion.py` — `CLAVE_ESCANEO_AUTOMATICO = "escaneo_automatico"`,
    `guardar_preferencia_escaneo_automatico(activado, ruta_config)` y
    `obtener_preferencia_escaneo_automatico(ruta_config)` (default `True`; mismo patrón atómico
    `.tmp` + `os.replace`; sin mecanismo paralelo).
  - `visor_videos.py` — casilla `QCheckBox "Escaneo automático"` en `fila_carpeta`; restauración de la
    preferencia antes de `_iniciar_carga()` (la casilla refleja el valor cargado antes de la
    interacción); handler `_al_cambiar_escaneo_automatico` que persiste inmediatamente; método único
    `_disparar_escaneo_si_automatico()` (única decisión `if escaneo_automatico.isChecked()`) usado por
    `_al_carpeta_actual_arbol` y `seleccionar_carpeta`; el botón "Escanear carpeta" conserva
    `iniciar_escaneo()` incondicional.
  - `DOCUMENTO_TECNICO.md` — `configuracion.py` documentado con la nueva preferencia; visor
    documentado con la casilla, la decisión única y el botón incondicional; dirección futura y árbol
    de directorios actualizados.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, hitos y próxima etapa actualizados.
  - `ROADMAP.md` — Etapa 2.8 marcada como implementada.
- **Pruebas:** `prueba_escaneo_automatico.py` 19/19; regresiones `prueba_escaneo_arbol.py` 11/11,
  `prueba_subcarpetas_arbol.py` 15/15, `prueba_escaneo_interfaz.py` 36/36, `prueba_seleccion_carpeta.py`
  26/26, `prueba_carpeta_actual.py` 19/19, `prueba_persistencia_arbol.py` 15/15,
  `prueba_persistencia_subcarpetas.py` 10/10, `prueba_escaneo_guardado.py` 24/24,
  `prueba_sincronizacion_interfaz.py` 18/18, `prueba_recarga_catalogo.py` 20/20, `prueba_escaneo.py`
  12/12, `prueba_progreso_visual.py` OK, `prueba_smoke.py` OK. Ejecución real de `visor_videos.py`:
  preferencia OFF → selección en el árbol sin escaneo (solo establece la carpeta) + botón escanea;
  preferencia ON → la selección escanea automáticamente; cierre limpio (`exit 0`).
- **Resultado:** La preferencia independiente permite al usuario decidir si la selección de una
  carpeta escanea automáticamente o solo establece la carpeta activa; las cuatro combinaciones con
  "Incluir subcarpetas" funcionan correctamente; el botón manual ignora la preferencia; compatibilidad
  hacia atrás garantizada por el default `True`.
- **Commit:** "Agregar preferencia independiente de escaneo automatico al seleccionar carpeta (Etapa 2.8)"
- **Decisiones importantes:**
  1. **Preferencia independiente**: nueva clave en el JSON compartido, mismo patrón atómico; default
     `True` (sin migraciones).
  2. **Decisión única**: `_disparar_escaneo_si_automatico()` centraliza el `if` de la preferencia;
     árbol y diálogo la invocan, el botón no.
  3. **Botón incondicional**: "Escanear carpeta" usa `iniciar_escaneo()` directamente, ignorando la
     preferencia.
  4. **Restauración previa a la interacción**: la casilla refleja el valor cargado antes de mostrar la
     ventana.

---

## 53. Verificación de la paridad de "Incluir subcarpetas" entre árbol, botón y diálogo (Etapa 2.7)

- **Fecha:** 2026-08-06
- **Tipo:** Etapa de **verificación arquitectónica** — **sin cambios de producción**.
- **Objetivo:** Confirmar con evidencia objetiva que el árbol, el botón "Escanear carpeta" y el diálogo
  "Seleccionar carpeta" respetan de forma idéntica el estado de "Incluir subcarpetas", reutilizando el
  pipeline existente.
- **Conclusión de la inspección:** la Etapa 2.6 ya garantizaba la paridad: los tres orígenes convergen en
  `iniciar_escaneo()` (visor_videos.py:619), que ejecuta
  `configurar_escaneo_recursivo(self.incluir_subcarpetas.isChecked())` (línea 627) antes de crear la
  `TareaEscaneo`. No se detectó diferencia funcional.
- **Archivos creados:**
  - `prueba_subcarpetas_arbol.py` — 15 verificaciones: para cada origen (árbol, botón, diálogo) y cada
    estado de la casilla (activada/desactivada) captura el resultado real de `videos_detectados` y el
    valor pasado a `configurar_escaneo_recursivo` (espía); verifica que desactivado produce solo el
    nivel superior, activado incluye las subcarpetas, y que árbol == botón == diálogo en ambos estados.
- **Archivos modificados:** ninguno de producción.
- **Pruebas:** `prueba_subcarpetas_arbol.py` 15/15. Regresiones: `prueba_escaneo_subcarpetas.py` 12/12,
  `prueba_escaneo_arbol.py` 11/11, `prueba_escaneo.py` 12/12, `prueba_escaneo_interfaz.py` 36/36,
  `prueba_smoke.py` OK. Ejecución real de `visor_videos.py` con una carpeta con subcarpetas: desactivado
  → `['top.mp4']`; activado → incluye `sub1/v1.mp4` y `sub2/v2.mkv`; cierre limpio (`exit 0`).
- **Resultado:** La hipótesis quedó confirmada: no fue necesario modificar ningún archivo de producción;
  la arquitectura de la Etapa 2.6 garantizaba automáticamente la paridad funcional.
- **Commit:** "Verificar paridad de subcarpetas entre arbol, boton y dialogo (Etapa 2.7)"
- **Decisiones importantes:**
  1. **Verificación en lugar de implementación**: el objetivo de la etapa ya estaba satisfecho por la
     Etapa 2.6; no se introdujeron cambios preventivos.
  2. **Evidencia objetiva**: la suite verifica los tres orígenes con el mismo estado de la casilla y
     compara resultados reales del escaneo, no solo la estructura del código.

---

## 52. Escaneo automático al seleccionar una carpeta en el árbol (Etapa 2.6)

- **Fecha:** 2026-08-06
- **Objetivo:** Integrar el Centro de Navegación con el flujo de trabajo principal: al seleccionar una
  carpeta válida en el árbol se inicia automáticamente el mismo escaneo que dispara el botón "Escanear
  carpeta", reutilizando exactamente el mismo punto de entrada (`iniciar_escaneo()`), sin duplicar
  lógica ni crear un segundo flujo.
- **Archivos creados:**
  - `prueba_escaneo_arbol.py` — 11 verificaciones: disparo automático desde el árbol (1 llamada);
    repetir la misma carpeta sin disparo; cambiar de carpeta con nuevo disparo; botón y árbol usando
    el mismo `iniciar_escaneo`; diálogo con un único escaneo (sin doble por la sincronización con el
    árbol); restauración inicial sin escaneo; flujo real (selección → pipeline → catálogo actualizado)
    y sin doble escaneo durante un pipeline activo.
- **Archivos modificados:**
  - `visor_videos.py` — `_al_carpeta_actual_arbol` y `seleccionar_carpeta()` (diálogo) invocan
    `self.iniciar_escaneo()` al final. El guard de repetición (`carpeta_seleccionada == ruta`) impide
    dobles disparos: la restauración de arranque y la sincronización con el diálogo **no** escanean.
  - `prueba_escaneo_interfaz.py` — T04, T05, T06 y T22 actualizados al nuevo contrato (el diálogo
    ahora dispara un único escaneo). T22 fija `carpeta_seleccionada` directamente para probar el
    escaneo manual de carpeta inválida.
  - `prueba_carpeta_actual.py`, `prueba_seleccion_arbol.py`, `prueba_expansion_carpetas.py`,
    `prueba_arbol_navegacion.py`, `prueba_persistencia_arbol.py` — espías de `iniciar_escaneo`
    (registran el disparo sin ejecutar el pipeline, evitando escaneos reales como el de `C:\`) y
    aserciones ajustadas.
  - `prueba_persistencia_carpeta.py` — parche acotado de `ArbolNavegacion.revelar_ruta → True` en el
    arnés: la suite prueba el round-trip de configuración y no la reconstrucción del árbol; evita que
    la deuda 8.3 rompa sus aserciones.
  - `DOCUMENTO_TECNICO.md` — punto de entrada único del escaneo documentado (botón, árbol y diálogo);
    `seleccionar_carpeta` y el handler actualizados; dirección futura y árbol de directorios
    actualizados.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, hitos, deuda técnica (T15 preexistente) y próxima
    etapa actualizados.
  - `ROADMAP.md` — Etapa 2.6 marcada como implementada.
- **Pruebas:** `prueba_escaneo_arbol.py` 11/11; `prueba_escaneo_interfaz.py` 36/36,
  `prueba_carpeta_actual.py` 19/19, `prueba_seleccion_arbol.py` 25/25, `prueba_expansion_carpetas.py`
  35/35, `prueba_arbol_navegacion.py` OK, `prueba_persistencia_arbol.py` 15/15,
  `prueba_persistencia_carpeta.py` 20/20, `prueba_seleccion_carpeta.py` 26/26, `prueba_smoke.py` OK y
  regresiones amplias (34 suites). Ejecución real de `visor_videos.py`: selección de
  `C:\prueba\videos_prueba` → escaneo automático → catálogo con los 4 videos reales, cierre limpio
  (`exit 0`).
- **Observación (preexistente):** `prueba_aplicar_incorporaciones.py` T15 falla de forma ambiental: la
  base real `biblioteca.db` tiene `tamano_bytes` poblado y T15 asume NULL. No atribuible a esta etapa
  (no modifica ese subsistema); registrado como deuda técnica.
- **Resultado:** Seleccionar una carpeta válida en el árbol (o por el diálogo) inicia automáticamente
  el escaneo y actualiza el catálogo mediante el pipeline existente; repetir la misma carpeta no
  redispara; la restauración inicial no escanea; nunca hay dos escaneos simultáneos.
- **Commit:** "Iniciar automaticamente el escaneo al seleccionar una carpeta en el arbol (Etapa 2.6)"
- **Decisiones importantes:**
  1. **Un único punto de entrada**: el árbol, el botón y el diálogo invocan `iniciar_escaneo()`; no
     existe un segundo flujo de escaneo.
  2. **Un solo disparo por acción**: el guard de repetición impide dobles disparos (restauración,
     sincronización con el diálogo y selección repetida).
  3. **Escaneo en curso**: se conserva el comportamiento de ignorar la nueva solicitud (sin colas,
     cancelaciones ni reinicios en esta etapa).
  4. **Tests con espías**: las suites de árbol parchean `iniciar_escaneo` para verificar el disparo sin
     ejecutar pipelines reales ni escanear discos como `C:\`.

---

## 51. Persistencia y restauración de la carpeta seleccionada del árbol (Etapa 2.5)

- **Fecha:** 2026-08-06
- **Objetivo:** Persistir la carpeta actualmente seleccionada en el árbol y restaurarla al reiniciar,
  reconstruyendo únicamente la rama necesaria para volver a mostrarla, manteniendo el catálogo
  desacoplado y sin escaneo automático.
- **Archivos creados:**
  - `prueba_persistencia_arbol.py` — 15 verificaciones: persistencia de la carpeta; **una única
    escritura** y sin reescritura por repetición (contador del wrap); restauración tras reinicio
    (carpeta, etiqueta y árbol sincronizados); **solo rama necesaria** (disco/a/x expandidos y
    cargados; b y c conservan placeholder); sin escaneo; tarjetas intactas; **restauración
    tolerante** (carpeta borrada → sin excepción, sin carpeta activa); diálogo intacto
    (válido/cancelar/inválido).
- **Archivos modificados:**
  - `visor_videos.py` — `_al_carpeta_actual_arbol` ahora persiste la carpeta con
    `guardar_ultima_carpeta(ruta, self._ruta_config)` (misma clave/escritura atómica; el guard de
    repetición evita reescrituras). La restauración de arranque usa
    `self.arbol_navegacion.revelar_ruta(carpeta_guardada)` y, si la ruta no puede reconstruirse,
    deja el estado consistente sin carpeta seleccionada (`carpeta_seleccionada = None`, etiqueta
    `MENSAJE_SIN_CARPETA`).
  - `arbol_navegacion.py` — nuevo método público `revelar_ruta(ruta)` (reconstrucción **estrictamente
    incremental**: disco por prefijo común, expansión nivel por nivel con la carga diferida existente,
    búsqueda solo del siguiente componente; comparación insensible a mayúsculas con `os.path.normcase`;
    devuelve `False` sin lanzar ante rutas no reconstruibles) + helper `_buscar_disco`. `seleccionar_ruta`
    se conserva (sincronizaciones rápidas con nodos ya cargados). Docstring actualizado a la Etapa 2.5.
  - `prueba_seleccion_arbol.py`, `prueba_expansion_carpetas.py`, `prueba_arbol_navegacion.py` —
    actualización solo de aislamiento (ruta de configuración temporal para que el nuevo persistir no
    escriba el `configuracion.json` real).
  - `DOCUMENTO_TECNICO.md` — `revelar_ruta` y la persistencia documentadas; dirección futura y árbol
    de directorios actualizados; **problema 13 en §8** registra la deuda técnica de nombres cortos 8.3.
  - `ESTADO_PROYECTO.md` — última etapa aprobada, deuda técnica, hitos y próxima etapa actualizados.
  - `ROADMAP.md` — Etapa 2.5 marcada como implementada.
- **Pruebas:** `prueba_persistencia_arbol.py` 15/15. Regresiones: `prueba_seleccion_arbol.py` 24/24,
  `prueba_expansion_carpetas.py` 34/34, `prueba_arbol_navegacion.py` OK, `prueba_carpeta_actual.py`
  17/17, `prueba_seleccion_carpeta.py` 26/26, `prueba_smoke.py` OK, `prueba_escaneo_interfaz.py` 36/36.
  Ejecución real de `visor_videos.py` con restauración real (`C:\Users\Marcos Casa`, ~0.10 s) y cierre
  limpio (`exit 0`).
- **Observación (deuda técnica):** las rutas Windows con **nombres cortos 8.3** (p. ej. `MARCOS~1`)
  no se reconstruyen en el árbol (el árbol carga nombres largos) y caen en el comportamiento tolerante
  (aplicación inicia sin carpeta seleccionada, sin inconsistencias). No afecta el uso normal; se
  registra para una futura etapa de robustez del Centro de Navegación.
- **Resultado:** La carpeta seleccionada en el árbol persiste entre ejecuciones y se restaura al
  iniciar reconstruyendo solo la rama necesaria, con el árbol y `carpeta_seleccionada` sincronizados y
  sin escaneo automático ni modificaciones del catálogo.
- **Commit:** "Persistir y restaurar la carpeta seleccionada del arbol de navegacion (Etapa 2.5)"
- **Decisiones importantes:**
  1. **Reutilización de `guardar_ultima_carpeta`**: no se agrega una segunda forma de persistir la
     carpeta; `carpeta_seleccionada` sigue siendo la única fuente de verdad.
  2. **`revelar_ruta` estrictamente incremental**: en cada nivel expande y busca solo el siguiente
     componente; no recorre el árbol ni el disco completos y no carga ramas ajenas.
  3. **Restauración tolerante**: si la ruta no puede reconstruirse, la aplicación inicia normalmente
     y queda sin carpeta seleccionada, sin excepciones ni estados inconsistentes.
  4. **Sin escrituras redundantes**: el guard de repetición evita reescribir la configuración cuando
     la carpeta no cambió.

---

## 50. Integración de la selección del árbol con la carpeta activa de la aplicación (Etapa 2.4)

- **Fecha:** 2026-08-06
- **Objetivo:** Integrar la selección del árbol con el concepto de carpeta actual de la aplicación
  (`carpeta_seleccionada` como única fuente de verdad), reflejándola en la interfaz, sin iniciar
  escaneos ni modificar el catálogo ni el panel derecho.
- **Archivos creados:**
  - `prueba_carpeta_actual.py` — 17 verificaciones: selección en el árbol → carpeta y etiqueta de la
    app actualizadas, sin escaneo, tarjetas intactas; repetición de la misma carpeta sin cambios
    (guard directo); `seleccionar_ruta` sobre ruta no cargada sin excepción ni cambios y sobre ruta
    cargada con sincronización; diálogo (cancelación conserva, ruta inválida con mensaje,
    persistencia intacta, sincroniza el árbol); botón "Escanear carpeta" solo visual; `_total_catalogo`
    intacto; botón "Seleccionar carpeta" funcional.
- **Archivos modificados:**
  - `visor_videos.py` — árbol guardado como `self.arbol_navegacion`; señal `ruta_seleccionada`
    conectada a `_al_carpeta_actual_arbol` (valida `os.path.isdir`, ignora repeticiones, asigna
    `carpeta_seleccionada`, actualiza `etiqueta_carpeta`, limpia mensaje, rearma botones; sin
    persistencia, tareas ni catálogo). `seleccionar_carpeta()` (diálogo) conserva su comportamiento
    e incorpora `self.arbol_navegacion.seleccionar_ruta(ruta_absoluta)`; la restauración de arranque
    también sincroniza el árbol.
  - `arbol_navegacion.py` — método público `seleccionar_ruta(ruta)`: busca solo entre nodos ya
    cargados (`_buscar_ruta`, recursión en memoria sin tocar el sistema de archivos), expande
    ancestros cargados y selecciona; si no está, no modifica la selección ni lanza. Docstring
    actualizado a la Etapa 2.4.
  - `prueba_seleccion_arbol.py`, `prueba_expansion_carpetas.py`, `prueba_arbol_navegacion.py` —
    actualizadas por el cambio de comportamiento intencional (seleccionar en el árbol ahora
    establece la carpeta de la app).
  - `DOCUMENTO_TECNICO.md` — módulo y visor documentados con la integración, `seleccionar_ruta` y la
    fuente única de verdad; dirección futura y árbol de directorios actualizados.
  - `ESTADO_PROYECTO.md` — última etapa aprobada y próxima etapa actualizadas; nuevo hito.
  - `ROADMAP.md` — Etapa 2.4 marcada como implementada.
- **Pruebas:** `prueba_carpeta_actual.py` 17/17. Regresiones: `prueba_seleccion_arbol.py` 24/24,
  `prueba_expansion_carpetas.py` 34/34, `prueba_arbol_navegacion.py` OK, `prueba_seleccion_carpeta.py`
  26/26, `prueba_smoke.py` OK, `prueba_escaneo_interfaz.py` 36/36. Ejecución real de `visor_videos.py`
  con cierre limpio (`exit 0`): selección de `C:\Users\Marcos Casa` reflejada en etiqueta sin escaneo.
- **Resultado:** Seleccionar una carpeta en el árbol actualiza la carpeta activa de la aplicación y
  la etiqueta; el diálogo sigue funcionando igual y sincroniza el árbol cuando el nodo está cargado;
  no se inicia ningún escaneo y el catálogo, SQLite y el panel derecho permanecen intactos.
- **Commit:** "Integrar la seleccion del arbol con la carpeta activa de la aplicacion (Etapa 2.4)"
- **Decisiones importantes:**
  1. **`carpeta_seleccionada` como única fuente de verdad**: el árbol la cambia y la refleja, pero
     `carpeta_actual()` solo representa el estado interno del widget; no hay copia paralela.
  2. **`seleccionar_ruta` sin tocar el disco**: solo busca entre nodos ya cargados; no expande ramas
     inexistentes, no carga carpetas nuevas ni recorre el sistema de archivos.
  3. **Sin efectos secundarios**: el handler actualiza únicamente el estado visual y de botones; no
     inicia tareas, no emite señales adicionales y no toca catálogo, tarjetas ni SQLite.
  4. **Guard de repetición**: ignorar selecciones repetidas evita trabajo innecesario.

---

## 49. Selección funcional del árbol de navegación (Etapa 2.3)

- **Fecha:** 2026-08-06
- **Objetivo:** Implementar la navegación funcional del árbol: seleccionar discos y carpetas con
  resaltado visual, conservar la carpeta actual dentro del propio árbol y exponerla mediante una
  interfaz limpia (`carpeta_actual()`), manteniendo el árbol completamente desacoplado del catálogo.
- **Archivos creados:**
  - `prueba_seleccion_arbol.py` — 24 verificaciones: selección de disco y carpeta (ruta, visual y
    señal), `carpeta_actual()` inicial `None`, modo `SingleSelection`, raíz "Este equipo" y
    placeholder excluidos (no modifican ni emiten), selección profunda, conservación al
    contraer/expandir sin emisiones duplicadas, señal siempre con rutas válidas; integración en
    `VisorVideos` (sin cambio de carpeta/etiqueta, gestor inactivo, sin pendientes, tarjetas
    intactas, splitter redimensionable).
- **Archivos modificados:**
  - `arbol_navegacion.py` — `SingleSelection` (reemplaza `NoSelection`); señal de clase
    `ruta_seleccionada = Signal(str)` (solo notificación); método público `carpeta_actual()` y
    estado `_ruta_actual`; handler `_al_cambiar_actual` conectado a `currentItemChanged` con
    `_ruta_valida()` (excluye raíz sin `ROL_RUTA` y placeholders con `ROL_PLACEHOLDER`); al
    contraer un ancestro, si el ítem anterior quedó oculto (`anterior.isHidden()`) se conserva
    `_ruta_actual` sin reemitir. Sin restauración visual automática de la selección (decisión de
    diseño).
  - `prueba_expansion_carpetas.py` — aserción `widget_sin_seleccion` (NoSelection) actualizada a
    `widget_seleccion_simple` (SingleSelection).
  - `DOCUMENTO_TECNICO.md` — módulo documentado con selección funcional, señal, `carpeta_actual()`
    y exclusión de raíz/placeholders; infraestructura de paneles, dirección futura y árbol de
    directorios actualizados.
  - `ESTADO_PROYECTO.md` — última etapa aprobada y próxima etapa actualizadas; nuevo hito.
  - `ROADMAP.md` — Etapa 2.3 marcada como implementada.
- **Pruebas:** `prueba_seleccion_arbol.py` 24/24. Regresiones: `prueba_expansion_carpetas.py`
  33/33, `prueba_arbol_navegacion.py` OK, `prueba_smoke.py` OK, `prueba_escaneo_interfaz.py`
  36/36. Ejecución real de `visor_videos.py` con cierre limpio (`exit 0`): selección de `C:\Users`
  con `carpeta_actual()=C:\Users`, panel derecho sin cambios.
- **Resultado:** El usuario puede seleccionar discos y carpetas con resaltado visual; la carpeta
  actual queda en el árbol (`carpeta_actual()`); expandir/contraer conserva la selección; la raíz y
  los placeholders nunca son carpetas válidas; la señal no está conectada a nada y el catálogo, el
  panel derecho, SQLite y el pipeline no sufren ningún cambio.
- **Commit:** "Implementar seleccion funcional en el arbol de navegacion (Etapa 2.3)"
- **Decisiones importantes:**
  1. **`carpeta_actual()` como interfaz oficial**: la señal `ruta_seleccionada` es solo notificación;
     las etapas futuras consultarán el estado mediante el método.
  2. **Simplicidad sobre restauración preventiva**: no se implementa búsqueda/restauración visual de
     la selección al re-expandir; basta conservar `_ruta_actual` (si Qt pierde la selección visual,
     el estado interno queda correcto).
  3. **Raíz y placeholders excluidos**: `_ruta_valida()` solo acepta nodos con `ROL_RUTA` real y sin
     `ROL_PLACEHOLDER`.

---

## 48. Expansión de discos y carpetas con carga diferida (Etapa 2.2)

- **Fecha:** 2026-08-06
- **Objetivo:** Permitir expandir los discos y visualizar las carpetas contenidas en cada disco,
  manteniendo el árbol pasivo y desacoplado del catálogo. Carga diferida estricta: al expandir un
  nodo se consultan únicamente sus hijos inmediatos, sin recorrer el árbol completo al iniciar la
  aplicación.
- **Archivos creados:**
  - `prueba_expansion_carpetas.py` — 33 verificaciones: `carpetas_de` (solo directorios, orden
    insensible a mayúsculas, vacío/inexistente/archivo/permiso denegado → `[]`); widget con disco
    simulado (carga diferida real: 0 llamadas al construir, placeholder previo, un nivel por
    expansión, re-expansión sin duplicados ni recarga, carpeta vacía sin hijos, raíz sin recarga,
    `NoSelection`, carpeta inaccesible sin excepción); integración en `VisorVideos` (expansión sin
    cambio de carpeta/etiqueta, gestor inactivo, sin pendientes, tarjetas intactas, clic sin acción,
    splitter redimensionable) y medición del tiempo de apertura.
- **Archivos modificados:**
  - `arbol_navegacion.py` — nueva función pura `carpetas_de(ruta)` (subdirectorios inmediatos
    ordenados con `sorted(..., key=str.lower)`; `[]` ante cualquier `OSError`); `ArbolNavegacion`
    con **carga diferida por placeholder** (`itemExpanded` interno → `_al_expandir`/`_cargar`, un
    solo nivel por expansión), estado de carga en el nodo (`ROL_CARGADO = Qt.UserRole + 2`, no en
    `id(item)`), ruta absoluta por nodo (`ROL_RUTA = Qt.UserRole + 1`) y placeholder marcado
    (`ROL_PLACEHOLDER = Qt.UserRole + 3`); protección defensiva ante `OSError` en `_cargar`;
    `NoSelection` y pasividad conservadas.
  - `DOCUMENTO_TECNICO.md` — módulo documentado con `carpetas_de`, roles y mecanismo de carga
    diferida; infraestructura de paneles, dirección futura y árbol de directorios actualizados.
  - `ESTADO_PROYECTO.md` — última etapa aprobada y próxima etapa actualizadas; nuevo hito.
  - `ROADMAP.md` — Etapa 2.2 marcada como implementada.
- **Pruebas:** `prueba_expansion_carpetas.py` 33/33. Regresiones: `prueba_arbol_navegacion.py` OK,
  `prueba_smoke.py` OK, `prueba_escaneo_interfaz.py` 36/36. Ejecución real de `visor_videos.py` con
  cierre limpio (`exit 0`) y apertura en ~0.5 s (sin escaneo de directorios al iniciar).
- **Resultado:** Los discos se expanden mostrando solo sus carpetas de primer nivel; cada carpeta
  se expande a su vez cargando solo su nivel; re-expandir no duplica; carpetas vacías e inaccesibles
  no rompen la exploración; el árbol no dispara ninguna acción sobre el catálogo. El panel derecho
  funciona igual y el splitter se redimensiona normalmente.
- **Commit:** "Implementar expansion de discos y carpetas con carga diferida (Etapa 2.2)"
- **Decisiones importantes:**
  1. **Estado de carga en el nodo** (`ROL_CARGADO`), no en `id(item)`: el estado pertenece al item y
     no a la identidad temporal del objeto Python.
  2. **Un solo nivel por expansión**: `_cargar` consulta solo los hijos inmediatos; nunca recorre el
     árbol completo ni precalcula niveles posteriores.
  3. **Tolerancia total a `OSError`**: `carpetas_de` devuelve `[]` ante cualquier error de acceso y
     `_cargar` protege además la llamada.
  4. **Orden consistente**: orden alfabético insensible a mayúsculas (`sorted(..., key=str.lower)`).
  5. **Ruta absoluta por nodo en `ROL_RUTA`**: base preparada para las Etapas 2.3 (navegación) y 2.4
     (selección de carpeta).

---

## 47. Árbol de navegación en el panel izquierdo (Etapa 2.1)

- **Fecha:** 2026-08-06
- **Objetivo:** Reemplazar el placeholder del panel izquierdo por un árbol real que constituya la
  infraestructura inicial del futuro Centro de Navegación. Mostrar únicamente el nodo raíz "Este
  equipo" y los discos disponibles del sistema. Sin navegación, sin escaneo, sin selección
  funcional y sin integración con lógica existente.
- **Archivos creados:**
  - `arbol_navegacion.py` — módulo de interfaz con `discos_disponibles()` (enumeración por
    `os.path.exists` sobre A–Z, solo Windows, sin dependencias externas ni lógica de UI) y
    `ArbolNavegacion(QTreeWidget)` (header oculto, `NoSelection`, raíz "Este equipo" expandida y un
    hijo por disco). Árbol completamente pasivo: sin señales, sin slots y sin navegación.
  - `prueba_arbol_navegacion.py` — verificación de la etapa: raíz "Este equipo", discos
    coincidentes con el sistema, placeholder eliminado, panel derecho funcional, splitter
    redimensionable, clic sobre disco sin ninguna acción y captura de pantalla.
- **Archivos modificados:**
  - `visor_videos.py` — import de `ArbolNavegacion` y reemplazo del `QLabel` placeholder por
    `ArbolNavegacion()` en el panel izquierdo del QSplitter. Sin cambios en el panel derecho ni en
    el pipeline.
  - `DOCUMENTO_TECNICO.md` — nuevo módulo documentado; infraestructura de paneles y constructor
    actualizados con el árbol; sección de dirección futura actualizada; árbol de directorios
    actualizado.
  - `ESTADO_PROYECTO.md` — etapa registrada como completada, actualizadas última etapa aprobada y
    próxima etapa.
  - `ROADMAP.md` — Etapa 2.1 marcada como implementada.
- **Pruebas:** `prueba_arbol_navegacion.py` OK. Regresiones: `prueba_smoke.py` OK,
  `prueba_escaneo_interfaz.py` 36/36, `prueba_persistencia_carpeta.py` 20/20,
  `prueba_cantidad_previews.py` 14/14, `prueba_seleccion_visual.py` OK. Ejecución real de
  `visor_videos.py` con cierre limpio (`exit 0`) y captura programática.
- **Resultado:** El placeholder desapareció y el panel izquierdo muestra el árbol real ("Este
  equipo" → `C:\`) sin ninguna acción al hacer clic. El panel derecho funciona igual y el splitter
  se redimensiona normalmente. Sin carpetas, sin navegación, sin escaneo ni integración (etapas
  siguientes).
- **Commit:** "Implementar arbol de navegacion en el panel izquierdo (Etapa 2.1: Este equipo y discos)"
- **Decisiones importantes:**
  1. **Módulo propio `arbol_navegacion.py`** — infraestructura nueva, no refactorización:
     encapsula la enumeración de discos (lógica pura, sin Qt) y el widget, respetando la
     separación interfaz/lógica (Regla 7) y dejando la base extensible del Centro de Navegación.
  2. **Enumeración por `os.path.exists` sobre A–Z** (no `GetLogicalDrives`): mecanismo stdlib,
     sin dependencias externas, separado de la interfaz.
  3. **Árbol pasivo con `NoSelection`**: el clic no produce ninguna acción funcional; el
     `currentItem` interno de Qt puede cambiar pero no hay highlight ni señales conectadas.

---

## 46. Infraestructura de paneles (QSplitter)

- **Fecha:** 2026-08-06
- **Objetivo:** Implementar la infraestructura de la nueva interfaz mediante un QSplitter
  horizontal que divida la ventana en panel izquierdo de navegación (placeholder) y panel
  derecho con la interfaz actual completa. Etapa exclusivamente estructural, sin
  funcionalidades nuevas.
- **Archivos modificados:**
  - `visor_videos.py` — agregado `QSplitter` y `QSize` a los imports; nueva clase
    `PanelPrincipal(QWidget)` con `minimumSizeHint()` anulado a `QSize(0, 0)` (ver decisión
    arquitectónica abajo); constructor de `VisorVideos` modificado para crear el QSplitter
    con panel izquierdo placeholder (`QWidget`, minWidth=80, maxWidth=400, `QLabel` "Panel
    de navegacion") y panel derecho `PanelPrincipal`; `setHandleWidth(8)` para usabilidad;
    `splitter.handle(1).setCursor(Qt.SplitHCursor)` exclusivamente sobre el handle.
  - `DOCUMENTO_TECNICO.md` — documentada la infraestructura de paneles, `PanelPrincipal` y
    la decisión de anular `minimumSizeHint`.
  - `ESTADO_PROYECTO.md` — etapa registrada como completada, actualizada última etapa
    aprobada y próxima etapa.
- **Pruebas:** `prueba_smoke.py` OK (7 secciones sin regresiones). Verificación manual:
  splitter arrastrable con el mouse, cursor cambia solo sobre el handle, estilo visual
  nativo de Windows, sin scroll horizontal innecesario, catálogo funcionando exactamente
  igual.
- **Resultado:** QSplitter funcional integrado como infraestructura permanente. Panel
  izquierdo placeholder sin lógica. Panel derecho conserva el 100% del comportamiento
  existente. Barra divisoria cómoda de agarrar (8 px) con cursor de redimensionamiento.
  Sin colores ni estilos personalizados.
- **Commit:** "Incorporar infraestructura de paneles con QSplitter (panel izquierdo placeholder + PanelPrincipal)"
- **Decisiones importantes:**
  1. **`PanelPrincipal.minimumSizeHint()` → `QSize(0, 0)`:** El `minimumSizeHint` por
     defecto del panel derecho (~720 px) está dominado por la barra de herramientas
     `fila_carpeta` (8 widgets: botones, checkbox, combo, labels) cuyo `minimumSizeHint`
     combinado fuerza un mínimo de ~703 px + márgenes. Sin la anulación, el QSplitter usa
     ese valor como tamaño mínimo efectivo, bloqueando el arrastre del divisor hacia la
     derecha porque el panel ya está en su mínimo. La anulación a `(0, 0)` permite que el
     splitter solo respete el `minimumWidth` del panel izquierdo (80 px), habilitando el
     arrastre libre en ambas direcciones. Se evaluaron y descartaron dos alternativas:
     `setMinimumWidth(0)` (no funciona porque Qt usa `max(minimumSizeHint, minimumWidth)`)
     y `QSizePolicy.Ignored` (tiene efectos laterales sobre cualquier layout padre, no
     solo el splitter).
  2. **`handleWidth=8` (no 5):** El ancho predeterminado de 5 px resultó demasiado
     delgado para tomar con el mouse en Windows 11/PySide6 6.11.1. Ocho píxeles conserva
     el estilo nativo y es cómodo de agarrar.
  3. **Cursor exclusivo sobre el handle:** `splitter.handle(1).setCursor(Qt.SplitHCursor)`
     asigna el cursor de redimensionamiento únicamente al `QSplitterHandle`, no al splitter
     completo, evitando que el cursor ↔ aparezca sobre toda la aplicación.

---

## 45. Redefinición de la dirección futura de la interfaz

- **Fecha:** 2026-08-05
- **Tipo:** Decisión de producto (no implica cambios de código).
- **Descripción:** Durante el cierre del ciclo de desarrollo de la Beta
  1.0 se redefinió la dirección futura de la interfaz de usuario. Se
  acordó evolucionar hacia una **interfaz modular basada en paneles
  independientes** (QSplitter), con un árbol de carpetas como mecanismo
  principal de navegación y la posibilidad de incorporar progresivamente
  paneles de propiedades, favoritos, etiquetas e IA.
- **Próximas líneas de trabajo:** infraestructura de paneles, árbol de
  carpetas, navegación desde el árbol, tarjetas expandibles,
  ordenamientos y organización.
- **Documentos actualizados:**
  - `VISION_PRODUCTO.md` — ampliada la sección de filosofía del
    producto y agregados los principios de diseño.
  - `ROADMAP.md` — agregadas las secciones «Próximas líneas de trabajo
    previstas» e «Infraestructura futura»; ampliada «Experiencia de
    usuario» con tarjetas expandibles y scroll horizontal.
  - `DOCUMENTO_TECNICO.md` — agregada la sección «Dirección
    arquitectónica futura» con la infraestructura prevista de paneles.
- **Resultado:** La documentación del proyecto refleja ahora la visión
  de largo plazo y permite que cualquier persona, al leer
  `VISION_PRODUCTO.md`, `ROADMAP.md` y `DOCUMENTO_TECNICO.md`,
  comprenda hacia dónde evoluciona el producto y cuál será la primera
  etapa del próximo ciclo de desarrollo.
- **Decisiones importantes:** El proyecto deja de concebirse únicamente
  como un visor de tarjetas y pasa a proyectarse como un entorno de
  trabajo. La exploración visual sigue siendo el objetivo principal;
  la reproducción permanece como función secundaria.

---

## 44. Cantidad configurable de previews visibles (3/5/7/9)

- **Fecha:** 2026-08-05
- **Objetivo:** Permitir al usuario elegir cuántas previews mostrar por video (3, 5, 7 o 9), con persistencia y actualización inmediata de la interfaz sin requerir reescaneo.
- **Archivos modificados:**
  - `escanear_videos.py` — `CANTIDAD_PREVIEWS` de constante `3` a mutable con valor por defecto `CANTIDAD_PREVIEWS_POR_DEFECTO`; setter `configurar_cantidad_previews(n)`; `_nombre_seguro` aplicado en `_es_archivo_preview`, `contar_miniaturas` y `miniatura_reutilizable` (corrección de bug colateral de la etapa de subcarpetas).
  - `configuracion.py` — clave `CLAVE_CANTIDAD_PREVIEWS`; `guardar_cantidad_previews(n, ruta_config)` y `obtener_cantidad_previews(ruta_config)` (default 3, mismo patrón atómico que las demás preferencias).
  - `visor_videos.py` — `QComboBox` con opciones 3/5/7/9; restauración al iniciar mediante `obtener_cantidad_previews` y configuración de `CANTIDAD_PREVIEWS`; handler `_al_cambiar_cantidad_previews` que persiste y actualiza la interfaz; método `Tarjeta.ajustar_previews(cantidad)` que muestra/oculta etiquetas y recarga previews desde caché instantáneamente; `_encolar_previews` corregido para usar `len(existentes) >= CANTIDAD_PREVIEWS` como criterio de completitud; `Tarjeta.__init__` usa `escanear_videos.CANTIDAD_PREVIEWS` dinámicamente.
  - `DOCUMENTO_TECNICO.md` — `CANTIDAD_PREVIEWS` documentado como configurable; `configuracion.py` documentado con `cantidad_previews`.
- **Archivos creados:**
  - `prueba_cantidad_previews.py` — 14 pruebas: mutable, `previews_existentes` con nueva cantidad, persistencia, default, UI con combo, restauración, escenarios 9→3, 3→7, 9→5→9, 9→9 (sin reescaneo en todos los casos).
- **Pruebas:** `prueba_cantidad_previews.py` 14/14, `prueba_previews_progresivas.py` 16/16, `prueba_smoke.py` OK.
- **Correcciones durante la etapa:**
  1. `_encolar_previews` usaba «tiene algún preview» como criterio → cambiado a «tiene todos los previews configurados», evitando que labels sobrantes quedaran en «Generando preview…» indefinidamente.
  2. `_es_archivo_preview`, `contar_miniaturas` y `miniatura_reutilizable` no usaban `_nombre_seguro`, causando mismatch con nombres de archivo sanitizados para videos en subcarpetas.
  3. La interfaz requería reescaneo para reflejar el cambio de cantidad → `Tarjeta.ajustar_previews` aplica el cambio inmediatamente mostrando/ocultando etiquetas y recargando desde caché.
- **Resultado:** Cantidad configurable con cambio visual inmediato. Separación clara entre cantidad visible (controlada por el usuario) y cantidad generada (controlada por el pipeline). Sin regeneración automática en segundo plano. Sin límites artificiales.
- **Commit:** "Agregar cantidad configurable de previews visibles (3/5/7/9) con persistencia"
- **Decisiones importantes:** `CANTIDAD_PREVIEWS` como variable de módulo mutable permite que `previews_existentes` y `previews_faltantes` se adapten automáticamente. `ajustar_previews` usa `setVisible(i < cantidad)` para ocultar/mostrar etiquetas sin reconstruir la tarjeta.

## 43. Persistencia de la preferencia "Incluir subcarpetas"

- **Fecha:** 2026-08-05
- **Objetivo:** Persistir la preferencia de la casilla "Incluir subcarpetas" entre ejecuciones de la aplicación, reutilizando el sistema de configuración existente.
- **Archivos modificados:**
  - `configuracion.py` — nueva clave `CLAVE_SUBCARPETAS = "incluir_subcarpetas"`; `guardar_preferencia_subcarpetas(activado, ruta_config)` persiste el booleano en el JSON compartido (misma escritura atómica `.tmp` + `os.replace`); `obtener_preferencia_subcarpetas(ruta_config)` restaura el valor (devuelve `False` por defecto si el archivo no existe, la clave falta o el valor no es booleano).
  - `visor_videos.py` — importa `guardar_preferencia_subcarpetas` y `obtener_preferencia_subcarpetas`; conecta `stateChanged` del checkbox a `_al_cambiar_subcarpetas`; restaura el estado del checkbox al iniciar con `obtener_preferencia_subcarpetas(self._ruta_config)`; método `_al_cambiar_subcarpetas` persiste inmediatamente el nuevo estado.
  - `DOCUMENTO_TECNICO.md` — `configuracion.py` documentado con `incluir_subcarpetas`; checkbox documentado con persistencia y restauración; `prueba_persistencia_subcarpetas.py` agregado al árbol.
- **Archivos creados:**
  - `prueba_persistencia_subcarpetas.py` — 10 pruebas: guardar True/False en JSON, obtener sin archivo, obtener sin clave, round-trip, restauración al iniciar True/False, persistencia al cambiar checkbox.
- **Pruebas:** `prueba_persistencia_subcarpetas.py` 10/10, `prueba_escaneo_subcarpetas.py` 12/12, `prueba_escaneo_interfaz.py` 36/36, `prueba_persistencia_carpeta.py` 20/20, `prueba_smoke.py` OK.
- **Resultado:** Preferencia persistida y restaurada correctamente. La casilla conserva su estado entre ejecuciones. Integración limpia con el sistema JSON existente (misma escritura atómica, misma clave). Sin perfiles de usuario, múltiples configuraciones ni otras preferencias en esta etapa.
- **Commit:** "Persistir preferencia 'Incluir subcarpetas' entre ejecuciones"
- **Decisiones importantes:** Mismo patrón que `ultima_carpeta`: clave en el mismo JSON compartido, escritura atómica con `.tmp` + `os.replace`, restauración tolerante (devuelve `False` ante cualquier anomalía). La conexión `stateChanged` persiste inmediatamente sin esperar al escaneo.

## 42. Escaneo opcional de subcarpetas

- **Fecha:** 2026-08-05
- **Objetivo:** Incorporar la opción de incluir o excluir subcarpetas durante el escaneo de videos, una funcionalidad prevista en el ROADMAP original.
- **Archivos modificados:**
  - `escanear_videos.py` — flag `_ESCANEO_RECURSIVO` a nivel módulo, setter `configurar_escaneo_recursivo(activado)`, función `_nombre_seguro(nombre)` que reemplaza `os.sep` y `/` por `_`, `escanear_videos(carpeta)` ampliado con `os.walk` cuando el flag está activo (devuelve rutas relativas), `ruta_miniatura` y `ruta_preview` usan `_nombre_seguro` para mantener planos los nombres de archivo con nombres de video que incluyen subcarpetas.
  - `visor_videos.py` — importa `QCheckBox`, `_nombre_seguro` y `configurar_escaneo_recursivo` desde `escanear_videos`; casilla `incluir_subcarpetas` (`QCheckBox` "Incluir subcarpetas") junto a los botones de carpeta y escaneo; `iniciar_escaneo()` llama a `configurar_escaneo_recursivo(self.incluir_subcarpetas.isChecked())` antes de crear la tarea; `miniatura_principal` usa `_nombre_seguro`.
  - `prueba_escaneo_interfaz.py` — test 31 actualizado: verifica `configurar_escaneo_recursivo` y `_nombre_seguro` en lugar de prohibir el módulo `escanear_videos`.
  - `DOCUMENTO_TECNICO.md` — `escanear_videos` documentado con modo recursivo y `_nombre_seguro`; `boton_escanear` actualizado con la casilla.
- **Archivos creados:**
  - `prueba_escaneo_subcarpetas.py` — 12 pruebas: flag, escaneo flat, recursivo con rutas relativas, restauración a flat, `_nombre_seguro` con slash/backslash/plano, `ruta_miniatura` y `ruta_preview` seguras, checkbox en UI.
- **Pruebas:** `prueba_escaneo_subcarpetas.py` 12/12, `prueba_escaneo.py` 12/12, `prueba_escaneo_interfaz.py` 36/36, `prueba_smoke.py` OK.
- **Resultado:** Escaneo recursivo funcional con rutas relativas. Miniaturas y previews con nombres seguros (separadores reemplazados por `_`). Sin persistencia de la preferencia, filtros por profundidad ni exclusiones de carpetas en esta etapa.
- **Commit:** "Agregar escaneo recursivo opcional de subcarpetas"
- **Decisiones importantes:** Flag global `_ESCANEO_RECURSIVO` como solución más simple dado que solo hay un escaneo a la vez (garantizado por el `GestorTareas`). `_nombre_seguro` permite mantener el sistema de archivos de miniaturas plano sin necesidad de crear subdirectorios. La importación directa desde `escanear_videos` en `visor_videos.py` fue necesaria porque no se podía modificar `tareas_videos.py` para reexportar las nuevas funciones.

## 41. Abrir carpetas de los seleccionados

- **Fecha:** 2026-08-05
- **Objetivo:** Agregar al menú contextual una quinta acción que abra las carpetas contenedoras de todos los videos seleccionados, con deduplicación para no abrir la misma carpeta más de una vez.
- **Archivos modificados:**
  - `visor_videos.py` — quinta acción "Abrir carpetas de los seleccionados" en `_mostrar_menu_contextual`; nuevo método `_abrir_carpetas_seleccionados` que itera `self.tarjetas_visibles()`, filtra por `_nombres_seleccionados`, calcula `os.path.dirname` de cada ruta, deduplica con `dict.fromkeys` (preserva orden de primera aparición) y abre cada carpeta única con `os.startfile`.
  - `DOCUMENTO_TECNICO.md` — menú contextual documentado con 5 acciones; agregado `prueba_abrir_carpetas_seleccionados.py` al árbol.
- **Archivos creados:**
  - `prueba_abrir_carpetas_seleccionados.py` — 10 pruebas: existencia del método, único seleccionado, múltiples misma carpeta (1 sola apertura), sin carpeta, sin selección, "Abrir carpeta" original intacta, 5 seleccionados deduplicados a 1.
- **Pruebas:** `prueba_abrir_carpetas_seleccionados.py` 10/10, `prueba_menu_contextual.py` 18/18, `prueba_copiar_rutas_seleccionados.py` 8/8, `prueba_shift_clic.py` 28/28, `prueba_smoke.py` OK.
- **Resultado:** Quinta acción en el menú contextual funcional. Carpetas abiertas una sola vez cada una mediante `dict.fromkeys`. La acción original "Abrir carpeta" permanece intacta. Sin confirmaciones ni límites artificiales.
- **Commit:** "Agregar accion: abrir carpetas de los seleccionados al menu contextual"
- **Decisiones importantes:** `dict.fromkeys` preserva el orden visible (primera aparición) y elimina duplicados de forma natural. La deduplicación opera sobre `os.path.dirname` de las rutas absolutas.

## 40. Copiar rutas de los seleccionados al portapapeles

- **Fecha:** 2026-08-05
- **Objetivo:** Agregar al menú contextual una cuarta acción que copie al portapapeles las rutas completas de todos los videos seleccionados, constituyendo la primera operación real sobre una selección múltiple.
- **Archivos modificados:**
  - `visor_videos.py` — cuarta acción "Copiar rutas de los seleccionados" en `_mostrar_menu_contextual`; nuevo método `_copiar_rutas_seleccionados` que itera `self.tarjetas_visibles()`, filtra por `self._nombres_seleccionados`, construye las rutas absolutas y las copia al portapapeles separadas por `\n`; el método existente `_copiar_ruta` permanece sin cambios.
  - `DOCUMENTO_TECNICO.md` — menú contextual documentado con 4 acciones; agregado `prueba_copiar_rutas_seleccionados.py` al árbol.
- **Archivos creados:**
  - `prueba_copiar_rutas_seleccionados.py` — 8 pruebas: elemento único, múltiples con orden visible, sin carpeta, sin selección, "Copiar ruta" original intacto, todos seleccionados, existencia del método.
- **Pruebas:** `prueba_copiar_rutas_seleccionados.py` 8/8, `prueba_menu_contextual.py` 18/18, `prueba_shift_clic.py` 28/28, `prueba_seleccion.py` 28/28, `prueba_doble_clic.py` 14/14, `prueba_smoke.py` OK.
- **Resultado:** Cuarta acción en el menú contextual funcional. Las rutas se copian en orden visible, una por línea. La acción original "Copiar ruta" sigue copiando únicamente la ruta del video sobre el que se abrió el menú. Sin exportación a archivos, copiar nombres ni metadatos.
- **Commit:** "Agregar acción "Copiar rutas de los seleccionados" al menú contextual"
- **Decisiones importantes:** Separación clara entre "Copiar ruta" (individual, la del video cliqueado) y "Copiar rutas de los seleccionados" (colectiva, por selección). La nueva acción es la primera operación real sobre selección múltiple en el proyecto.

## 39. Selección por rango con Shift+clic

- **Fecha:** 2026-08-05
- **Objetivo:** Incorporar selección por rango mediante Shift+clic, con comportamiento estándar de Windows, reutilizando el sistema de selección ya existente.
- **Archivos modificados:**
  - `visor_videos.py` — nueva señal `seleccion_por_rango = Signal(str)` en `Tarjeta`; `mousePressEvent` detecta `Qt.ShiftModifier` y enruta a `seleccion_por_rango` o `seleccionada` según corresponda; atributo `_ancla_seleccion` en `VisorVideos` (rastrea la última tarjeta seleccionada sin Shift); método `_al_seleccion_por_rango(nombre)` que calcula el rango sobre `self.visibles` (orden visible) entre el ancla y la tarjeta clickeada; sin ancla o ancla fuera de visibles → equivale a clic normal; el ancla no se actualiza durante el rango; `_reemplazar_tarjetas` limpia el ancla; conexión de la nueva señal en `_crear_tarjetas` y `_agregar_tarjetas`.
  - `DOCUMENTO_TECNICO.md` — sección de selección ampliada con Shift+clic, ancla, rango por orden visible y limpieza en reconstrucción.
- **Archivos creados:**
  - `prueba_shift_clic.py` — 28 pruebas: señal, atributo, método, Shift+clic sin ancla, rango hacia abajo, rango hacia arriba, ancla no se modifica, Ctrl+clic compatible, doble clic, emisión de señal, ancla fuera de visibles, limpieza en `_reemplazar_tarjetas`.
- **Pruebas:** `prueba_shift_clic.py` 28/28, `prueba_seleccion.py` 28/28, `prueba_restauracion_seleccion.py` 15/15, `prueba_menu_contextual.py` 18/18, `prueba_doble_clic.py` 14/14, `prueba_smoke.py` OK.
- **Resultado:** Shift+clic funcional en ambas direcciones (hacia arriba y hacia abajo). Ancla inmutable durante el rango. Compatibilidad total con selección simple, Ctrl+clic, menú contextual y doble clic. Sin Ctrl+Shift+clic, selección con teclado ni atajos adicionales.
- **Commit:** "Agregar selección por rango con Shift+clic"
- **Decisiones importantes:** Señal independiente `seleccion_por_rango` para no modificar el contrato de `seleccionada`. El rango opera sobre el orden visible (`self.visibles`), no sobre el orden de creación. El ancla se descarta en `_reemplazar_tarjetas` porque las referencias a las tarjetas antiguas se pierden.

## 38. Restauración automática de la selección tras reconstruir la lista de tarjetas

- **Fecha:** 2026-08-05
- **Objetivo:** Restaurar la selección visual después de `_reemplazar_tarjetas` (recarga tras sincronización) sin perder el estado de selección del usuario.
- **Archivos modificados:**
  - `visor_videos.py` — `_reemplazar_tarjetas` ahora preserva `_nombres_seleccionados` antes de limpiar y, tras crear las nuevas tarjetas, restaura solo los nombres que siguen existiendo (filtrados contra `nombres_nuevos`). Los nombres que desaparecieron del catálogo se descartan silenciosamente.
  - `prueba_seleccion.py` — antiguo test "`_reemplazar_tarjetas` limpia la selección" reemplazado por 3 verificaciones de restauración (28 pruebas totales).
  - `DOCUMENTO_TECNICO.md` — actualizada la descripción de persistencia de selección y agregado `prueba_restauracion_seleccion.py` al árbol.
  - `ESTADO_PROYECTO.md` — deuda técnica actualizada.
- **Archivos creados:**
  - `prueba_restauracion_seleccion.py` — 15 pruebas: restauración simple, múltiple, sin selección previa, nombre ausente, verificación de estilo visual.
- **Pruebas:** `prueba_restauracion_seleccion.py` 15/15, `prueba_seleccion.py` 28/28, `prueba_menu_contextual.py` 18/18, `prueba_doble_clic.py` 14/14, `prueba_smoke.py` OK.
- **Resultado:** La selección se conserva automáticamente al reconstruir la lista de tarjetas. Sin persistencia en disco ni entre ejecuciones. Sin modificar el comportamiento de clic simple, Ctrl+clic, doble clic ni menú contextual.
- **Commit:** "Restaurar automáticamente la selección tras reconstruir la lista de tarjetas"
- **Decisiones importantes:** Se reutiliza `_nombres_seleccionados` y `_marcar_tarjeta` sin nuevas estructuras de datos. El filtrado contra `nombres_nuevos` evita marcas huérfanas. Los nombres desaparecidos se descartan sin error.

## 37. Menú contextual con acciones básicas (abrir, abrir carpeta, copiar ruta)

- **Fecha:** 2026-08-05
- **Objetivo:** Agregar un menú contextual mediante clic derecho sobre las filas de videos, con tres acciones básicas.
- **Archivos modificados:**
  - `visor_videos.py` — nueva señal `menu_contextual = Signal(str)` en `Tarjeta`, manejo de `Qt.RightButton` en `mousePressEvent` (selecciona la tarjeta si no lo estaba, conserva multi-selección), conexión en `_crear_tarjetas` y `_agregar_tarjetas`, método `_mostrar_menu_contextual(nombre)` con `QMenu` de tres acciones, `_abrir_carpeta(nombre)` (`os.startfile` sobre la carpeta seleccionada) y `_copiar_ruta(nombre)` (`QApplication.clipboard().setText` con ruta absoluta).
  - `prueba_doble_clic.py` — test 14 relajado: solo verifica que `os.isfile` no se use directamente (ya no prohíbe `os.startfile`, que ahora se usa legítimamente para abrir carpeta).
  - `DOCUMENTO_TECNICO.md` — actualizada la descripción de `Tarjeta.seleccionada` / `_nombres_seleccionados` con el menú contextual.
  - `ESTADO_PROYECTO.md` — nuevo hito completado, actualización de última etapa aprobada.
  - `ROADMAP.md` — acciones sobre elementos seleccionados marcadas como implementadas.
- **Archivos creados:**
  - `prueba_menu_contextual.py` — 18 pruebas del menú contextual (señal, selección por clic derecho, señal emitida, `_abrir_carpeta`, `_copiar_ruta`, compatibilidad con doble clic y clic izquierdo).
- **Pruebas:** `prueba_menu_contextual.py` 18/18, `prueba_seleccion.py` 26/26, `prueba_seleccion_visual.py` OK, `prueba_doble_clic.py` 14/14, `prueba_smoke.py` OK.
- **Resultado:** Menú contextual funcional con tres acciones. "Abrir" reutiliza exactamente el mecanismo existente de doble clic. "Abrir carpeta" abre el Explorador de Windows. "Copiar ruta" copia la ruta completa al portapapeles. Selección inteligente: clic derecho sobre fila no seleccionada la selecciona; sobre selección múltiple la conserva. Sin eliminar, renombrar, favoritos, etiquetas, acciones masivas ni submenús.
- **Commit:** "Incorporar menú contextual con acciones básicas (abrir, abrir carpeta, copiar ruta)"
- **Decisiones importantes:** `os.startfile` ahora se usa en dos lugares: `apertura_videos.py` (abrir video) y `visor_videos.py._abrir_carpeta` (abrir carpeta). Verificación AST de `visor_videos.py` relajada para permitir este uso legítimo.

## 36. Selección visual de filas (simple y múltiple con Ctrl+clic)

- **Fecha:** 2026-08-05
- **Objetivo:** Incorporar selección visual de filas en la lista de videos, con selección simple y múltiple mediante Ctrl+clic, preparando la base para futuras operaciones sobre elementos seleccionados.
- **Archivos modificados:**
  - `visor_videos.py` — señal `seleccionada(nombre, ctrl)` en `Tarjeta`, `mousePressEvent` con detección de `Qt.ControlModifier`, método `marcar_seleccionada(True/False)` con estilo de borde azul 3px (`ESTILO_SELECCIONADA`), tracking de selección en `VisorVideos` mediante `_nombres_seleccionados` (expuesto como `@property nombres_seleccionados`), métodos `_al_seleccionar_tarjeta` / `_limpiar_seleccion` / `_marcar_tarjeta`, conexión de señal en `_crear_tarjetas` y `_agregar_tarjetas`, limpieza en `_reemplazar_tarjetas`.
  - `DOCUMENTO_TECNICO.md` — nueva entrada documental `Tarjeta.seleccionada` / `_nombres_seleccionados`.
- **Archivos creados:**
  - `prueba_seleccion.py` — 26 pruebas unitarias de selección.
  - `prueba_seleccion_visual.py` — verificación automatizada del comportamiento de selección.
- **Pruebas:** `prueba_seleccion.py` 26/26, verificación visual OK. Regresiones: `prueba_escaneo_interfaz.py` 36/36, `prueba_escaneo_guardado.py` 24/24, `prueba_sincronizacion_interfaz.py` 18/18, `prueba_smoke.py` OK, `prueba_progreso.py` 13/13, `prueba_pagina_siguiente.py` 20/20.
- **Commit:** Aprobado y commiteado (junto con etapa 37).
- **Resultado:** Selección simple (clic reemplaza) y múltiple (Ctrl+clic agrega/quita) con diferencia visual clara (borde azul). La selección persiste al filtrar pero se pierde al reconstruir tarjetas. El doble clic no interfiere con la selección. Sin menús, botones, Shift+clic ni acciones masivas en esta etapa.
- **Decisiones importantes:** `Tarjeta.seleccionada` es señal de clase, no propiedad (la propiedad se eliminó para evitar conflicto con el descriptor del Signal). Base preparada para futuras operaciones sobre `_nombres_seleccionados`.

## 35. Estabilización de la Beta 1.0

- **Fecha:** 2026-08-05
- **Objetivo:** Corregir tres defectos de la Beta 1.0 validados por el usuario con 23 videos reales.
- **Archivos modificados:**
  - `escanear_videos.py` — definición de `_ARGS_SIN_CONSOLA` con `creationflags=subprocess.CREATE_NO_WINDOW` aplicado a todos los `subprocess.run` de FFprobe/FFmpeg.
  - `visor_videos.py` — carga inmediata de previews existentes en `_crear_tarjetas` y `_agregar_tarjetas`; nuevo layout definitivo de `Tarjeta` con datos a la izquierda (maxWidth=240) y 4 imágenes horizontales consecutivas (miniatura + 3 previews) con ancho automático por aspect ratio.
- **Pruebas:** `prueba_filas_horizontales.py` 16/16, `prueba_previews_progresivas.py` 16/16, `prueba_escaneo_interfaz.py` 36/36, `prueba_interfaz_asincrona.py` 29/29, `prueba_pagina_siguiente.py` 20/20, `prueba_recarga_catalogo.py` 19/20 (T13 preexistente), `prueba_sincronizacion_interfaz.py` 18/18, `prueba_doble_clic.py` 14/14.
- **Commit:** "Estabilizar la Beta 1.0 (consola, reescaneo de previews y layout definitivo)"
- **Resultado:** Beta lista para distribución de pruebas. Sin ventanas de consola, previews conservadas tras reescaneo, layout definitivo aprobado.
- **Decisiones importantes:** Estructura del contenedor de imágenes independiente de `CANTIDAD_PREVIEWS` para soportar cualquier número sin rediseñar.

## 34. Empaquetado de la Beta 1.0

- **Fecha:** 2026-08-04
- **Objetivo:** Empaquetar la aplicación como ejecutable portable e instalador de Windows para distribución de pruebas.
- **Archivos creados:**
  - `VisorVideos.exe` + `_internal/` — portable PyInstaller `--onedir --windowed`.
  - `instalador_beta1.0.iss` — script Inno Setup 6.7.3.
  - `VisorVideos_Beta1.0_Setup.exe` — instalador funcional.
- **Archivos modificados:**
  - `rutas.py` — `_directorio_base()` con soporte para `sys.frozen` (resolución de raíz junto al ejecutable en modo portable).
- **Pruebas:** Instalación limpia, primer inicio desde acceso directo, catálogo poblado por la app instalada, desinstalación total, sin regresiones contra el portable.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Ejecutable portable validado con driver funcional completo. Instalador con `biblioteca.db` vacía de esquema vigente, instalación por usuario sin permisos de administrador.
- **Decisiones importantes:** `biblioteca.db` vacía en el instalador (sin datos de desarrollo). FFmpeg/FFprobe no empaquetados: se resuelven por PATH. Instalación en `{localappdata}\Programs`.

## 33. Separación del punto de entrada de producción y del arnés de smoke tests

- **Fecha:** 2026-08-04
- **Objetivo:** Independizar el smoke test del arranque normal para preparar el empaquetado de la Beta.
- **Archivos creados:**
  - `prueba_smoke.py` — arnés de ejecución explícita con `python prueba_smoke.py`, base SQLite temporal, fases: paginación, escaneo + carpeta + sincronización, previews, doble clic y persistencia.
- **Archivos modificados:**
  - `visor_videos.py` — `main()` reducido a bootstrap puro (`QApplication`, `VisorVideos()`, `resize`, `show`, `exec`).
  - Cinco suites de interfaz (`prueba_escaneo_interfaz.py`, `prueba_seleccion_carpeta.py`, `prueba_interfaz_asincrona.py`, `prueba_pagina_siguiente.py`, `prueba_recarga_catalogo.py`) — pasan a invocar `prueba_smoke.py` por subprocess.
- **Pruebas:** Arranque normal sin smoke automático (proceso vivo tras 8 s sin stdout/stderr). Smoke explícito con exit 0.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Aplicación preparada para empaquetado sin ejecutar pruebas al iniciar.
- **Decisiones importantes:** Separación definitiva entre punto de entrada de producción y arnés de verificación.

## 32. Persistencia de la última carpeta seleccionada

- **Fecha:** 2026-08-03
- **Objetivo:** Recordar entre sesiones la carpeta seleccionada por el usuario.
- **Archivos creados:**
  - `configuracion.py` — servicio de persistencia de configuración: `guardar_ultima_carpeta()` (escritura atómica con `.tmp` + `os.replace`), `obtener_ultima_carpeta()` (tolerante: `None` ante ausencia/corrupción/carpeta inexistente), `VARIABLE_ENTORNO = "VISOR_CONFIG"` para aislamiento de pruebas.
  - `prueba_persistencia_carpeta.py` — 20 pruebas.
- **Archivos modificados:**
  - `rutas.py` — añade `ruta_configuracion()` → `configuracion.json`.
  - `visor_videos.py` — constructor ampliado con `ruta_config`, restauración al arranque y persistencia al seleccionar.
  - `.gitignore` — añade `configuracion.json`.
  - 11 módulos de prueba — añaden `_CONFIG_TEMPORAL` + `VISOR_CONFIG` para aislamiento.
- **Pruebas:** 20/20 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Carpeta elegida persistida y restaurada automáticamente. Pruebas aisladas sin tocar archivo real del usuario.
- **Decisiones importantes:** `VISOR_CONFIG` es redirección de ubicación, no bandera de depuración. Persistencia de preferencias generales queda pendiente.

## 31. Apertura del video por doble clic

- **Fecha:** 2026-08-03
- **Objetivo:** Abrir el video con la aplicación predeterminada del sistema mediante doble clic sobre su tarjeta.
- **Archivos creados:**
  - `apertura_videos.py` — módulo de servicio: `abrir_video_con_aplicacion_predeterminada(nombre, carpeta)`, único punto del proyecto que ejecuta `os.startfile`.
  - `prueba_doble_clic.py` — 14 pruebas, incluido AST de `visor_videos.py` con cero referencias a `os.path.isfile`/`os.startfile`.
- **Archivos modificados:**
  - `visor_videos.py` — señal `Tarjeta.doble_clic = Signal(str)`, sobrescritura de `mouseDoubleClickEvent`, handler `_abrir_video(nombre)`, constante `MENSAJE_ERROR_ABRIR`, conexión en `_crear_tarjetas` y `_agregar_tarjetas`.
- **Pruebas:** 14/14 OK. Regresiones 72/72 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Doble clic funcional en tarjetas de carga inicial y páginas adicionales. Apertura aislada del resto de la arquitectura.
- **Decisiones importantes:** `os.startfile` en un único módulo de servicio, verificado por AST.

## 30. Previews progresivas para la Beta 1.0

- **Fecha:** 2026-08-03
- **Objetivo:** Generar tres previews por video (fotogramas al 25/50/75 %) de forma progresiva en segundo plano.
- **Archivos creados:**
  - `prueba_previews_progresivas.py` — 16 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `CANTIDAD_PREVIEWS = 3`, `ruta_preview`, `_es_archivo_preview`, `previews_existentes`, `previews_faltantes`, `calcular_tiempo_preview`, `generar_preview`, `generar_previews_faltantes`.
  - `tareas_videos.py` — `TareaPreviewsProgresivas(TareaBase)`.
  - `visor_videos.py` — segundo `GestorTareas` (`gestor_previews`), cola `_cola_previews`, lotes de `TAMANIO_LOTE_PREVIEWS = 3`, temporizador `_timer_previews` (300 ms), actualización incremental `Tarjeta.actualizar_previews`.
- **Pruebas:** 16/16 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Previews generados incrementalmente sin bloquear la carga del catálogo. Reutilización de miniatura base si FFmpeg falla. Nunca sobrescribe ni elimina archivos.
- **Decisiones importantes:** Segundo `GestorTareas` independiente para no interferir con el pipeline principal. Convención `miniaturas/<prefijo>_preview_NN.jpg`.

## 29. Incorporación y visualización del tamaño de los archivos de video

- **Fecha:** 2026-08-02
- **Objetivo:** Mostrar el tamaño de cada archivo de video en el catálogo.
- **Archivos creados:**
  - `prueba_tamano_archivo.py` — 15 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — añade `tamano_bytes INTEGER` a `COLUMNAS_EXTRA` (migración idempotente), `obtener_tamanos_archivos`, `combinar_registros_con_tamanos`.
  - `tareas_videos.py` — `TareaTamanosArchivos(TareaBase)`.
  - `visor_videos.py` — pipeline a 7 tareas (tamaños entre escaneo y FFprobe), campo "Tamaño" con `formatear_tamano` (B/KB/MB/GB).
- **Pruebas:** 15/15 OK. Regresiones en 5 suites OK. Correcciones de aislamiento T15/T27.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Tamaño de archivo visible en cada fila del catálogo con formato legible.
- **Decisiones importantes:** `tamano_bytes` como columna opcional (NULL si archivo no legible). Migración idempotente sin tocar registros existentes.

## 28. Presentación del catálogo en filas horizontales

- **Fecha:** 2026-08-02
- **Objetivo:** Cambiar la presentación del catálogo a una tarjeta horizontal por video, una fila por video en una única columna.
- **Archivos creados:**
  - `prueba_filas_horizontales.py` — 16 pruebas.
- **Archivos modificados:**
  - `visor_videos.py` — `Tarjeta` con `QHBoxLayout` (miniatura izquierda + columna de campos derecha), eliminación de `COLUMNAS = 2` y `setColumnStretch`.
- **Pruebas:** 16/16 OK. Regresiones `prueba_pagina_siguiente.py` 20/20 y `prueba_recarga_catalogo.py` 20/20 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Layout horizontal definitivo. Solo primera miniatura por video (previews y doble clic incorporados en etapas posteriores).
- **Decisiones importantes:** Sin cambios en datos reales.

## 27. Carga manual de una página adicional del catálogo

- **Fecha:** 2026-08-02
- **Objetivo:** Permitir al usuario cargar manualmente páginas adicionales del catálogo con el botón "Cargar más".
- **Archivos creados:**
  - `prueba_pagina_siguiente.py` — 20 pruebas.
- **Archivos modificados:**
  - `visor_videos.py` — factoría `_crear_tarea_lectura(desplazamiento=0)`, botón `boton_cargar_mas`, `cargar_mas()`, `_agregar_tarjetas(filas)`, estados `_pagina_pendiente`/`tarea_pagina`/`_total_catalogo`, handlers y constante `MENSAJE_ERROR_PAGINA`.
- **Pruebas:** 20/20 OK. Regresiones 98/98 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Páginas adicionales agregadas sin reemplazar existentes y sin duplicados. Sin scroll infinito ni búsqueda en SQL (pendientes).
- **Decisiones importantes:** El reemplazo de tarjetas sigue siendo exclusivo de la recarga tras sincronización.

## 26. Recarga asíncrona del catálogo tras la sincronización

- **Fecha:** 2026-08-02
- **Objetivo:** Recargar automáticamente el catálogo después de una sincronización exitosa.
- **Archivos creados:**
  - `prueba_recarga_catalogo.py` — 20 pruebas.
- **Archivos modificados:**
  - `visor_videos.py` — pipeline a 6 tareas, `_recarga_catalogo_pendiente`/`tarea_recarga_catalogo`, `_reemplazar_tarjetas(filas)`, `_iniciar_recarga_catalogo()`, handlers y constante `MENSAJE_ERROR_RECARGA`.
- **Pruebas:** 20/20 OK. Regresiones 82/82 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Tras sincronización exitosa, las tarjetas se reemplazan con la primera página actualizada. Tarjetas viejas conservadas hasta resultado válido.
- **Decisiones importantes:** La recarga fallida no revierte la sincronización ya confirmada. Sin FFprobe/FFmpeg/miniaturas en la recarga.

## 25. Integración de la sincronización completa en la interfaz

- **Fecha:** 2026-08-02
- **Objetivo:** Lanzar `TareaSincronizacionCatalogo` desde la interfaz tras el guardado exitoso del pipeline.
- **Archivos creados:**
  - `prueba_sincronizacion_interfaz.py` — 18 pruebas.
- **Archivos modificados:**
  - `visor_videos.py` — pipeline a 5 tareas, estados `_sincronizacion_pendiente`/`tarea_sincronizacion`/`resultado_sincronizacion`, handlers, constantes `MENSAJE_SINCRONIZANDO`/`MENSAJE_ERROR_SINCRONIZACION`, `texto_resumen_sincronizacion()`.
  - `prueba_escaneo_guardado.py` — actualizada a cadena de 5 tareas (24 pruebas).
  - `prueba_escaneo_interfaz.py` — actualizada a cadena de 5 tareas (36 pruebas).
- **Pruebas:** 18/18 OK. Regresiones 355/355 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Sincronización completa integrada en la interfaz. Registros ausentes eliminados de SQLite, presentes conservados. Sin recarga de tarjetas en esta etapa.
- **Decisiones importantes:** GUI sin SQLite ni SQL (AST verificado). Sincronización solo tras guardado exitoso.

## 24. Sincronización asíncrona del catálogo (TareaSincronizacionCatalogo)

- **Fecha:** 2026-08-02
- **Objetivo:** Orquestar en segundo plano la secuencia completa de sincronización disco ↔ BD.
- **Archivos creados:**
  - `prueba_sincronizacion_asincrona.py` — 27 pruebas.
- **Archivos modificados:**
  - `tareas_videos.py` — `import escanear_videos as escanear_mod`, clase `TareaSincronizacionCatalogo(TareaBase)`.
  - `prueba_plan_sincronizacion.py` — adaptación con allowlist exacta para `TareaSincronizacionCatalogo`.
- **Pruebas:** 27/27 OK. Regresiones 310/310 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Secuencia `detectar_diferencias` → `preparar_plan_sincronizacion` → `aplicar_incorporaciones` → `eliminar_candidatos` ejecutada en QThread. Sin integración con la interfaz en esta etapa.
- **Decisiones importantes:** Incorporación y eliminación como transacciones independientes. Tarea sin SQL propio: delega en funciones de `escanear_videos`.

## 23. Eliminación controlada de candidatos ausentes del catálogo

- **Fecha:** 2026-08-01
- **Objetivo:** Eliminar de forma controlada los registros ausentes del disco según el plan de sincronización.
- **Archivos creados:**
  - `prueba_eliminar_candidatos.py` — 16 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `eliminar_candidatos(plan, ruta_db=None)`, helper `_validar_plan_sincronizacion` (compartido con `aplicar_incorporaciones`).
- **Pruebas:** 16/16 OK. Regresiones 294/294 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Eliminación atómica (`DELETE` por nombre con `rowcount`, un solo `commit`, rollback total). Sin eliminación de archivos físicos ni miniaturas.
- **Decisiones importantes:** `_coleccion_nombres` devuelve orden determinista. Validación compartida con `aplicar_incorporaciones`.

## 22. Aplicación de incorporaciones del plan de sincronización

- **Fecha:** 2026-08-01
- **Objetivo:** Aplicar de forma no destructiva las incorporaciones del plan de sincronización.
- **Archivos creados:**
  - `prueba_aplicar_incorporaciones.py` — 15 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `aplicar_incorporaciones(plan, ruta_db=None)`.
- **Pruebas:** 15/15 OK. Regresiones 279/279 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Persiste únicamente `a_incorporar` delegando en `guardar_videos`. No elimina candidatos ni modifica `ya_sincronizados`.
- **Decisiones importantes:** Validación completa previa antes de abrir SQLite.

## 21. Preparación del plan de sincronización

- **Fecha:** 2026-08-01
- **Objetivo:** Preparar un plan puro de sincronización a partir del resultado de `detectar_diferencias`.
- **Archivos creados:**
  - `prueba_plan_sincronizacion.py` — 12 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `preparar_plan_sincronizacion(diferencias)`, helper `_coleccion_nombres`.
- **Pruebas:** 12/12 OK. Regresiones 267/267 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Plan `{"carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"}` con registros básicos y candidatos informativos. Operación pura: sin SQLite, sin FFprobe/FFmpeg.
- **Decisiones importantes:** `fecha_importacion` generada en la preparación, no en la detección. Deduplicación de nombres repetidos queda pendiente.

## 20. Detección no destructiva de diferencias disco ↔ BD

- **Fecha:** 2026-08-01
- **Objetivo:** Detectar diferencias entre la carpeta de videos y el catálogo SQLite sin modificar datos.
- **Archivos creados:**
  - `prueba_detectar.py` — 15 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `detectar_diferencias(carpeta, ruta_db=None)`.
- **Pruebas:** 15/15 OK. Regresiones 252/252 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Comparación por nombre, solo lectura. Sin integración al pipeline ni a la interfaz.
- **Decisiones importantes:** No detecta movimientos ni renombrados. No recorre subcarpetas.

## 19. Generación asíncrona de miniaturas en el pipeline

- **Fecha:** 2026-07-31
- **Objetivo:** Integrar la generación de miniaturas en el pipeline escaneo → FFprobe → miniaturas → guardado.
- **Archivos modificados:**
  - `escanear_videos.py` — `asegurar_miniaturas(videos, carpeta)`, `combinar_registros_con_miniaturas(registros, resultado_miniaturas)`.
  - `tareas_videos.py` — `TareaMiniaturas(TareaBase)`, re-exporta `asegurar_miniaturas` y `combinar_registros_con_miniaturas`.
  - `visor_videos.py` — pipeline a 4 tareas con paso de miniaturas, estados `_miniaturas_pendiente`/`tarea_miniaturas`/`resultado_miniaturas`.
  - `prueba_escaneo_guardado.py` — ampliada a 24 pruebas.
  - `prueba_escaneo_interfaz.py` — actualizada a secuencia de 4 tareas (36 pruebas).
- **Pruebas:** 24/24 OK. Regresiones 252/252 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Una miniatura básica por video integrada en el pipeline. FFmpeg ejecutado solo en segundo plano. Sin selección inteligente ni limpieza de miniaturas antiguas.
- **Decisiones importantes:** Reutilización por `mtime`. Escritura en siguiente ranura libre. Nunca sobrescribe ni elimina.

## 18. Integración de FFprobe en el pipeline

- **Fecha:** 2026-07-31
- **Objetivo:** Extender el pipeline para que los registros se guarden con metadatos FFprobe.
- **Archivos modificados:**
  - `escanear_videos.py` — `CLAVES_METADATOS_FFPROBE`, `_normalizar_ruta(ruta)`, `combinar_registros_con_ffprobe(videos, carpeta, resultado_ffprobe)`.
  - `tareas_videos.py` — re-exporta `combinar_registros_con_ffprobe`.
  - `visor_videos.py` — pipeline a 3 tareas (escaneo → FFprobe → guardado), estados `_ffprobe_pendiente`/`tarea_ffprobe`/`resultado_ffprobe`.
  - `prueba_escaneo_guardado.py` — ampliada a 19 pruebas.
- **Pruebas:** 19/19 OK. Regresiones 247/247 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Registros guardados con duración, resolución y codec. NULL ante fallos individuales.
- **Decisiones importantes:** Combinación pura de registros por ruta normalizada. Sin FFmpeg/miniaturas en esta etapa.

## 17. Integración del pipeline limitado (escaneo → registros básicos → guardado)

- **Fecha:** 2026-07-31
- **Objetivo:** Implementar el encadenamiento escaneo → preparación → guardado y corregir la desviación arquitectónica (preparación de registros debe estar en la capa de catálogo).
- **Archivos modificados:**
  - `escanear_videos.py` — `preparar_registros_basicos(videos, carpeta)`.
  - `tareas_videos.py` — eliminada definición local, re-exporta desde `escanear_videos`.
  - `visor_videos.py` — encadenamiento escaneo → guardado con mismo `GestorTareas`, estados `_guardado_pendiente`/`tarea_guardado`/`registros_guardados`.
- **Archivos creados:**
  - `prueba_escaneo_guardado.py` — 16 pruebas.
- **Pruebas:** 16/16 OK. Regresiones 244/244 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Pipeline funcional con escritura real en SQLite. Sin FFprobe/FFmpeg/miniaturas. Sin eliminación de registros ni recarga.
- **Decisiones importantes:** La preparación de registros es lógica de catálogo, no de tareas. Corrección de arquitectura.

## 16. Escaneo manual y asíncrono de la carpeta seleccionada desde la interfaz

- **Fecha:** 2026-07-30
- **Objetivo:** Permitir al usuario escanear la carpeta elegida desde la interfaz.
- **Archivos creados:**
  - `prueba_escaneo_interfaz.py` — 36 pruebas.
- **Archivos modificados:**
  - `visor_videos.py` — botón "Escanear carpeta", `iniciar_escaneo()`, `videos_detectados`, enrutado por `_escaneo_pendiente`, constantes `MENSAJE_ESCANEANDO`/`MENSAJE_ERROR_ESCANEO`/`MENSAJE_SIN_ESCANEO`.
- **Pruebas:** 36/36 OK. Regresiones 192/192 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Escaneo asíncrono de la carpeta seleccionada. Conteo de videos detectados visible. Sin escritura en SQLite ni FFprobe/FFmpeg.
- **Decisiones importantes:** Mismo `GestorTareas` reutilizado. Enrutado por flag `_escaneo_pendiente`.

## 15. Selección de carpeta en la interfaz

- **Fecha:** 2026-07-30
- **Objetivo:** Permitir al usuario seleccionar la carpeta de videos desde la interfaz.
- **Archivos creados:**
  - `prueba_seleccion_carpeta.py` — 26 pruebas.
- **Archivos modificados:**
  - `visor_videos.py` — botón "Seleccionar carpeta", `carpeta_seleccionada`, `seleccionar_carpeta()`, constantes `MENSAJE_SIN_CARPETA`/`MENSAJE_RUTA_INVALIDA`.
- **Pruebas:** 26/26 OK. Regresiones 192/192 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Selección de carpeta con normalización y validación. Sin escaneo automático.
- **Decisiones importantes:** Seleccionar carpeta no escanea su contenido. La persistencia queda para etapa futura.

## 14. Integración de la lectura paginada con la interfaz (carga inicial asíncrona)

- **Fecha:** 2026-07-30
- **Objetivo:** Cargar la primera página del catálogo en segundo plano sin bloquear la interfaz.
- **Archivos creados:**
  - `prueba_interfaz_asincrona.py` — 29 pruebas.
- **Archivos modificados:**
  - `visor_videos.py` — eliminado `import sqlite3` y `listar_videos`. `GestorTareas` + `TareaLecturaCatalogoPaginada` para carga inicial. Constantes `TAMANIO_PAGINA_INICIAL = 100`, `MENSAJE_CARGANDO`, `MENSAJE_ERROR`.
- **Pruebas:** 29/29 OK. Regresiones 192/192 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Interfaz sin SQLite. Carga inicial asíncrona con estado de carga y manejo de errores.
- **Decisiones importantes:** Sin `check_same_thread=False`. Apagado ordenado con `gestor.cerrar()`.

## 13. Lectura paginada del catálogo

- **Fecha:** 2026-07-29
- **Objetivo:** Implementar lectura paginada con LIMIT/OFFSET/COUNT en SQL para catálogos grandes.
- **Archivos creados:**
  - `prueba_lectura_paginada.py` — 32 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `listar_videos_paginado(limite, desplazamiento=0, texto=None, ruta_db=None)`.
  - `tareas_videos.py` — `TareaLecturaCatalogoPaginada(TareaBase)`.
- **Pruebas:** 32/32 OK. Regresiones 192/192 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Consulta paginada con búsqueda parcial por LIKE parametrizada. Sin integración con la interfaz en esta etapa.
- **Decisiones importantes:** `%` y `_` actúan como comodines LIKE (documentado como limitación conocida).

## 12. Contrato definitivo de TareaGuardarVideos ante entradas inválidas (observación)

- **Fecha:** 2026-07-29
- **Objetivo:** Garantizar que el constructor de `TareaGuardarVideos` nunca lance ante entradas inválidas.
- **Archivos modificados:**
  - `tareas_videos.py` — ampliada la captura de `(TypeError, ValueError)` a `Exception` al materializar la colección.
  - `prueba_guardar_videos.py` — ampliada de 31 a 34 pruebas (generador fallido, entradas inválidas, error diferido).
- **Pruebas:** 34/34 OK. Regresiones OK.
- **Commit:** Sin commit independiente (corrección incluida en el commit de la etapa de colección).
- **Resultado:** Constructor nunca lanza. Todos los errores por señal `error`.
- **Decisiones importantes:** Contrato definitivo documentado y cubierto por pruebas.

## 11. Escritura de colección transaccional asíncrona

- **Fecha:** 2026-07-29
- **Objetivo:** Implementar escritura de múltiples registros en una única transacción atómica.
- **Archivos creados:**
  - `prueba_guardar_videos.py` — 31 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — internos compartidos `_validar_registro_video(datos)` y `_upsert_video(conn, datos)`. `guardar_videos(datos_videos, ruta_db=None)`.
  - `tareas_videos.py` — `TareaGuardarVideos(TareaBase)`.
- **Pruebas:** 31/31 OK. Regresiones OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Escritura de colección con un solo commit y rollback total. Sin eliminación de registros.
- **Decisiones importantes:** `guardar_video` y `guardar_videos` comparten validación y upsert sin duplicar código.

## 10. Aislamiento del registro y validación previa a SQL (observación de la etapa 9)

- **Fecha:** 2026-07-28
- **Objetivo:** Resolver observación: aislar el diccionario de entrada en `TareaGuardarVideo` y validar contrato antes de abrir SQLite.
- **Archivos modificados:**
  - `tareas_videos.py` — `TareaGuardarVideo` toma instantánea `self._datos = dict(datos)`.
  - `prueba_guardar.py` — ampliada a 19 pruebas.
- **Pruebas:** 19/19 OK. Regresiones OK.
- **Commit:** Sin commit independiente (resuelto antes del commit de la etapa 9).
- **Resultado:** Constructor inmune a mutaciones posteriores del llamador. Validación previa a SQL sin abrir conexión.

## 9. Escritura individual asíncrona de video

- **Fecha:** 2026-07-28
- **Objetivo:** Implementar escritura individual asíncrona de registros de video en SQLite.
- **Archivos creados:**
  - `prueba_guardar.py` — 19 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `guardar_video(datos, ruta_db=None)`.
  - `tareas_videos.py` — `TareaGuardarVideo(TareaBase)`.
- **Pruebas:** 19/19 OK. Regresiones OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Upsert transaccional de un único registro. `commit`/`rollback`/`close` propios.
- **Decisiones importantes:** Conexión abierta y cerrada dentro del hilo de trabajo.

## 8. Lectura asíncrona del catálogo

- **Fecha:** 2026-07-28
- **Objetivo:** Leer el catálogo SQLite en segundo plano.
- **Archivos creados:**
  - `prueba_lectura.py` — 15 pruebas.
- **Archivos modificados:**
  - `escanear_videos.py` — `listar_videos(ruta_db=None)` con validación `os.path.isfile` antes de conectar.
  - `tareas_videos.py` — `TareaLecturaCatalogo(TareaBase)`.
- **Pruebas:** 15/15 OK. Regresiones 37/37 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Lectura asíncrona con conexión por hilo. Base inexistente → `FileNotFoundError` sin crear archivos.
- **Decisiones importantes:** La lectura nunca crea la base.

## 7. Escaneo asíncrono

- **Fecha:** 2026-07-27
- **Objetivo:** Ejecutar el escaneo de archivos de video en segundo plano.
- **Archivos creados:**
  - `prueba_escaneo.py` — 12 pruebas.
- **Archivos modificados:**
  - `tareas_videos.py` — `TareaEscaneo(TareaBase)`.
- **Pruebas:** 12/12 OK. Regresiones OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Escaneo asíncrono con errores propagados por señal `error`.
- **Decisiones importantes:** Reutiliza `escanear_videos(carpeta)` sin cambios.

## 6. Procesamiento asíncrono de metadatos FFprobe

- **Fecha:** 2026-07-27
- **Objetivo:** Ejecutar FFprobe en segundo plano para no bloquear la interfaz.
- **Archivos creados:**
  - `tareas_videos.py` — `rutas_videos()` y `TareaFFprobe(TareaBase)`.
  - `prueba_ffprobe.py` — 12 pruebas.
- **Pruebas:** 12/12 OK. Regresiones OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Metadatos FFprobe en segundo plano con resultado y error por ruta. Timeout 30 s.
- **Decisiones importantes:** FFprobe en hilo de trabajo. `creationflags=subprocess.CREATE_NO_WINDOW` en Windows.

## 5. Infraestructura reutilizable de trabajos en segundo plano

- **Fecha:** 2026-07-27
- **Objetivo:** Crear infraestructura genérica para ejecutar tareas asíncronas con QThread.
- **Archivos creados:**
  - `tareas.py` — `Estado`, `TareaBase(QObject)`, `GestorTareas(QObject)`.
  - `prueba_tareas.py` — 13 pruebas.
- **Pruebas:** 13/13 OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Infraestructura con señales `tarea_iniciada`, `tarea_resultado`, `tarea_error`, `tarea_finalizada`. Un QThread por ejecución. Apagado ordenado con `cerrar(timeout_ms)`.
- **Decisiones importantes:** Ciclo de vida `inactivo` → `ocupado` → `inactivo`.

## 4. Rutas independientes del directorio de trabajo

- **Fecha:** 2026-07-26
- **Objetivo:** Resolver rutas del proyecto sin depender del CWD.
- **Archivos creados:**
  - `rutas.py` — `ruta_raiz()`, `ruta_biblioteca()`, `ruta_carpeta_miniaturas()`, `ruta_carpeta_videos()`.
- **Archivos modificados:**
  - `escanear_videos.py` — eliminadas constantes relativas, usa `rutas.py`.
  - `visor_videos.py` — `miniatura_principal()` resuelve a través de `rutas.py`.
- **Pruebas:** Regresiones completas OK. Smoke test desde CWD ajeno al proyecto OK.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Proyecto funciona desde cualquier ubicación.
- **Decisiones importantes:** Resolución anclada en `os.path.dirname(os.path.abspath(__file__))`.

## 3. Primera generación de miniaturas con preservación de archivos

- **Fecha:** 2026-07-26
- **Objetivo:** Implementar generación automática de miniaturas con reutilización y preservación.
- **Archivos modificados:**
  - `escanear_videos.py` — constantes `CARPETA_MINIATURAS`/`EXTENSION_MINIATURA`, funciones `ffmpeg_disponible`, `ruta_miniatura`, `calcular_tiempo_miniatura`, `miniatura_vigente`, `generar_miniatura`, `siguiente_indice_libre`, `miniatura_reutilizable`, `asegurar_miniatura`. `sincronizar_bd()` invoca `asegurar_miniatura`.
- **Pruebas:** Smoke test OK. Miniatura generada sin sobrescribir existentes.
- **Commit:** Aprobado y commiteado.
- **Resultado:** Como máximo una miniatura nueva por video por escaneo. Reutilización por `mtime`. Escritura en siguiente ranura libre.
- **Decisiones importantes:** Nunca sobrescribir ni eliminar archivos. Videos vacíos (0 bytes) no generan miniatura.

## 2. Incorporación de Git

- **Fecha:** 2026-07-26
- **Objetivo:** Añadir control de versiones al proyecto.
- **Archivos creados:** `.gitignore` con `biblioteca.db`, `datos.txt`, `miniaturas/`, `__pycache__/`, `*.pyc`.
- **Pruebas:** N/A.
- **Commit:** Inicial.
- **Resultado:** Proyecto bajo control de versiones Git.

## 1. Arquitectura congelada — línea base

- **Fecha:** 2026-08-02 (fecha de congelamiento documental)
- **Objetivo:** Establecer la arquitectura base del proyecto y documentarla como referencia.
- **Archivos existentes en la línea base:**
  - `escanear_videos.py` — backend: escaneo, SQLite, FFprobe, FFmpeg, miniaturas, sincronización.
  - `visor_videos.py` — interfaz gráfica PySide6.
  - `biblioteca.db` — base de datos SQLite del catálogo.
  - `miniaturas/` — caché de miniaturas generadas.
  - `videos_prueba/` — dataset de prueba.
  - `main.py`, `operaciones.py`, `prueba_agente.py`, `datos.txt` — artefactos ajenos al visor (preservados).
- **Pruebas:** Verificación de compilación, sincronización de catálogo, metadatos FFprobe, smoke test GUI (4 videos, filtro "real" → 1 video).
- **Commit:** Arquitectura base documentada.
- **Resultado:** Arquitectura congelada como referencia para desarrollo posterior.
- **Decisiones importantes:** Separación interfaz/lógica/catálogo. Interfaz nunca accede directamente a SQLite, FFprobe, FFmpeg ni archivos. Documentación en 4 documentos (REGLAS, DOCUMENTO_TECNICO, ESTADO, ROADMAP).
