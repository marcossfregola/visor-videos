"""Servicio B7.4 — copia individual segura de un video catalogado (B8.3A).

Contrato B8.3A:
- Recibe video_id, carpeta_destino, ruta_db.
- Valida origen, destino, misma carpeta y colisiones por destino físico normalizado exacto.
- Mismo nombre en otra carpeta = permitido (homónimo); distingue por ruta_normalizada.
- Destino exacto libre -> copiar y catalogar por ruta_normalizada con NUEVO video_id.
- Destino exacto ocupada (FS o catálogo) -> rechazar sin overwrite ni reutilización ID.
- Copia a temporal exclusivo dentro del destino; verifica tamaño + SHA-256;
  publica a ruta final sin sobrescritura (rename local).
- Incorpora el nuevo archivo al catálogo incrementalmente con nuevo video_id
  usando helpers existentes y metadata correcta, sin reescaneo global.
- Si falla antes de publicar: limpiar solo temporal propio.
- Si falla catalogación DESPUÉS de publicar, no borrar silenciosamente un
  archivo válido: devolver estado de inconsistencia claro para que UI informe.
  Nunca dejar SQLite apuntando a archivo inexistente.
- Origen y su DB/relaciones permanecen intactos.
- No genera sufijos _001 por nombre UNIQUE; la identidad es ruta_normalizada.
  Colisión FS existente se rechaza (no overwrite, no auto-rename sobre FS).
"""

import hashlib
import os
import shutil
import sqlite3
import uuid
from datetime import datetime

import nombres as nombres_mod
from rutas import normalizar_ruta_clave, ruta_biblioteca, ruta_carpeta_miniaturas


class CopiarError(Exception):
    pass


class ValidacionError(CopiarError):
    pass


class ColisionError(CopiarError):
    pass


class OrigenNoEncontradoError(CopiarError):
    pass


class HashMismatchError(CopiarError):
    pass


class CopiarInconsistenciaError(CopiarError):
    """Fallo DB post-publicación: archivo válido en FS pero no catalogado.

    No se borra el archivo silenciosamente; la UI debe informar inconsistencia.
    Atributos: ruta_nueva (str), error_db (str)
    """

    def __init__(self, mensaje, ruta_nueva, error_db):
        super().__init__(mensaje)
        self.ruta_nueva = ruta_nueva
        self.error_db = error_db


def _validar_video_id(video_id):
    if isinstance(video_id, bool) or not isinstance(video_id, int):
        raise TypeError("video_id debe ser un entero")
    if video_id <= 0:
        raise ValueError("video_id debe ser un entero positivo")


def _hash_sha256_stream(ruta, chunk_size=1024 * 1024):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _obtener_video_por_id(conn, video_id):
    fila = conn.execute(
        "SELECT id, nombre, ruta FROM videos WHERE id = ?", (video_id,)
    ).fetchone()
    if fila is None:
        return None
    return {"id": fila[0], "nombre": fila[1], "ruta": fila[2]}


def _existe_fs_case_insensitive(carpeta, nombre):
    """True si existe archivo/carpeta con mismo nombre case-insensitive en carpeta."""
    try:
        # fast path: exact exists (case-sensitive on Linux, case-insensitive on Windows)
        if os.path.exists(os.path.join(carpeta, nombre)):
            # On Windows normcase would already handle, on Linux we need extra lower check
            # If exists, definitely colision (even case-sensitive). Return True.
            return True
    except Exception:
        pass
    try:
        entradas = os.listdir(carpeta)
        low = nombre.lower()
        norm = os.path.normcase(nombre)
        for e in entradas:
            if e.lower() == low:
                return True
            try:
                if os.path.normcase(e) == norm:
                    return True
            except Exception:
                pass
    except OSError:
        pass
    return False


def _nombre_seguro_copia(nombre):
    """Replica escanear_videos._nombre_seguro sin ciclo."""
    return nombre.replace(os.sep, "_").replace("/", "_")


