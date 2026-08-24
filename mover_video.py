"""Servicio B7.2 — mover individual seguro de un video catalogado.

Contrato:
- Preserva video_id, nombre, marcadores, segmentos, colores, relaciones derivados.
- No reescanea; sí actualiza ruta en catálogo.
- Misma carpeta: rechazo/no-op.
- Destino existente: rechazo, nunca overwrite.
- Same-volume: rename atómico + UPDATE transacción + rollback inverso.
- Cross-volume: copiar streaming a temporal único en destino, flush, verificar
  tamaño y SHA-256, publicar via rename local revalidando colisión, UPDATE,
  y recién entonces eliminar origen. Compensaciones según spec.
"""

import hashlib
import os
import sqlite3
import uuid

from rutas import normalizar_ruta_clave, ruta_biblioteca


class MoverError(Exception):
    pass


class ValidacionError(MoverError):
    pass


class ColisionError(MoverError):
    pass


class OrigenNoEncontradoError(MoverError):
    pass


class HashMismatchError(MoverError):
    pass


class CompensacionFalloError(MoverError):
    """Fallo crítico: FS y DB divergentes y la compensación también falló."""

    def __init__(self, mensaje, ruta_original, ruta_nueva, error_db, error_compensacion):
        super().__init__(mensaje)
        self.ruta_original = ruta_original
        self.ruta_nueva = ruta_nueva
        self.error_db = error_db
        self.error_compensacion = error_compensacion


class CriticoMoverError(MoverError):
    """Fallo crítico post-commit cross-volume: ambas copias conservadas, DB al destino."""

    def __init__(self, mensaje, ruta_original, ruta_nueva, error_eliminar):
        super().__init__(mensaje)
        self.ruta_original = ruta_original
        self.ruta_nueva = ruta_nueva
        self.error_eliminar = error_eliminar


def _validar_video_id(video_id):
    if isinstance(video_id, bool) or not isinstance(video_id, int):
        raise TypeError("video_id debe ser un entero")
    if video_id <= 0:
        raise ValueError("video_id debe ser un entero positivo")


def _hash_sha256_stream(ruta, chunk_size=1024 * 1024):
    """SHA-256 streaming sin cargar todo en RAM."""
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _es_mismo_volumen(ruta_origen, carpeta_destino):
    """Determina si origen y destino están en el mismo volumen."""
    try:
        abs_origen = os.path.abspath(ruta_origen)
        abs_dest = os.path.abspath(carpeta_destino)
        # Windows: comparar unidad
        drive_o = os.path.splitdrive(abs_origen)[0].lower()
        drive_d = os.path.splitdrive(abs_dest)[0].lower()
        if drive_o != drive_d:
            return False
        # POSIX: comparar st_dev del directorio contenedor
        try:
            # directorio del origen (si archivo) o origen mismo si es dir
            dir_o = os.path.dirname(abs_origen) if os.path.isfile(abs_origen) else abs_origen
            # si origen no existe aún? usar dirname
            if not os.path.exists(dir_o):
                dir_o = os.path.dirname(abs_origen)
            st_o = os.stat(dir_o) if os.path.exists(dir_o) else None
            st_d = os.stat(abs_dest) if os.path.exists(abs_dest) else None
            if st_o is not None and st_d is not None and hasattr(st_o, "st_dev"):
                return st_o.st_dev == st_d.st_dev
        except Exception:
            pass
        return True
    except Exception:
        return True


def _obtener_video_por_id(conn, video_id):
    fila = conn.execute(
        "SELECT id, nombre, ruta FROM videos WHERE id = ?", (video_id,)
    ).fetchone()
    if fila is None:
        return None
    return {"id": fila[0], "nombre": fila[1], "ruta": fila[2]}


