# STATUS — Visor de Videos

## Fase actual

**Beta 3 terminada, validada y publicada.**

El estado tecnico verificado prevalece sobre cualquier texto historico que lo presente como pendiente. La Beta 3 esta cerrada sobre el codigo definitivo, validada manualmente y publicada; el instalador oficial `VisorVideos_Beta3_Setup.exe` existe en `Distribucion\Beta3\`.

## Ultimo baseline aprobado

- Tag `v3.0-beta` sobre HEAD `4408d5426f65db1e41aad8b1d58a97695d438bf8` (commit "Cerrar la Beta 3: alinear la documentación oficial con el estado final del proyecto").
- Rama `main` con tracking `origin/main`; worktree limpio; 107 archivos tracked.
- Proteccion del baseline de adopcion: `C:\ProjectStorage\VisorVideo\backups\adoption-baseline` (documentacion, methodology, agent_exchange, manifiesto SHA-256).
- Bootstrap B-A en curso: `PROJECT_STRUCTURED` (transformacion documental aprobada).

## Estado funcional

- La aplicacion abre sin crash (verificado: titulo "Biblioteca de videos", 23 tarjetas cargadas, contador "23 videos").
- FFmpeg funcional; FFprobe funcional; SQLite funcional (catalogo con 23 filas restauradas).
- Datos restaurados identicos al backup persistente (`source-protect`).
- Git limpio en HEAD.

## Elementos implementados relevantes

- Centro de Navegacion (Bloque 2): arbol "Este equipo", expansion diferida, seleccion, persistencia, escaneo automatico, indicadores de carpetas escaneadas.
- Beta 3 (Bloques A-E): experiencia visual (tiempos, duracion simplificada, tamanos, vista ampliada configurable/desactivable, previews progresivas), seleccion y operaciones (modo checks, copiar, pegar, eliminar a Papelera, atajos), progreso real, integracion con reproductor (apertura por doble clic).
- Bloque 4: catalogo por seleccion de carpetas (escaneo multicarpeta, sincronizacion multicarpeta segura, selector de alcance unificado, auditoria integral).
- Correccion de la regresion de previews: cada video usa su propia carpeta real del catalogo.
- Empaquetado oficial: `instalador.iss` + `EMPACADO.md`; instalador Beta 3 generado (por usuario, sin FFmpeg empaquetado).
- 77 suites de pruebas presentes; resultados heredados: 74/77 OK (ver Problemas conocidos).

## Trabajo pendiente real

- Definir el alcance de la **Beta 4** mediante planificacion exclusivamente documental (proximo ciclo de desarrollo).
- Paginacion completa automatica del catalogo (scroll infinito, busqueda en SQL desde la interfaz, ordenamiento configurable).
- Deduplicacion de nombres repetidos en el plan de sincronizacion.
- Cancelacion del escaneo.
- Filtrado del catalogo desde el arbol (Etapa 2.10 diferida).
- Evaluar y optimizar el rendimiento con colecciones grandes.
- Decisiones abiertas heredadas: identidad estable de videos, orden natural en selecciones de carpetas, alcance de Beta 4.

## Deuda tecnica conocida

- Crecimiento y duplicacion de infraestructura entre las suites de prueba (helpers y conectores repetidos).
- Detalle excesivo en el documento tecnico historico (ya resuelto en la estructura nueva: `ARCHITECTURE.md` condensada).
- Restauracion de rutas Windows 8.3 (nombres cortos) en el arbol: cae en comportamiento tolerante; no afecta el uso normal.
- Estado de "escaneada" por sesion: vive en memoria y se pierde al reiniciar.
- Crecimiento acumulativo de miniaturas (nuevas ranuras sin limpieza; requiere autorizacion para limpiar).
- Criterio de reutilizacion por `mtime` sin hash de integridad; riesgo de miniaturas parciales/corruptas si FFmpeg falla a mitad de escritura.
- Coincidencia de miniaturas por prefijo (`startswith`).

## Problemas conocidos

- **Tests capaces de tocar estado real:** algunos tests operan sobre la base real o asumen preferencias; los nuevos desarrollos deben aislar los tests del estado real (`RULES.md` 7).
- **Fallos historicos de tests (2):** `prueba_persistencia_carpeta.py` 18/20 (T11/T16: asume que el arranque no crea `configuracion.json`; la restauracion de `escaneo_automatico` lo escribe) y `prueba_aplicar_incorporaciones.py` 14/15 (T15: asume filas con `tamano_bytes = NULL`; la base real lo tiene poblado). Preexistentes, no atribuibles a etapas recientes; corregir en etapas especificas.
- **Fallo transitorio no reproducido:** `prueba_copiar_rutas_seleccionados.py` fallo una vez en suite completa y luego paso 8/8 aislado; sin evidencia de bug reproducible del producto.
- **Coexistencia FFmpeg 8.1.1 / 9.0:** la 8.1.1 es la efectiva por PATH; la 9.0 vive en ProjectStorage. Ambas funcionan; no se corrige sin autorizacion (ver `ENVIRONMENT.md`).
- **PyInstaller ausente:** necesario solo para generar el ejecutable portable; el procedimiento documentado en `EMPACADO.md` no se puede ejecutar hasta instalarlo en una etapa autorizada.

## Entorno pendiente relacionado

- PyInstaller ausente (ver arriba).
- Coexistencia FFmpeg a resolver o documentar como aceptada.
- No existen manifests de dependencias (solo `EMPACADO.md` y `ENVIRONMENT.md`).

## Proximos focos

1. Cerrar la adopcion metodologica B-A (auditorias del Director hasta `BOOTSTRAP_HANDOFF_COMPLETED`).
2. Planificacion documental de la Beta 4.
3. Abordar los pendientes reales priorizados en `ROADMAP.md`.
