"""Orquestador puro B7.6 — operaciones masivas seguras sobre videos catalogados.

Contrato:
- Sin Qt, sin procesamiento multimedia externo, sin acceso directo a FS más allá de delegar a servicios individuales.
- Recibe operación (mover|copiar|eliminar), lista ordenada de video_id, destino cuando aplique, ruta_db, cancel_check y callback progreso.
- Llama secuencialmente al servicio individual correspondiente: mover_video.mover_video, copiar_video.copiar_video, eliminar_video.eliminar_video.
- No hace pre-vuelo global que replique reglas; cada servicio resuelve/rechaza según su contrato.
- Un fallo individual no cancela automáticamente todo el lote; continúa salvo cancelación o error que haga inseguro continuar (no hay tal, solo cancel).
- Cancelación cooperativa antes de cada ítem; no revierte completados. Para eliminar respeta punto de no retorno del servicio.
- No hace transacción gigante; cada ítem conserva garantías del servicio individual.
- Progreso por ítem actual/total.
"""

import mover_video as _mover_mod
import copiar_video as _copiar_mod
import eliminar_video as _eliminar_mod
from rutas import ruta_biblioteca


def _validar_video_ids(video_ids):
    if isinstance(video_ids, (str, bytes, bytearray)):
        raise TypeError("video_ids debe ser una colección de enteros, no texto")
    try:
        lista = list(video_ids)
    except TypeError:
        raise TypeError("video_ids debe ser una colección iterable")
    for vid in lista:
        if isinstance(vid, bool) or not isinstance(vid, int):
            raise TypeError(f"video_id debe ser entero, got {vid!r}")
        if vid <= 0:
            raise ValueError(f"video_id debe ser positivo, got {vid!r}")
    return lista


