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

import os
import sqlite3

import mover_video as _mover_mod
import copiar_video as _copiar_mod
import eliminar_video as _eliminar_mod
from rutas import normalizar_ruta_clave, ruta_biblioteca


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


def _emit_progreso(progreso_callback, actual, total, detalles, fallidos, vid, idx):
    """Emite progreso y registra fallos visibles sin abortar lote.

    Capturas específicas para errores esperados de interfaz; genérico para inesperados.
    """
    if not callable(progreso_callback):
        return
    try:
        progreso_callback(actual, total)
    except (TypeError, ValueError, RuntimeError, AttributeError) as exc:
        detalles.append({"video_id": vid, "ok": False, "error_progreso": f"{type(exc).__name__}: {exc}", "tipo_progreso": type(exc).__name__, "indice": idx, "progreso_error": True})
        fallidos.append({"video_id": vid, "error": f"progreso_callback falló: {exc}", "tipo": type(exc).__name__, "excepcion": exc, "indice": idx, "progreso_error": True})
    except Exception as exc:
        detalles.append({"video_id": vid, "ok": False, "error_progreso": f"{type(exc).__name__}: {exc}", "tipo_progreso": type(exc).__name__, "indice": idx, "progreso_error": True})
        fallidos.append({"video_id": vid, "error": f"progreso_callback error inesperado: {type(exc).__name__}: {exc}", "tipo": type(exc).__name__, "excepcion": exc, "indice": idx, "progreso_error": True})


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
        except (OSError, ValueError, TypeError, sqlite3.Error):
            pass
    if not isinstance(ruta_db, str) or not ruta_db.strip():
        raise ValueError("ruta_db debe ser texto no vacío")
    if operacion in ("mover", "copiar"):
        if carpeta_destino is not None and not isinstance(carpeta_destino, str):
            raise TypeError("carpeta_destino debe ser texto o None")

    detalles = []
    exitosos = []
    fallidos = []
    cancelados = []
    # B8.3A — detección de destino físico duplicado dentro del mismo lote
    destinos_lote_norm = {}
    nombres_por_id = {}
    # Pre-cargar nombres determinísticamente para mover/copiar
    if operacion in ("mover", "copiar") and isinstance(carpeta_destino, str) and carpeta_destino.strip():
        if vids:
            if not os.path.isfile(ruta_db):
                raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
            conn_tmp = sqlite3.connect(ruta_db)
            try:
                filas = conn_tmp.execute(
                    f"SELECT id, nombre FROM videos WHERE id IN ({','.join('?' for _ in vids)})", vids
                ).fetchall()
                for fid, fnom in filas:
                    nombres_por_id[fid] = fnom
            finally:
                try:
                    conn_tmp.close()
                except OSError:
                    pass

    def _destino_lote_normalizado(vid):
        """Calcula destino normalizado para vid en lote mover/copiar.

        Si no computable por falta de nombre, retorna None para delegar a servicio.
        Si normalización falla, propaga ValueError para marcar fallido explícito.
        """
        if operacion not in ("mover", "copiar"):
            return None
        if not isinstance(carpeta_destino, str) or not carpeta_destino.strip():
            return None
        nombre = nombres_por_id.get(vid)
        if not isinstance(nombre, str) or not nombre:
            return None
        dest = os.path.join(os.path.abspath(carpeta_destino.strip()), nombre)
        # normalizar_ruta_clave puede lanzar ValueError/TypeError; no silenciar
        dest_norm = normalizar_ruta_clave(dest)
        if not isinstance(dest_norm, str) or not dest_norm.strip():
            raise ValueError(f"ruta_normalizada vacía para destino {dest!r}")
        return dest_norm
    # omitidos es espejo de cancelados para contrato spec
    for idx, vid in enumerate(vids):
        # cancelación cooperativa antes de iniciar cada ítem — caso esperado explícito, error inesperado visible
        if callable(cancel_check):
            cancelar_solicitada = False
            try:
                cancelar_solicitada = bool(cancel_check())
            except (TypeError, ValueError, RuntimeError, AttributeError) as exc:
                cancel_check_error = f"cancel_check falló: {type(exc).__name__}: {exc}"
                detalles.append({"video_id": vid, "ok": False, "error": cancel_check_error, "tipo": type(exc).__name__, "excepcion": exc, "indice": idx, "cancelado": False})
                fallidos.append({"video_id": vid, "error": cancel_check_error, "tipo": type(exc).__name__, "excepcion": exc, "indice": idx})
                cancelar_solicitada = False
            except Exception as exc:
                cancel_check_error = f"cancel_check error inesperado: {type(exc).__name__}: {exc}"
                detalles.append({"video_id": vid, "ok": False, "error": cancel_check_error, "tipo": type(exc).__name__, "excepcion": exc, "indice": idx, "cancelado": False})
                fallidos.append({"video_id": vid, "error": cancel_check_error, "tipo": type(exc).__name__, "excepcion": exc, "indice": idx})
                cancelar_solicitada = False
            if cancelar_solicitada:
                for j in range(idx, total):
                    v = vids[j]
                    entry = {"video_id": v, "indice": j, "motivo": "cancelado"}
                    cancelados.append(entry)
                    detalles.append({"video_id": v, "ok": False, "cancelado": True, "omitido": True, "error": "cancelado", "tipo": "Cancelado", "indice": j})
                    _emit_progreso(progreso_callback, j + 1, total, detalles, fallidos, v, j)
                break
        if len(cancelados) > 0 and idx >= len(vids) - len(cancelados):
            if any(d.get("indice") == idx for d in detalles):
                continue

        # B8.3A — prevalidación intra-lote: dos ítems con mismo destino físico normalizado
        dest_norm = None
        dest_error = None
        try:
            dest_norm = _destino_lote_normalizado(vid)
        except (ValueError, TypeError, OSError, sqlite3.Error) as exc:
            # fallo determinístico de normalización: marcar ítem como fallido explícito
            dest_error = f"no se pudo normalizar destino para video_id {vid}: {type(exc).__name__}: {exc}"
            fallidos.append({"video_id": vid, "error": dest_error, "tipo": type(exc).__name__, "excepcion": exc, "indice": idx})
            detalles.append({"video_id": vid, "ok": False, "error": dest_error, "tipo": type(exc).__name__, "excepcion": exc, "indice": idx, "cancelado": False})
            _emit_progreso(progreso_callback, idx + 1, total, detalles, fallidos, vid, idx)
            continue
        # si dest_norm es None (sin nombre), delegar a servicio sin prevalidación intra-lote
        if dest_norm is not None:
            if dest_norm in destinos_lote_norm:
                prev_idx = destinos_lote_norm[dest_norm]
                prev_vid = vids[prev_idx] if 0 <= prev_idx < len(vids) else None
                err_msg = f"destino físico duplicado dentro del lote: {dest_norm!r} ya solicitado por video_id {prev_vid} (índice {prev_idx}); este ítem {vid} (índice {idx}) rechaza sin overwrite"
                fallidos.append({"video_id": vid, "error": err_msg, "tipo": "ColisionError", "excepcion": Exception(err_msg), "indice": idx})
                detalles.append({"video_id": vid, "ok": False, "error": err_msg, "tipo": "ColisionError", "excepcion": Exception(err_msg), "indice": idx, "cancelado": False})
                _emit_progreso(progreso_callback, idx + 1, total, detalles, fallidos, vid, idx)
                continue
            else:
                destinos_lote_norm[dest_norm] = idx

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
            fallidos.append({"video_id": vid, "error": str(exc), "tipo": type(exc).__name__, "excepcion": exc, "indice": idx})
            detalles.append({"video_id": vid, "ok": False, "error": str(exc), "tipo": type(exc).__name__, "excepcion": exc, "indice": idx, "cancelado": False})
        finally:
            if not any(c.get("video_id") == vid and c.get("indice") == idx for c in cancelados):
                _emit_progreso(progreso_callback, idx + 1, total, detalles, fallidos, vid, idx)

    try:
        detalles = sorted(detalles, key=lambda d: d.get("indice", 0))
    except (TypeError, ValueError, AttributeError) as exc:
        detalles.append({"video_id": -1, "ok": False, "error": f"fallo orden detalles: {exc}", "tipo": type(exc).__name__, "indice": -1})
    procesados = len(exitosos) + len(fallidos)
    omitidos = list(cancelados)
    return {
        "total": total,
        "procesados": procesados,
        "exitosos": exitosos,
        "fallidos": fallidos,
        "cancelados": cancelados,
        "omitidos": omitidos,
        "detalles": detalles,
        "exitosos_count": len(exitosos),
        "fallidos_count": len(fallidos),
        "cancelados_count": len(cancelados),
        "omitidos_count": len(omitidos),
        "operacion": operacion,
    }
