# ROADMAP — Visor de Videos

Trabajo futuro **decidido** y priorizado. Separacion obligatoria: `ROADMAP = decidido`, `BACKLOG = quiza`. Las ideas tentativas viven en `BACKLOG.md`; lo ya implementado queda registrado en `HISTORIAL_PROYECTO.md` y en `STATUS.md`.

## Prioridad inmediata

1. **Cerrar la adopcion metodologica B-A** del bootstrap (`PROJECT_STRUCTURED` en curso; fases posteriores hasta `BOOTSTRAP_HANDOFF_COMPLETED`).
2. **Planificacion documental de la Beta 4** (definir alcance, bloques y plan mediante una etapa exclusivamente documental, equivalente a la Etapa B3.0).

## Proximo ciclo: Beta 4

La Beta 3 quedo finalizada, validada y publicada. El proximo ciclo de desarrollo (Beta 4) recogera mejoras y correcciones detectadas durante la validacion y el uso real, con su alcance definido por planificacion previa.

## Pendientes tecnicos comprometidos

- Paginacion completa automatica del catalogo: scroll infinito, busqueda en SQL desde la interfaz y ordenamiento configurable (la carga manual "Cargar mas" ya existe).
- Deduplicacion de nombres repetidos en el plan de sincronizacion.
- Cancelacion del escaneo.
- Filtrado del catalogo desde el arbol (Etapa 2.10, diferida de la Beta 3).
- Evaluar y optimizar el rendimiento con colecciones grandes.
- Identidad estable de videos (decision abierta heredada).
- Orden natural en selecciones de carpetas (decision abierta heredada).

## Criterio

Las funcionalidades pasan de este documento o de `BACKLOG.md` al desarrollo solo cuando existe una etapa aprobada para implementarlas.