def _replicar_cache_miniaturas(nombre_original, nombre_final):
    """Copia miniatura/previews de nombre_original hacia nombre_final (B7.4 fix-027).

    Solo copia archivos cuyo sufijo tras el prefijo sea _<digitos> o
    _preview_<digitos> (evita colisiones tipo video vs video_realista).
    No sobrescribe destino existente. Copia con shutil.copyfile (mtime nuevo)
    para que miniatura_vigente sea True respecto del video copiado (cuya
    mtime es ahora). No requiere FFmpeg.
    Retorna (mini_copiadas, preview_copiadas). Errores silenciosos por
    archivo; si carpeta miniaturas no existe, retorna (0,0).
    """
    try:
        import rutas as _rutas_dyn  # resolución dinámica para permitir monkeypatch en tests
        carpeta_mini = _rutas_dyn.ruta_carpeta_miniaturas()
    except Exception:
        try:
            carpeta_mini = ruta_carpeta_miniaturas()
        except Exception:
            return (0, 0)
    if not isinstance(carpeta_mini, str) or not carpeta_mini:
        return (0, 0)
    if not os.path.isdir(carpeta_mini):
        return (0, 0)
    if not isinstance(nombre_original, str) or not nombre_original:
        return (0, 0)
    if not isinstance(nombre_final, str) or not nombre_final:
        return (0, 0)
    prefijo_old = _nombre_seguro_copia(os.path.splitext(nombre_original)[0])
    prefijo_new = _nombre_seguro_copia(os.path.splitext(nombre_final)[0])
    if prefijo_old == prefijo_new:
        return (0, 0)
    try:
        archivos = os.listdir(carpeta_mini)
    except OSError:
        return (0, 0)
    # Recolectar src->dst
    pares = []
    for fname in archivos:
        if not fname.lower().endswith(".jpg"):
            continue
        base, ext = os.path.splitext(fname)
        # preview primero (más específico)
        if base.startswith(prefijo_old + "_preview_"):
            suffix = base[len(prefijo_old):]  # _preview_XX
            rest = suffix[len("_preview_"):]
            if rest.isdigit():
                new_name = prefijo_new + suffix + ext
                src = os.path.join(carpeta_mini, fname)
                dst = os.path.join(carpeta_mini, new_name)
                if src != dst and os.path.isfile(src) and not os.path.exists(dst):
                    pares.append((src, dst, True))
            continue
        if base.startswith(prefijo_old + "_"):
            suffix = base[len(prefijo_old):]  # _NN
            rest = suffix[1:] if suffix.startswith("_") else ""
            if rest.isdigit():
                new_name = prefijo_new + suffix + ext
                src = os.path.join(carpeta_mini, fname)
                dst = os.path.join(carpeta_mini, new_name)
                if src != dst and os.path.isfile(src) and not os.path.exists(dst):
                    pares.append((src, dst, False))
    mini_copiadas = 0
    preview_copiadas = 0
    for src, dst, es_preview in pares:
        try:
            # copyfile crea mtime nuevo (ahora) para vigencia vs video nuevo
            shutil.copyfile(src, dst)
            # preservar accesible, no preservar mtime viejo
            try:
                # asegurar mtime del destino sea >= ahora (copyfile ya lo hace)
                pass
            except Exception:
                pass
            if es_preview:
                preview_copiadas += 1
            else:
                mini_copiadas += 1
        except OSError:
            continue
        except Exception:
            continue
    return (mini_copiadas, preview_copiadas)