def lote_operaciones(operacion, video_ids, ruta_db, carpeta_destino=None, cancel_check=None, progreso_callback=None):
    """Ejecuta lote secuencial delegando a servicios individuales.

    Args:
        operacion: "mover" | "copiar" | "eliminar"
        video_ids: lista ordenada de video_id (estable)
        ruta_db: ruta a biblioteca.db
        carpeta_destino: requerido para mover/copiar, irrelevante para eliminar
        cancel_check: callable sin args -> True si debe cancelar antes del próximo ítem
        progreso_callback: callable (actual, total) tras cada ítem (incluye cancelados)

    Returns:
        dict con claves: total, procesados, exitosos, fallidos, cancelados, omitidos, detalles
        - total: len(video_ids)
        - procesados: exitosos+fallidos (completados)
        - exitosos: lista de {video_id, resultado, indice}
        - fallidos: lista de {video_id, error, tipo, indice, excepcion}
        - cancelados: lista de {video_id, indice, motivo}
        - omitidos: alias de cancelados (compat)
        - detalles: lista ordenada por indice con {video_id, ok, indice, resultado|error|tipo|cancelado}
    """
    if operacion not in ("mover", "copiar", "eliminar"):
        raise ValueError(f"operacion debe ser 'mover'|'copiar'|'eliminar', got {operacion!r}")
    vids = _validar_video_ids(video_ids)
    total = len(vids)
    # ruta_db: None => default biblioteca.db (compat con servicios individuales y VisorVideos default)
    if ruta_db is None:
        try:
            ruta_db = ruta_biblioteca()
        except Exception:
            pass
    if not isinstance(ruta_db, str) or not ruta_db.strip():
        raise ValueError("ruta_db debe ser texto no vacío")
    if operacion in ("mover", "copiar"):
        # No validamos existencia aquí para respetar "no pre-vuelo global"; dejamos que servicio valide.
        # Solo validamos tipo básico si se provee
        if carpeta_destino is not None and not isinstance(carpeta_destino, str):
            raise TypeError("carpeta_destino debe ser texto o None")

    detalles = []
    exitosos = []
    fallidos = []
    cancelados = []
    # omitidos es espejo de cancelados para contrato spec
    cancel_check_error = None
    for idx, vid in enumerate(vids):
        # cancelación cooperativa antes de iniciar cada ítem — caso esperado explícito, error inesperado visible
        if callable(cancel_check):
            cancelar_solicitada = False
            try:
                cancelar_solicitada = bool(cancel_check())
            except (TypeError, ValueError, RuntimeError, AttributeError) as exc:
                # error esperado de interfaz/estado: visible, no silenciado, continuar sin cancelar
                cancel_check_error = f"cancel_check falló: {type(exc).__name__}: {exc}"
                detalles.append({"video_id": vid, "ok": False, "error": cancel_check_error, "tipo": type(exc).__name__, "excepcion": exc, "indice": idx, "cancelado": False})
                fallidos.append({"video_id": vid, "error": cancel_check_error, "tipo": type(exc).__name__, "excepcion": exc, "indice": idx})
                # no cancelar, registrar y continuar al progreso visible
                cancelar_solicitada = False
            except Exception as exc:
                cancel_check_error = f"cancel_check error inesperado: {type(exc).__name__}: {exc}"
                detalles.append({"video_id": vid, "ok": False, "error": cancel_check_error, "tipo": type(exc).__name__, "excepcion": exc, "indice": idx, "cancelado": False})
                fallidos.append({"video_id": vid, "error": cancel_check_error, "tipo": type(exc).__name__, "excepcion": exc, "indice": idx})
                cancelar_solicitada = False
            if cancelar_solicitada:
                # marcar este y restantes como cancelados
                for j in range(idx, total):
                    v = vids[j]
                    entry = {"video_id": v, "indice": j, "motivo": "cancelado"}
                    cancelados.append(entry)
                    detalles.append({"video_id": v, "ok": False, "cancelado": True, "omitido": True, "error": "cancelado", "tipo": "Cancelado", "indice": j})
                    if callable(progreso_callback):
                        try:
                            progreso_callback(j + 1, total)
                        except (TypeError, ValueError, RuntimeError, AttributeError) as exc_cb:
                            # progreso con error esperado: visible pero no aborta lote
                            detalles.append({"video_id": v, "ok": False, "error": f"progreso_callback falló tras cancel: {exc_cb}", "tipo": type(exc_cb).__name__, "indice": j})
                        except Exception as exc_cb:
                            detalles.append({"video_id": v, "ok": False, "error": f"progreso_callback error inesperado tras cancel: {type(exc_cb).__name__}: {exc_cb}", "tipo": type(exc_cb).__name__, "indice": j})
                break
        # si ya cancelado y break, no ejecutar
        if len(cancelados) > 0 and idx >= len(vids) - len(cancelados):
            # ya manejado por break
            if any(d.get("indice") == idx for d in detalles):
                continue

        try:
            if operacion == "mover":
                res = _mover_mod.mover_video(vid, carpeta_destino, ruta_db)
            elif operacion == "copiar":
                res = _copiar_mod.copiar_video(vid, carpeta_destino, ruta_db)
            else:
                res = _eliminar_mod.eliminar_video(vid, ruta_db)
            exitosos.append({"video_id": vid, "resultado": res, "indice": idx})
            detalles.append({"video_id": vid, "ok": True, "resultado": res, "indice": idx})
        except Exception as exc:
            # cualquier excepción del servicio se registra como fallo parcial y se continúa
            fallidos.append({"video_id": vid, "error": str(exc), "tipo": type(exc).__name__, "excepcion": exc, "indice": idx})
            detalles.append({"video_id": vid, "ok": False, "error": str(exc), "tipo": type(exc).__name__, "excepcion": exc, "indice": idx, "cancelado": False})
        finally:
            # progreso por ítem, incluso tras fallo; errores de callback visibles, no silenciados
            if not any(c.get("video_id") == vid and c.get("indice") == idx for c in cancelados):
                if callable(progreso_callback):
                    try:
                        progreso_callback(idx + 1, total)
                    except (TypeError, ValueError, RuntimeError, AttributeError) as exc:
                        # error esperado de progreso: registrar visible sin abortar lote ni revertir DB
                        detalles.append({"video_id": vid, "ok": detalles[-1].get("ok", False) if detalles and detalles[-1].get("indice")==idx else False, "error_progreso": f"{type(exc).__name__}: {exc}", "tipo_progreso": type(exc).__name__, "indice": idx, "progreso_error": True})
                        fallidos.append({"video_id": vid, "error": f"progreso_callback falló: {exc}", "tipo": type(exc).__name__, "excepcion": exc, "indice": idx, "progreso_error": True})
                    except Exception as exc:
                        detalles.append({"video_id": vid, "ok": detalles[-1].get("ok", False) if detalles and detalles[-1].get("indice")==idx else False, "error_progreso": f"{type(exc).__name__}: {exc}", "tipo_progreso": type(exc).__name__, "indice": idx, "progreso_error": True})
                        fallidos.append({"video_id": vid, "error": f"progreso_callback error inesperado: {type(exc).__name__}: {exc}", "tipo": type(exc).__name__, "excepcion": exc, "indice": idx, "progreso_error": True})

    # Si cancelación ocurrió, el progreso ya se emitió para cada cancelado; los anteriores ya emitidos.
    # Asegurar que detalles está ordenado por indice — errores de orden visibles
    try:
        detalles = sorted(detalles, key=lambda d: d.get("indice", 0))
    except (TypeError, ValueError, AttributeError) as exc:
        # orden falló pero no silenciar: agregar registro visible
        detalles.append({"video_id": -1, "ok": False, "error": f"fallo orden detalles: {exc}", "tipo": type(exc).__name__, "indice": -1})
    except Exception as exc:
        detalles.append({"video_id": -1, "ok": False, "error": f"error inesperado orden detalles: {type(exc).__name__}: {exc}", "tipo": type(exc).__name__, "indice": -1})
    procesados = len(exitosos) + len(fallidos)
    # omitidos es alias de cancelados
    omitidos = list(cancelados)
    return {
        "total": total,
        "procesados": procesados,
        "exitosos": exitosos,
        "fallidos": fallidos,
        "cancelados": cancelados,
        "omitidos": omitidos,
        "detalles": detalles,
        # compatibilidad extra
        "exitosos_count": len(exitosos),
        "fallidos_count": len(fallidos),
        "cancelados_count": len(cancelados),
        "omitidos_count": len(omitidos),
        "operacion": operacion,
    }
