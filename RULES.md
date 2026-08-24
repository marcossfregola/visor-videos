# RULES — Visor de Videos

Reglas permanentes del proyecto. Consolidan las reglas heredadas, adaptadas a una version agnostica del mecanismo de trabajo con agentes, y remiten al protocolo multiagente V1.3 para la operacion.

## 1. Metodologia

- El proyecto avanza mediante etapas pequenas, verificables y acumulativas.
- Cada etapa tiene un unico objetivo claramente definido.
- No mezclar funcionalidades grandes en una misma implementacion.
- No avanzar a una nueva etapa antes de aprobar la anterior.

## 2. Inspeccion previa

Antes de modificar cualquier archivo se debe:

- inspeccionar el estado actual del proyecto;
- identificar los archivos a modificar;
- justificar por que son necesarios;
- indicar que archivos no seran modificados.

## 3. Cambios

- Modificar unicamente los archivos estrictamente necesarios.
- No realizar refactorizaciones innecesarias.
- No introducir cambios ajenos al alcance de la etapa.

## 4. Auditoria y evidencia

- Al finalizar cada etapa se entregan: archivos creados, modificados y eliminados; explicacion tecnica; pruebas realmente ejecutadas; limitaciones restantes; salida de `git status`.
- Nunca afirmar pruebas no ejecutadas ni verificaciones visuales no realizadas.
- La evidencia debe distinguir: codigo modificado, archivos generados durante pruebas, cambios reales en SQLite, cambios reales en miniaturas y archivos ignorados por Git.

## 5. Git y commits

- Flujo obligatorio: implementacion -> pruebas -> auditoria -> aprobacion -> commit.
- Nunca crear commits por iniciativa propia.
- Un commit por etapa aprobada; no mezclar cambios.
- Arbol limpio tras cada commit.
- No hacer push sin autorizacion expresa.

## 6. Proteccion de datos y preservacion

- Nunca eliminar, sobrescribir, reemplazar, mover ni renombrar archivos existentes sin autorizacion expresa.
- Incluye bases de datos, miniaturas, caches, archivos temporales, archivos ignorados por Git y datos de prueba.
- Ante la duda: preservar.
- No se realiza borrado permanente desde funciones del producto; la eliminacion usa la Papelera nativa de Windows.
- No borrar backups (`source-protect`, `adoption-baseline`) ni historicos sin autorizacion.

## 7. Pruebas

- Ejecutar las pruebas correspondientes a cada etapa y reportar solo las realmente ejecutadas.
- Los tests no deben modificar el estado real del usuario: aislar del `biblioteca.db`, `configuracion.json`, `miniaturas/` y datos reales siempre que sea posible.
- No corregir fallos historicos de tests fuera de una etapa que los incluya explícitamente.

## 8. Arquitectura

- Mantener separadas: interfaz, catalogo/logica de dominio, SQLite, escaneo, FFprobe, FFmpeg, cache, trabajos en segundo plano y configuracion.
- La interfaz nunca debe acceder directamente a SQLite, FFprobe, FFmpeg, archivos ni logica pesada.
- El trabajo pesado debe ejecutarse fuera del hilo principal (infraestructura `QThread`/`GestorTareas`).
- Cada video transporta y utiliza su propia ruta real; la carpeta activa de navegacion es un concepto distinto del alcance del catalogo.

## 9. Documentacion

- Una categoria de informacion tiene una unica fuente oficial (matriz definida en la adopcion; nucleo: `README.md`, `PROJECT.md`, `STATUS.md`, `ARCHITECTURE.md`, `ENVIRONMENT.md`, `RULES.md`; condicionales: `ROADMAP.md`, `BACKLOG.md`, `HISTORIAL_PROYECTO.md`, `EMPACADO.md`).
- Cuando cambie la arquitectura o el comportamiento tecnico, verificar si `ARCHITECTURE.md` requiere actualizacion.
- La arquitectura documental se audita periodicamente o cuando se detecte mezcla de responsabilidades o duplicacion entre documentos.
- No duplicar contenido profundo entre documentos; los demas documentos solo referencian.

## 10. Calidad

Prioridades: 1. Seguridad de los datos. 2. Arquitectura. 3. Mantenibilidad. 4. Estabilidad. 5. Rendimiento. 6. Nuevas funcionalidades.

## 11. Evaluacion de etapas

- Cada etapa se evalua exclusivamente contra el objetivo definido en su momento de aprobacion.
- Las funcionalidades previstas para etapas futuras no constituyen evidencia de incompletitud de la etapa evaluada.

## 12. Gestion de hilos y agentes

- El trabajo operativo con agentes (orquestador, auditor, implementador; hilos tematicos; stages y runs; intent store; commit policy) se rige por el `PROTOCOLO_MULTIAGENTE_V1.3_FINAL.md`.
- Los hilos nuevos parten de los documentos oficiales actualizados del nucleo documental.
- `HISTORIAL_PROYECTO.md` se consulta solo para antecedentes; no forma parte del contexto operativo de desarrollo.
- Las reglas transitorias de un bootstrap (sandbox, rotacion de instancias, entorno particular de una PC) no se convierten en reglas permanentes del producto.

## 13. Cierre y continuidad

Al finalizar cada hilo de trabajo se realizan dos cierres independientes:

- **Cierre tecnico:** documentacion tecnica, pruebas correspondientes y commit de la etapa implementada.
- **Cierre estrategico:** solo cuando hayan surgido ideas de producto, cambios de prioridad, decisiones de arquitectura de alto nivel o criterios de diseno que deban conservarse; se materializan en `PROJECT.md`, `BACKLOG.md`, `ARCHITECTURE.md` y/o `ROADMAP.md` con un commit documental independiente.

## 14. Prohibiciones operativas

- No limpiar ni corregir la coexistencia FFmpeg 8.1.1 / 9.0 sin autorizacion.
- No ejecutar tests ni la aplicacion en fases exclusivamente documentales.
- No eliminar documentacion heredada ni historicos durante una adopcion, salvo decision expresa posterior.
- No instalar, desinstalar ni actualizar dependencias fuera de una etapa autorizada.
