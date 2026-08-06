# VISOR DE VIDEOS

## Estado general

Proyecto de escritorio profesional para Windows orientado a explorar
grandes colecciones de videos mediante miniaturas representativas.

**Fase actual:** Beta 1.0 estabilizada. Ejecutable portable e instalador
de Windows funcionales. Arquitectura base consolidada con pipeline
asíncrono completo (escaneo, tamaños, FFprobe, miniaturas, guardado,
sincronización, recarga), previews progresivos, apertura por doble clic
y persistencia de la última carpeta seleccionada.

## Último commit aprobado

**Mensaje:** Persistir preferencia "Incluir subcarpetas" entre ejecuciones

**Etapa:** Persistencia de la preferencia de subcarpetas — el estado de la
casilla "Incluir subcarpetas" se guarda y restaura automáticamente:
- Al modificar la casilla, se persiste inmediatamente en `configuracion.json`
  mediante `guardar_preferencia_subcarpetas` (escritura atómica `.tmp` + `os.replace`).
- Al iniciar la aplicación, se restaura el último valor con
  `obtener_preferencia_subcarpetas` (devuelve `False` por defecto).
- Mismo patrón que `ultima_carpeta`: clave `incluir_subcarpetas` como booleano
  en el JSON compartido.

**Pruebas superadas:** `prueba_persistencia_subcarpetas.py` 10/10, `prueba_escaneo_subcarpetas.py` 12/12, `prueba_escaneo_interfaz.py` 36/36, `prueba_persistencia_carpeta.py` 20/20, `prueba_smoke.py` OK.

**SHA:** consultar con `git log -1`.

## Hitos completados

- Arquitectura general y separación de capas.
- Control de versiones con Git.
- Resolución centralizada de rutas (independiente del CWD).
- Generación de miniaturas con preservación de archivos.
- Infraestructura de trabajos en segundo plano (QThread).
- Escaneo asíncrono de videos.
- Lectura asíncrona del catálogo SQLite.
- Lectura paginada del catálogo (`LIMIT`/`OFFSET`/`COUNT` en SQL).
- Escritura individual y de colección asíncronas.
- Integración asíncrona de la interfaz (carga inicial sin bloquear).
- Selección de carpeta desde la interfaz.
- Escaneo manual y asíncrono de la carpeta elegida.
- Pipeline completo: escaneo → tamaños → FFprobe → miniaturas → guardado → sincronización → recarga.
- Detección de diferencias disco ↔ BD (no destructiva).
- Plan de sincronización y aplicación de incorporaciones.
- Eliminación controlada de registros ausentes.
- Sincronización asíncrona del catálogo e integración en la interfaz.
- Recarga asíncrona del catálogo tras sincronización.
- Carga manual de páginas adicionales (botón "Cargar más").
- Presentación del catálogo en filas horizontales (una tarjeta por video).
- Visualización del tamaño de archivos (B/KB/MB/GB).
- Previews progresivos por video (3 fotogramas al 25/50/75 %).
- Apertura del video por doble clic (módulo de servicio `apertura_videos.py`).
- Persistencia de la última carpeta seleccionada (`configuracion.json`).
- Separación del punto de entrada de producción y del arnés de smoke tests.
- Ejecutable portable (PyInstaller `--onedir --windowed`).
- Instalador Beta funcional (Inno Setup, sin permisos de administrador).
- Feedback visual del procesamiento (barra de progreso indeterminada con texto de etapa).
- Selección visual de filas (simple y múltiple con Ctrl+clic). Base preparada para futuras acciones sobre elementos seleccionados sin agregar menús ni botones todavía.
- Menú contextual con clic derecho sobre filas de videos (abrir, abrir carpeta, copiar ruta).
- Restauración automática de la selección tras reconstruir la lista de tarjetas.
- Selección por rango con Shift+clic basada en un ancla de selección y el orden visible.
- Copia de rutas de los seleccionados mediante menú contextual (primera operación sobre selección múltiple).
- Apertura de carpetas de los seleccionados mediante menú contextual (deduplicación de carpetas).
- Escaneo opcional de subcarpetas con persistencia de la preferencia "Incluir subcarpetas".
- Validación manual con videos reales: escaneo con y sin subcarpetas, diferencia en cantidad de videos detectados, sin regresiones.
## Pendientes prioritarios

1. ~~Mejorar el feedback visual del procesamiento (barra de progreso,~~
   ~~estado visible de tareas en curso).~~ **Implementado.**
2. ~~Incorporar selección visual de filas (selección simple y múltiple,~~
   ~~acciones sobre videos seleccionados).~~ **Implementado.**
3. Evaluar y optimizar el rendimiento con colecciones grandes de videos.
4. Paginación completa automática del catálogo (scroll infinito,
   búsqueda en SQL desde la interfaz, ordenamiento configurable).
5. Deduplicación de nombres repetidos en el plan de sincronización.

Las funcionalidades futuras pendientes se detallan en `ROADMAP.md`.
Los problemas técnicos vigentes se detallan en `DOCUMENTO_TECNICO.md` §8.

## Deuda técnica

- Crecimiento y duplicación de infraestructura entre las suites de
  prueba (helpers, conectores y patrones repetidos).
- Pendiente documental: reducir progresivamente el nivel de detalle de
  implementación en `DOCUMENTO_TECNICO.md`, conservando la información
  arquitectónica pero eliminando detalles que ya refleja el código fuente.
- La selección se restaura automáticamente después de reconstruir
  completamente las tarjetas (`_reemplazar_tarjetas`), pero solo para
  los nombres que siguen existiendo en el nuevo conjunto.

## Próxima etapa

**Mejora continua de la Beta.** La Beta 1.0 fue validada en equipos
externos, lo que dio origen a las correcciones de estabilización ya
implementadas. La fase actual se centra en mejorar la experiencia de
uso basada en pruebas reales, continuando con la optimización de
rendimiento con colecciones grandes. El sistema completo de selección
ya está funcional: simple, Ctrl+clic, Shift+clic, restauración tras
reescaneo y menú contextual con acciones básicas (abrir, abrir carpeta,
copiar ruta).

## Documentos del proyecto

- `REGLAS_PROYECTO.md` — reglas permanentes de desarrollo.
- `DOCUMENTO_TECNICO.md` — arquitectura y referencia técnica.
- `ROADMAP.md` — funcionalidades previstas.
- `VISION_PRODUCTO.md` — decisiones estratégicas y filosofía.
- `HISTORIAL_PROYECTO.md` — registro cronológico de etapas.
- `ESTADO_PROYECTO.md` — este documento.
