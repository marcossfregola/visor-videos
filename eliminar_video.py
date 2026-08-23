"""Servicio B7.5 — eliminación individual segura a Papelera Windows.

Contrato:
- Resuelve video_id -> nombre/ruta via SQLite.
- Valida origen existente en FS.
- Envía a Papelera mediante mecanismo histórico seguro
  (SHFileOperationW + FOF_ALLOWUNDO).
  Nunca usa borrado permanente del archivo.
- Si Papelera falla: DB intacta, lanza EliminarError.
- Si Papelera tuvo éxito y la actualización de catálogo falla:
  lanza EliminarInconsistenciaError explícita con ruta ya en Papelera
  y detalle de error DB, sin ocultarlo ni compensar borrando.
- Catálogo: en transacción, elimina marcadores_video y segmentos_video
  del video_id (evita huérfanos) y luego DELETE FROM videos.
  No borra videos_derivados / videos_derivados_segmentos (orfandad
  histórica tolerada por diseño, sin FK CASCADE). No requiere migración.
- No usa recodificación.
- Reutiliza mecanismo existente sin añadir dependencia externa.
"""

import os
import sqlite3

import operaciones as operaciones_mod
from rutas import ruta_biblioteca


class EliminarError(Exception):
    pass


class ValidacionError(EliminarError):
    pass


class OrigenNoEncontradoError(EliminarError):
    pass


class EliminarInconsistenciaError(EliminarError):
    """Fallo DB post-Papelera: archivo ya en Papelera pero catálogo no actualizado.

    Atributos: ruta (str), error_db (str)
    """

    def __init__(self, mensaje, ruta, error_db):
        super().__init__(mensaje)
        self.ruta = ruta
        self.error_db = error_db


def _validar_video_id(video_id):
    if isinstance(video_id, bool) or not isinstance(video_id, int):
        raise TypeError("video_id debe ser un entero")
    if video_id <= 0:
        raise ValueError("video_id debe ser un entero positivo")


def _obtener_video_por_id(conn, video_id):
    fila = conn.execute(
        "SELECT id, nombre, ruta FROM videos WHERE id = ?", (video_id,)
    ).fetchone()
    if fila is None:
        return None
    return {"id": fila[0], "nombre": fila[1], "ruta": fila[2]}


def eliminar_video(video_id, ruta_db=None):
    """Elimina un video catalogado enviándolo a la Papelera (B7.5).

    Retorna dict {ok, video_id, nombre, ruta} en éxito.
    Lanza ValidacionError / OrigenNoEncontradoError /
    EliminarInconsistenciaError / EliminarError en fallos.

    Nunca usa os.remove para el video; solo _enviar_a_papelera.
    """
    _validar_video_id(video_id)
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not isinstance(ruta_db, str) or not ruta_db.strip():
        raise ValidacionError("ruta_db debe ser texto no vacío")
    # Normalizar ruta_db a abs para verificar existencia
    ruta_db_abs = os.path.abspath(ruta_db.strip()) if os.path.isabs(ruta_db.strip()) else os.path.abspath(ruta_db.strip())
    # Verificar DB existe (usar ruta original si es relativa)
    check_path = ruta_db if os.path.isfile(ruta_db) else ruta_db_abs
    if not os.path.isfile(check_path):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")

    conn0 = sqlite3.connect(check_path)
    try:
        try:
            conn0.execute("SELECT 1 FROM videos LIMIT 1")
        except sqlite3.OperationalError as exc:
            raise EliminarError(f"tabla videos no disponible: {exc}") from exc
        video = _obtener_video_por_id(conn0, video_id)
        if video is None:
            raise ValidacionError(f"video_id {video_id} no existe")
        nombre = video["nombre"]
        ruta_actual = video["ruta"]
    finally:
        try:
            conn0.close()
        except Exception:
            pass

    if not isinstance(nombre, str) or not nombre:
        raise ValidacionError("nombre en DB inválido")
    if not isinstance(ruta_actual, str) or not ruta_actual:
        raise ValidacionError("ruta en DB inválida")

    # Resolver ruta absoluta para FS
    if os.path.isabs(ruta_actual):
        ruta_actual_abs = os.path.abspath(ruta_actual)
    else:
        ruta_actual_abs = os.path.abspath(ruta_actual)

    # Determinar ruta objetivo existente
    # Preferir ruta_actual_abs si existe, sino ruta_actual original
    target_path = None
    if os.path.isfile(ruta_actual_abs):
        target_path = ruta_actual_abs
    elif os.path.isfile(ruta_actual):
        target_path = ruta_actual
    else:
        raise OrigenNoEncontradoError(
            f"archivo origen no encontrado: {ruta_actual!r} (resuelto {ruta_actual_abs!r})"
        )

    # Enviar a Papelera mediante mecanismo histórico seguro
    try:
        operaciones_mod._enviar_a_papelera(target_path)
    except OSError as exc:
        # DB intacta
        raise EliminarError(f"no se pudo enviar a la Papelera: {exc}") from exc
    except Exception as exc:
        raise EliminarError(f"fallo inesperado al enviar a Papelera: {exc}") from exc

    # Verificar que ya no existe en FS (Papelera movió)
    # No es error si aún visible por handle bloqueado? SHFileOperation ya habría fallado.
    # No validamos estrictamente; continuamos a catalogo.

    # Actualización catálogo en transacción
    conn = sqlite3.connect(check_path)
    try:
        conn.execute("BEGIN")
        # Evitar huérfanos: borrar marcadores y segmentos asociados
        try:
            conn.execute("DELETE FROM marcadores_video WHERE video_id = ?", (video_id,))
        except sqlite3.OperationalError:
            # tabla puede no existir en DB vieja sin marcadores, ignorar
            pass
        try:
            conn.execute("DELETE FROM segmentos_video WHERE video_id = ?", (video_id,))
        except sqlite3.OperationalError:
            pass
        # No tocar videos_derivados / videos_derivados_segmentos (orfandad tolerada)
        cur = conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        if cur.rowcount == 0:
            conn.rollback()
            raise EliminarInconsistenciaError(
                f"video_id {video_id} no encontrado para eliminar tras Papelera (archivo en Papelera en {target_path!r} conservado)",
                ruta=target_path,
                error_db="DELETE rowcount 0",
            )
        conn.commit()
    except EliminarInconsistenciaError:
        raise
    except (sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        raise EliminarInconsistenciaError(
            f"fallo DB tras Papelera (archivo en Papelera en {target_path!r} conservado, requiere intervención): {exc}",
            ruta=target_path,
            error_db=str(exc),
        ) from exc
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        # Clasificar como inconsistencia si archivo ya en Papelera
        raise EliminarInconsistenciaError(
            f"fallo inesperado DB tras Papelera (archivo en Papelera en {target_path!r}): {exc}",
            ruta=target_path,
            error_db=str(exc),
        ) from exc
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return {
        "ok": True,
        "video_id": video_id,
        "nombre": nombre,
        "ruta": target_path,
        "ruta_anterior": target_path,
    }