def copiar_video(video_id, carpeta_destino, ruta_db=None):
    """Copia un video catalogado a carpeta existente (B7.4).

    - Mantiene origen intacto; nuevo video_id distinto; no copia marcadores/segmentos.
    - Si nombre UNIQUE impide mismo nombre, genera nombre con sufijo _001 via B6.8.
    - FS existente en destino se rechaza (no overwrite).
    - Verifica tamaño y SHA-256 via temporal.
    - Incorpora incrementalmente sin reescaneo.

    Retorna dict {ok, video_id, nombre, ruta, video_id_original, nombre_original,
                  ruta_original, nombre_final, modo} en éxito.

    Lanza ValidacionError / ColisionError / OrigenNoEncontradoError /
    HashMismatchError / CopiarInconsistenciaError / CopiarError en fallos.
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

    # Cargar registro original
    conn0 = sqlite3.connect(ruta_db)
    try:
        try:
            conn0.execute("SELECT 1 FROM videos LIMIT 1")
        except sqlite3.OperationalError as exc:
            raise CopiarError(f"tabla videos no disponible: {exc}") from exc
        video = _obtener_video_por_id(conn0, video_id)
        if video is None:
            raise ValidacionError(f"video_id {video_id} no existe")
        nombre_original = video["nombre"]
        ruta_actual = video["ruta"]
    finally:
        try:
            conn0.close()
        except Exception:
            pass

    if not isinstance(nombre_original, str) or not nombre_original:
        raise ValidacionError("nombre en DB inválido")
    if not isinstance(ruta_actual, str) or not ruta_actual:
        raise ValidacionError("ruta en DB inválida")

    # Normalizar ruta origen a absoluta para FS
    if os.path.isabs(ruta_actual):
        ruta_actual_abs = os.path.abspath(ruta_actual)
    else:
        ruta_actual_abs = os.path.abspath(ruta_actual)

    # Misma carpeta: rechazo
    try:
        dir_actual = os.path.dirname(ruta_actual_abs)
        dir_dest_norm = os.path.normcase(os.path.normpath(carpeta_destino_abs))
        dir_actual_norm = os.path.normcase(os.path.normpath(dir_actual))
        if dir_dest_norm == dir_actual_norm:
            raise ValidacionError(f"origen y destino son la misma carpeta: {carpeta_destino_abs!r}")
        # también verificar ruta final igual (mismo archivo) - se validará con nombre_final luego
    except ValidacionError:
        raise
    except Exception:
        pass

    # Origen faltante
    if not os.path.isfile(ruta_actual_abs):
        if not os.path.isfile(ruta_actual):
            raise OrigenNoEncontradoError(f"archivo origen no encontrado: {ruta_actual!r} (resuelto {ruta_actual_abs!r})")
        # si ruta relativa existe pero abs no, usar relativa para lectura
        ruta_actual_abs = os.path.abspath(ruta_actual) if os.path.isfile(os.path.abspath(ruta_actual)) else ruta_actual

    # B8.3A — destino exacto: mismo basename en otra carpeta permitido, sin sufijo
    # Copiar crea archivo físico distinto y debe obtener NUEVO video_id, aunque conserve mismo nombre visible.
    nombre_final = nombre_original
    nueva_ruta = os.path.join(carpeta_destino_abs, nombre_final)
    nueva_ruta = os.path.abspath(nueva_ruta)

    # Contrato único de colisión por ruta_normalizada exacta
    try:
        ruta_destino_normalizada = normalizar_ruta_clave(nueva_ruta)
    except Exception as exc:
        raise ValidacionError(f"no se pudo normalizar ruta destino {nueva_ruta!r}: {exc}") from exc
    try:
        ruta_actual_normalizada = normalizar_ruta_clave(ruta_actual_abs)
    except Exception as exc:
        raise CopiarError(f"no se pudo normalizar ruta origen {ruta_actual_abs!r}: {exc}") from exc

    # Mismo archivo físico (no-op) — origen y destino misma ruta normalizada
    if ruta_destino_normalizada == ruta_actual_normalizada:
        raise ValidacionError("origen y destino son el mismo archivo (misma ruta normalizada)")

    # Misma carpeta ya validada arriba, pero si por ruta normalizada es misma carpeta y mismo nombre también es colisión
    # FS destino existe -> rechazo nunca overwrite (case-insensitive Windows)
    if _existe_fs_case_insensitive(carpeta_destino_abs, nombre_final) or os.path.exists(nueva_ruta):
        raise ColisionError(f"ya existe un archivo en destino: {nueva_ruta!r}")

    # Catálogo: ruta_destino_normalizada ya catalogada -> rechazo (otro video_id)
    conn_check = sqlite3.connect(ruta_db)
    try:
        fila_dup = conn_check.execute(
            "SELECT id FROM videos WHERE ruta_normalizada = ?", (ruta_destino_normalizada,)
        ).fetchone()
        if fila_dup is not None:
            raise ColisionError(f"ya existe otro video catalogado en destino {nueva_ruta!r} (id {fila_dup[0]}, ruta_normalizada {ruta_destino_normalizada!r})")
    finally:
        try:
            conn_check.close()
        except Exception:
            pass

    # === Copia a temporal exclusivo dentro del destino ===
    ruta_temporal = None
    for _ in range(5):
        tmp_name = f".tmp_copiar_{uuid.uuid4().hex}_{nombre_final}.part"
        cand = os.path.join(carpeta_destino_abs, tmp_name)
        if not os.path.exists(cand):
            ruta_temporal = cand
            break
    if ruta_temporal is None:
        raise CopiarError("no se pudo generar temporal único")

    # Copia streaming
    try:
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
        if not os.path.isfile(ruta_temporal):
            raise CopiarError("temporal no creado tras copia")
    except OSError as exc:
        try:
            if ruta_temporal and os.path.exists(ruta_temporal):
                os.remove(ruta_temporal)
        except Exception:
            pass
        raise CopiarError(f"fallo al copiar a temporal: {exc}") from exc
    except Exception as exc:
        try:
            if ruta_temporal and os.path.exists(ruta_temporal):
                os.remove(ruta_temporal)
        except Exception:
            pass
        raise CopiarError(f"fallo inesperado al copiar: {exc}") from exc

    # Verificar tamaño y SHA-256
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
        raise CopiarError(f"fallo al verificar tamaño/hash: {exc}") from exc
    except Exception as exc:
        try:
            if os.path.exists(ruta_temporal):
                os.remove(ruta_temporal)
        except Exception:
            pass
        raise CopiarError(f"fallo inesperado en verificación: {exc}") from exc

    # Publicar temporal a destino final por rename atómico local, revalidando colisión ruta_normalizada exacta
    try:
        if _existe_fs_case_insensitive(carpeta_destino_abs, nombre_final) or os.path.exists(nueva_ruta):
            try:
                os.remove(ruta_temporal)
            except Exception:
                pass
            raise ColisionError(f"colisión al publicar: ya existe destino {nueva_ruta!r}")
        # Revalidar catálogo por ruta_normalizada antes de publicar (evita publicar si otro insertó misma ruta)
        conn_pre_pub = sqlite3.connect(ruta_db)
        try:
            fila_dup_pub = conn_pre_pub.execute(
                "SELECT id FROM videos WHERE ruta_normalizada = ?", (ruta_destino_normalizada,)
            ).fetchone()
            if fila_dup_pub is not None:
                try:
                    os.remove(ruta_temporal)
                except Exception:
                    pass
                raise ColisionError(f"colisión al publicar: ya existe video catalogado en destino {nueva_ruta!r} (id {fila_dup_pub[0]})")
        finally:
            try:
                conn_pre_pub.close()
            except Exception:
                pass
        os.rename(ruta_temporal, nueva_ruta)
    except ColisionError:
        raise
    except OSError as exc:
        try:
            if os.path.exists(ruta_temporal):
                os.remove(ruta_temporal)
        except Exception:
            pass
        try:
            if os.path.exists(nueva_ruta) and os.path.getsize(nueva_ruta) == 0:
                os.remove(nueva_ruta)
        except Exception:
            pass
        raise CopiarError(f"fallo al publicar temporal a destino: {exc}") from exc

    if not os.path.isfile(nueva_ruta):
        raise CopiarError("destino final no existe tras publicación")

    # Limpiar resto temporal (no debería existir)
    try:
        if ruta_temporal and os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)
    except Exception:
        pass

    # === Incorporación incremental al catálogo con nuevo video_id ===
    # Obtener metadata física derivable del archivo copiado
    try:
        st = os.stat(nueva_ruta)
        tamano_bytes = st.st_size
        mtime_ns = st.st_mtime_ns
    except OSError as exc:
        # Archivo válido en FS pero no se puede stat: inconsistencia
        raise CopiarInconsistenciaError(
            f"copia publicada en FS pero no se pudo obtener stat para catalogación (archivo conservado): {exc}",
            ruta_nueva=nueva_ruta,
            error_db=str(exc),
        ) from exc

    # FFprobe (no bloqueante para catalogación, pero intentamos)
    duracion = None
    ancho = None
    alto = None
    codec = None
    try:
        import escanear_videos as escanear_mod
        datos_ff = escanear_mod.obtener_datos_ffprobe(nueva_ruta)
        if isinstance(datos_ff, dict):
            duracion = datos_ff.get("duracion_segundos")
            ancho = datos_ff.get("ancho")
            alto = datos_ff.get("alto")
            codec = datos_ff.get("codec_video")
    except Exception:
        # No es crítico: continuamos con metadata parcial
        pass

    # Validar duracion si existe
    try:
        if duracion is not None:
            # si no es utilizable, setear None para no almacenar basura
            import math
            if not isinstance(duracion, (int, float)) or isinstance(duracion, bool) or not math.isfinite(float(duracion)) or float(duracion) <= 0:
                duracion = None
    except Exception:
        duracion = None

    # Alta en SQLite (INSERT, no upsert) — identidad por ruta_normalizada
    conn2 = None
    try:
        import escanear_videos as escanear_mod
        conn2 = escanear_mod.conectar_bd(ruta_db)
        conn2.execute("BEGIN")
        # Revalidar duplicado dentro de transacción por ruta_normalizada exacta (carrera)
        fila_dup2 = conn2.execute(
            "SELECT id FROM videos WHERE ruta_normalizada = ?", (ruta_destino_normalizada,)
        ).fetchone()
        if fila_dup2 is not None:
            conn2.rollback()
            # Archivo ya publicado con ruta que ahora colisiona (carrera)
            # No borrar archivo silenciosamente: informar inconsistencia
            raise CopiarInconsistenciaError(
                f"ruta duplicada en catálogo al incorporar copia (carrera): {nueva_ruta!r} ya existe id {fila_dup2[0]} (ruta_normalizada {ruta_destino_normalizada!r}) — archivo en {nueva_ruta!r} conservado pero no catalogado",
                ruta_nueva=nueva_ruta,
                error_db=f"duplicate ruta_normalizada {ruta_destino_normalizada!r}",
            )

        extension_col = os.path.splitext(nombre_final)[1].lower()
        if not extension_col:
            extension_col = ".mp4"
        fecha_imp = datetime.now().isoformat()
        # B8.3 schema ya preparado por conectar_bd; no silenciar fallo de migración aditiva
        escanear_mod._asegurar_columnas_videos(conn2)

        # INSERT explícito (no upsert) para preservar identidad nueva, incluye ruta_normalizada NOT NULL UNIQUE
        conn2.execute(
            """
            INSERT INTO videos (nombre, ruta, ruta_normalizada, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes, mtime_ns)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nombre_final,
                os.path.abspath(nueva_ruta),
                ruta_destino_normalizada,
                extension_col,
                fecha_imp,
                float(duracion) if isinstance(duracion, (int, float)) and duracion is not None else None,
                int(ancho) if isinstance(ancho, int) and ancho > 0 else None,
                int(alto) if isinstance(alto, int) and alto > 0 else None,
                str(codec) if isinstance(codec, str) and codec.strip() else None,
                0,
                int(tamano_bytes),
                int(mtime_ns),
            ),
        )
        conn2.commit()
        # Obtener nuevo id por ruta_normalizada (inequívoco para homónimos)
        fila_new = conn2.execute(
            "SELECT id FROM videos WHERE ruta_normalizada = ?",
            (ruta_destino_normalizada,),
        ).fetchone()
        if fila_new is None:
            # Inconsistencia: INSERT aparentemente ok pero no se encuentra
            raise CopiarInconsistenciaError(
                f"no se pudo obtener id del nuevo video tras insertar {nombre_final!r} — archivo en {nueva_ruta!r} conservado",
                ruta_nueva=nueva_ruta,
                error_db="SELECT id after INSERT returned None",
            )
        nuevo_id = fila_new[0]
    except CopiarInconsistenciaError:
        raise
    except sqlite3.IntegrityError as exc:
        try:
            if conn2 is not None:
                conn2.rollback()
        except Exception:
            pass
        # No borrar archivo: inconsistencia clara
        raise CopiarInconsistenciaError(
            f"integridad de catálogo al incorporar copia (archivo en {nueva_ruta!r} conservado): {exc}",
            ruta_nueva=nueva_ruta,
            error_db=str(exc),
        ) from exc
    except sqlite3.OperationalError as exc:
        try:
            if conn2 is not None:
                conn2.rollback()
        except Exception:
            pass
        raise CopiarInconsistenciaError(
            f"fallo DB al incorporar copia (archivo en {nueva_ruta!r} conservado): {exc}",
            ruta_nueva=nueva_ruta,
            error_db=str(exc),
        ) from exc
    except Exception as exc:
        try:
            if conn2 is not None:
                conn2.rollback()
        except Exception:
            pass
        # Si es otro error no previsto y ya publicamos, tratar como inconsistencia si archivo existe
        if os.path.isfile(nueva_ruta):
            raise CopiarInconsistenciaError(
                f"error al dar de alta copia (archivo en {nueva_ruta!r} conservado): {exc}",
                ruta_nueva=nueva_ruta,
                error_db=str(exc),
            ) from exc
        raise CopiarError(f"fallo al dar de alta copia: {exc}") from exc
    finally:
        if conn2 is not None:
            try:
                conn2.close()
            except Exception:
                pass

    # B8.3A — réplica canónica por video_id (v<id>_01.jpg) sin regeneración FFmpeg.
    # Usa video_id origen y nuevo_id conocidos tras INSERT; no decide por nombre.
    # Copia no destructiva solo si destino no existe, con temporal+replace si aplica.
    # Si falla la réplica después de archivo+DB válidos, no destruir copia válida;
    # fallo queda visible via detalles pero ok=True se preserva (contrato CopiarInconsistencia histórico).
    # CERO fallback por nombre: si helper por ID no existe es error de programación reportado, nunca cache por nombre.
    mini_copiadas = 0
    preview_copiadas = 0
    cache_replica_detalle = None
    cache_fallos = 0
    try:
        import escanear_videos as esc_rep
        # resolución dinámica solo para permitir monkeypatch en tests; producción usa helper canónico por ID
        replicar = getattr(esc_rep, "replicar_cache_por_id", None) or getattr(esc_rep, "copiar_cache_entre_ids", None)
        if callable(replicar):
            res_cache = replicar(video_id, nuevo_id)
            if isinstance(res_cache, dict):
                cache_replica_detalle = res_cache
                mini_copiadas = int(res_cache.get("mini_copiadas", 0))
                preview_copiadas = int(res_cache.get("preview_copiadas", 0))
                cache_fallos = int(res_cache.get("fallos", 0))
                if cache_fallos:
                    try:
                        print(f"[B8.3A] copiar_video cache réplica fallos vid_origen={video_id} vid_dest={nuevo_id} detalle={res_cache}")
                    except Exception:
                        pass
            elif isinstance(res_cache, (list, tuple)) and len(res_cache) >= 2:
                mini_copiadas, preview_copiadas = int(res_cache[0]), int(res_cache[1])
                cache_replica_detalle = {"mini_copiadas": mini_copiadas, "preview_copiadas": preview_copiadas, "copiados": mini_copiadas + preview_copiadas, "fallos": 0, "detalles": []}
                cache_fallos = 0
            else:
                cache_replica_detalle = {"copiados": 0, "ya_existentes": 0, "fallos": 1, "detalles": [{"src": "", "dst": "", "estado": "helper_retorno_inesperado", "preview": False}], "mini_copiadas": 0, "preview_copiadas": 0}
                cache_fallos = 1
                try:
                    print(f"[B8.3A] copiar_video helper retorno inesperado vid_origen={video_id} vid_dest={nuevo_id} res={res_cache!r}")
                except Exception:
                    pass
        else:
            # B8.3A cierre: helper por ID no disponible -> fallo de réplica visible, NUNCA fallback por nombre
            cache_replica_detalle = {"copiados": 0, "ya_existentes": 0, "fallos": 1, "detalles": [{"src": "", "dst": "", "estado": "helper_no_disponible_error_programacion", "preview": False}], "mini_copiadas": 0, "preview_copiadas": 0}
            cache_fallos = 1
            try:
                print(f"[B8.3A] copiar_video helper replicar_cache_por_id no disponible vid_origen={video_id} vid_dest={nuevo_id} error_programacion")
            except Exception:
                pass
        if mini_copiadas > 0:
            try:
                import escanear_videos as escanear_mod2
                conn3 = escanear_mod2.conectar_bd(ruta_db)
                try:
                    conn3.execute("UPDATE videos SET cantidad_miniaturas = ? WHERE id = ?", (int(mini_copiadas), int(nuevo_id)))
                    conn3.commit()
                finally:
                    try:
                        conn3.close()
                    except Exception:
                        pass
            except Exception as exc_upd:
                # best-effort: fallo de actualización no destruye copia; reportar en detalle
                try:
                    print(f"[B8.3A] copiar_video fallo UPDATE cantidad_miniaturas vid={nuevo_id}: {exc_upd}")
                except Exception:
                    pass
                if isinstance(cache_replica_detalle, dict):
                    cache_replica_detalle.setdefault("detalles", []).append({"src": "", "dst": "", "estado": f"fallo_update_cantidad:{exc_upd}", "preview": False})
                    cache_replica_detalle["fallos"] = int(cache_replica_detalle.get("fallos", 0)) + 1
                    cache_fallos = int(cache_replica_detalle.get("fallos", 0))
    except Exception as exc:
        # réplica best-effort: no destruir copia válida ya publicada+DB; reportar visible y en resultado
        try:
            print(f"[B8.3A] copiar_video excepción réplica cache vid_origen={video_id} vid_dest={nuevo_id}: {type(exc).__name__}: {exc}")
        except Exception:
            pass
        if cache_replica_detalle is None:
            cache_replica_detalle = {"copiados": mini_copiadas + preview_copiadas, "ya_existentes": 0, "fallos": 1, "detalles": [{"src": "", "dst": "", "estado": f"excepcion:{type(exc).__name__}:{exc}", "preview": False}], "mini_copiadas": mini_copiadas, "preview_copiadas": preview_copiadas}
            cache_fallos = 1
        else:
            try:
                if isinstance(cache_replica_detalle, dict):
                    cache_replica_detalle.setdefault("detalles", []).append({"src": "", "dst": "", "estado": f"excepcion:{type(exc).__name__}:{exc}", "preview": False})
                    cache_replica_detalle["fallos"] = int(cache_replica_detalle.get("fallos", 0)) + 1
                    cache_fallos = int(cache_replica_detalle.get("fallos", 0))
            except Exception:
                pass

    # Garantizar detalle determinista aunque no haya cache origen (evitar None)
    if cache_replica_detalle is None:
        cache_replica_detalle = {"copiados": mini_copiadas + preview_copiadas, "ya_existentes": 0, "fallos": 0, "detalles": [], "mini_copiadas": mini_copiadas, "preview_copiadas": preview_copiadas}

    return {
        "ok": True,
        "video_id": nuevo_id,
        "nombre": nombre_final,
        "ruta": os.path.abspath(nueva_ruta),
        "carpeta_destino": os.path.abspath(carpeta_destino_abs),
        "carpeta_destino_normalizada": os.path.normcase(os.path.normpath(os.path.abspath(carpeta_destino_abs))),
        "video_id_original": video_id,
        "nombre_original": nombre_original,
        "ruta_original": ruta_actual_abs,
        "ruta_anterior": ruta_actual_abs,
        "nombre_final": nombre_final,
        "modo": "copia-temporal-verificada",
        "cache_replica": cache_replica_detalle,
        "cache_fallos": cache_fallos,
        "mini_copiadas": mini_copiadas,
        "preview_copiadas": preview_copiadas,
    }