def mover_video(video_id, carpeta_destino, ruta_db=None, forzar_cross_volume=False):
    """Mueve un video catalogado a carpeta existente (B7.2).

    Mantiene mismo nombre y video_id; actualiza únicamente ruta.
    Valida misma carpeta y colisión.

    Same-volume: rename atómico -> UPDATE transacción -> si DB falla rollback.
    Cross-volume: streaming copy a temporal en destino -> flush -> verificar
      tamaño y SHA-256 -> publicar via rename local revalidando colisión ->
      comprobar destino -> UPDATE -> eliminar origen.

    forzar_cross_volume: para pruebas sin dos discos físicos; si True ejecuta
      ruta cross-volume aunque esté en mismo volumen.

    Retorna dict {ok, video_id, nombre, ruta, ruta_anterior} en éxito.
    Lanza excepciones tipadas en fallo.
    """
    _validar_video_id(video_id)
    if not isinstance(carpeta_destino, str) or not carpeta_destino.strip():
        raise ValidacionError("carpeta_destino debe ser texto no vacío")
    carpeta_destino_abs = os.path.abspath(carpeta_destino.strip())
    if not os.path.isdir(carpeta_destino_abs):
        raise ValidacionError(f"carpeta destino no existe o no es directorio: {carpeta_destino!r}")
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")

    # Cargar registro
    conn0 = sqlite3.connect(ruta_db)
    try:
        try:
            conn0.execute("SELECT 1 FROM videos LIMIT 1")
        except sqlite3.OperationalError as exc:
            raise MoverError(f"tabla videos no disponible: {exc}") from exc
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

    # Normalizar rutas absolutas para FS
    # ruta_actual puede ser relativa histórica; normalizar a absoluta para comparar
    if os.path.isabs(ruta_actual):
        ruta_actual_abs = os.path.abspath(ruta_actual)
    else:
        # si es relativa, resolver respecto a cwd actual (conservador: abspath)
        ruta_actual_abs = os.path.abspath(ruta_actual)
    nueva_ruta = os.path.join(carpeta_destino_abs, nombre)
    nueva_ruta = os.path.abspath(nueva_ruta)

    # B8.3A — contrato único de colisión por ruta_normalizada exacta
    try:
        ruta_destino_normalizada = normalizar_ruta_clave(nueva_ruta)
    except Exception as exc:
        raise ValidacionError(f"no se pudo normalizar ruta destino {nueva_ruta!r}: {exc}") from exc
    try:
        ruta_actual_normalizada = normalizar_ruta_clave(ruta_actual_abs)
    except Exception as exc:
        raise MoverError(f"no se pudo normalizar ruta actual {ruta_actual_abs!r}: {exc}") from exc
    # Misma ruta física (no-op) — mismo destino físico que origen
    if ruta_destino_normalizada == ruta_actual_normalizada:
        raise ValidacionError("origen y destino son el mismo archivo (misma ruta normalizada)")
    # Misma carpeta: rechazo/no-op claro (destino físico distinto pero misma carpeta)
    try:
        dir_actual = os.path.dirname(ruta_actual_abs)
        dir_dest_norm = os.path.normcase(os.path.normpath(carpeta_destino_abs))
        dir_actual_norm = os.path.normcase(os.path.normpath(dir_actual))
        if dir_dest_norm == dir_actual_norm:
            raise ValidacionError(f"origen y destino son la misma carpeta: {carpeta_destino_abs!r}")
    except ValidacionError:
        raise
    except Exception:
        pass

    # Destino existente en FS: rechazo nunca overwrite (aunque DB no tenga colisión)
    if os.path.exists(nueva_ruta):
        raise ColisionError(f"ya existe un archivo en destino: {nueva_ruta!r}")

    # Catálogo: otro video_id con misma ruta_normalizada destino -> rechazo
    conn_chk = sqlite3.connect(ruta_db)
    try:
        fila_dup = conn_chk.execute(
            "SELECT id FROM videos WHERE ruta_normalizada = ? AND id != ?", (ruta_destino_normalizada, video_id)
        ).fetchone()
        if fila_dup is not None:
            raise ColisionError(f"ya existe otro video con la misma ruta destino {nueva_ruta!r} (id {fila_dup[0]}, ruta_normalizada {ruta_destino_normalizada!r})")
    finally:
        try:
            conn_chk.close()
        except Exception:
            pass

    # Origen faltante
    if not os.path.isfile(ruta_actual_abs):
        # verificar también ruta relativa original si difiere
        if not os.path.isfile(ruta_actual):
            raise OrigenNoEncontradoError(f"archivo origen no encontrado: {ruta_actual!r} (resuelto {ruta_actual_abs!r})")

    # Decidir volumen
    es_mismo = _es_mismo_volumen(ruta_actual_abs, carpeta_destino_abs)
    if forzar_cross_volume:
        es_mismo = False

    if es_mismo:
        # === SAME-VOLUME ===
        # rename atómico
        try:
            os.rename(ruta_actual_abs if os.path.isfile(ruta_actual_abs) else ruta_actual, nueva_ruta)
        except OSError as exc:
            raise MoverError(f"fallo al mover en filesystem (same-volume): {exc}") from exc

        # UPDATE transacción — revalida colisión ruta_normalizada y actualiza dual-write
        conn = sqlite3.connect(ruta_db)
        try:
            conn.execute("BEGIN")
            # Carrera: otro proceso pudo insertar misma ruta_normalizada entre prevalidación y rename
            fila_dup_tx = conn.execute(
                "SELECT id FROM videos WHERE ruta_normalizada = ? AND id != ?", (ruta_destino_normalizada, video_id)
            ).fetchone()
            if fila_dup_tx is not None:
                conn.rollback()
                try:
                    os.rename(nueva_ruta, ruta_actual_abs)
                except OSError as exc_comp:
                    raise CompensacionFalloError(
                        f"colisión ruta_normalizada en transacción y compensación falló: {exc_comp}",
                        ruta_original=ruta_actual_abs,
                        ruta_nueva=nueva_ruta,
                        error_db=f"colisión ruta_normalizada {ruta_destino_normalizada!r} id {fila_dup_tx[0]}",
                        error_compensacion=str(exc_comp),
                    ) from exc_comp
                raise ColisionError(f"ya existe otro video con la misma ruta destino {nueva_ruta!r} (carrera, id {fila_dup_tx[0]})")
            cur = conn.execute(
                "UPDATE videos SET ruta = ?, ruta_normalizada = ? WHERE id = ?",
                (nueva_ruta, ruta_destino_normalizada, video_id),
            )
            if cur.rowcount == 0:
                conn.rollback()
                try:
                    os.rename(nueva_ruta, ruta_actual_abs)
                except OSError as exc_comp:
                    raise CompensacionFalloError(
                        f"video_id {video_id} no encontrado tras rename y compensación falló",
                        ruta_original=ruta_actual_abs,
                        ruta_nueva=nueva_ruta,
                        error_db="UPDATE rowcount 0",
                        error_compensacion=str(exc_comp),
                    ) from exc_comp
                raise MoverError(f"video_id {video_id} no encontrado para actualizar")
            conn.commit()
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                os.rename(nueva_ruta, ruta_actual_abs)
            except OSError as exc_comp:
                raise CompensacionFalloError(
                    f"fallo SQLite tras rename FS y la compensación también falló: {exc} | compensación: {exc_comp}",
                    ruta_original=ruta_actual_abs,
                    ruta_nueva=nueva_ruta,
                    error_db=str(exc),
                    error_compensacion=str(exc_comp),
                ) from exc_comp
            raise MoverError(f"fallo al persistir movimiento en DB (FS restaurado): {exc}") from exc
        except MoverError:
            raise
        except CompensacionFalloError:
            raise
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                os.rename(nueva_ruta, ruta_actual_abs)
            except OSError as exc_comp:
                raise CompensacionFalloError(
                    f"fallo inesperado tras rename y compensación falló: {exc} | compensación: {exc_comp}",
                    ruta_original=ruta_actual_abs,
                    ruta_nueva=nueva_ruta,
                    error_db=str(exc),
                    error_compensacion=str(exc_comp),
                ) from exc_comp
            raise MoverError(f"fallo inesperado al mover: {exc}") from exc
        finally:
            try:
                conn.close()
            except Exception:
                pass

        return {
            "ok": True,
            "video_id": video_id,
            "nombre": nombre,
            "ruta": nueva_ruta,
            "ruta_anterior": ruta_actual_abs,
            "modo": "same-volume",
        }

    else:
        # === CROSS-VOLUME ===
        ruta_temporal = None
        # Generar temporal único en carpeta destino
        for _ in range(5):
            tmp_name = f".tmp_mover_{uuid.uuid4().hex}_{nombre}.part"
            cand = os.path.join(carpeta_destino_abs, tmp_name)
            if not os.path.exists(cand):
                ruta_temporal = cand
                break
        if ruta_temporal is None:
            raise MoverError("no se pudo generar temporal único")
        # Paso 1: copiar streaming a temporal
        try:
            # Copia streaming
            with open(ruta_actual_abs, "rb") as src:
                with open(ruta_temporal, "wb") as dst:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)
                    try:
                        dst.flush()
                        os.fsync(dst.fileno())
                    except Exception:
                        pass
            # Cierre ya hecho por context
            # Verificar que temporal existe y tamaño
            if not os.path.isfile(ruta_temporal):
                raise MoverError("temporal no creado tras copia")
        except OSError as exc:
            # limpiar temporal parcial
            try:
                if ruta_temporal and os.path.exists(ruta_temporal):
                    os.remove(ruta_temporal)
            except Exception:
                pass
            raise MoverError(f"fallo al copiar a temporal: {exc}") from exc
        except Exception as exc:
            try:
                if ruta_temporal and os.path.exists(ruta_temporal):
                    os.remove(ruta_temporal)
            except Exception:
                pass
            raise MoverError(f"fallo inesperado al copiar: {exc}") from exc

        # Paso 3: verificar tamaño y SHA-256
        try:
            tam_origen = os.path.getsize(ruta_actual_abs)
            tam_temp = os.path.getsize(ruta_temporal)
            if tam_origen != tam_temp:
                try:
                    os.remove(ruta_temporal)
                except Exception:
                    pass
                raise HashMismatchError(f"tamaño distinto origen {tam_origen} vs temporal {tam_temp}")
            hash_origen = _hash_sha256_stream(ruta_actual_abs)
            hash_temp = _hash_sha256_stream(ruta_temporal)
            if hash_origen != hash_temp:
                try:
                    os.remove(ruta_temporal)
                except Exception:
                    pass
                raise HashMismatchError(f"SHA-256 distinto origen {hash_origen[:8]} vs temporal {hash_temp[:8]}")
        except HashMismatchError:
            raise
        except OSError as exc:
            try:
                if os.path.exists(ruta_temporal):
                    os.remove(ruta_temporal)
            except Exception:
                pass
            raise MoverError(f"fallo al verificar tamaño/hash: {exc}") from exc
        except Exception as exc:
            try:
                if os.path.exists(ruta_temporal):
                    os.remove(ruta_temporal)
            except Exception:
                pass
            raise MoverError(f"fallo inesperado en verificación: {exc}") from exc

        # Paso 4: publicar temporal a destino final por rename atómico local, revalidando colisión
        try:
            if os.path.exists(nueva_ruta):
                try:
                    os.remove(ruta_temporal)
                except Exception:
                    pass
                raise ColisionError(f"colisión al publicar: ya existe destino {nueva_ruta!r}")
            os.rename(ruta_temporal, nueva_ruta)
        except ColisionError:
            raise
        except OSError as exc:
            try:
                if os.path.exists(ruta_temporal):
                    os.remove(ruta_temporal)
            except Exception:
                pass
            # si quedó dest parcial, limpiar
            try:
                if os.path.exists(nueva_ruta) and os.path.getsize(nueva_ruta) == 0:
                    os.remove(nueva_ruta)
            except Exception:
                pass
            raise MoverError(f"fallo al publicar temporal a destino: {exc}") from exc

        # Paso 5: comprobar destino final existente
        if not os.path.isfile(nueva_ruta):
            # intentar limpiar? origen intacto
            raise MoverError("destino final no existe tras publicación")

        # Paso 6: UPDATE SQLite — dual-write ruta_normalizada y revalida colisión
        conn = sqlite3.connect(ruta_db)
        try:
            conn.execute("BEGIN")
            fila_dup_tx2 = conn.execute(
                "SELECT id FROM videos WHERE ruta_normalizada = ? AND id != ?", (ruta_destino_normalizada, video_id)
            ).fetchone()
            if fila_dup_tx2 is not None:
                conn.rollback()
                try:
                    if os.path.isfile(nueva_ruta):
                        os.remove(nueva_ruta)
                except Exception:
                    pass
                raise ColisionError(f"ya existe otro video con la misma ruta destino {nueva_ruta!r} (carrera cross-volume, id {fila_dup_tx2[0]})")
            cur = conn.execute(
                "UPDATE videos SET ruta = ?, ruta_normalizada = ? WHERE id = ?",
                (nueva_ruta, ruta_destino_normalizada, video_id),
            )
            if cur.rowcount == 0:
                conn.rollback()
                # compensar destino: eliminar copia
                try:
                    if os.path.isfile(nueva_ruta):
                        os.remove(nueva_ruta)
                except Exception:
                    pass
                raise MoverError(f"video_id {video_id} no encontrado para actualizar (cross-volume)")
            conn.commit()
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            # compensar destino, origen intacto
            try:
                if os.path.isfile(nueva_ruta):
                    os.remove(nueva_ruta)
            except Exception:
                pass
            raise MoverError(f"fallo DB cross-volume (origen intacto, destino compensado): {exc}") from exc
        except MoverError:
            raise
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                if os.path.isfile(nueva_ruta):
                    os.remove(nueva_ruta)
            except Exception:
                pass
            raise MoverError(f"fallo inesperado DB cross-volume: {exc}") from exc
        finally:
            try:
                conn.close()
            except Exception:
                pass

        # Paso 7: recién entonces eliminar origen
        try:
            os.remove(ruta_actual_abs)
        except OSError as exc:
            # Conservar ambas copias, DB al destino, error crítico explícito
            # No intentar rollback DB (ya committed)
            raise CriticoMoverError(
                f"movimiento cross-volume completado en DB y destino, pero fallo al eliminar origen (ambas copias conservadas, DB al destino): {exc}",
                ruta_original=ruta_actual_abs,
                ruta_nueva=nueva_ruta,
                error_eliminar=str(exc),
            ) from exc
        except Exception as exc:
            raise CriticoMoverError(
                f"fallo inesperado al eliminar origen tras commit (ambas copias conservadas): {exc}",
                ruta_original=ruta_actual_abs,
                ruta_nueva=nueva_ruta,
                error_eliminar=str(exc),
            ) from exc

        # Limpiar cualquier resto temporal (no debería existir)
        try:
            if ruta_temporal and os.path.exists(ruta_temporal):
                os.remove(ruta_temporal)
        except Exception:
            pass

        return {
            "ok": True,
            "video_id": video_id,
            "nombre": nombre,
            "ruta": nueva_ruta,
            "ruta_anterior": ruta_actual_abs,
            "modo": "cross-volume",
        }
