"""Servicio B7.1 — renombrado individual seguro de un video catalogado.

Contrato:
- Preserva video_id, marcadores, segmentos, colores, relaciones derivados.
- No reescanea; sí reasocia/renombra cache de miniaturas/previews existente
  (preservando archivos, sin regeneración) para que la primera miniatura
  y las previews sigan visibles tras reinicio sin Escanear carpeta.
- Validación conservadora Windows reutilizando nombres.py.
- Ejecución fuera del hilo UI vía TareaRenombrarVideo.
- Compensación obligatoria si SQLite falla tras rename FS (incluye cache).
"""

import os
import re
import sqlite3

import nombres as nombres_mod
import rutas as rutas_mod

from rutas import ruta_biblioteca


class RenombradoError(Exception):
    pass


class ValidacionError(RenombradoError):
    pass


class ColisionError(RenombradoError):
    pass


class CompensacionFalloError(RenombradoError):
    """Fallo crítico: FS y DB divergentes y la compensación también falló."""

    def __init__(self, mensaje, ruta_original, ruta_nueva, error_db, error_compensacion):
        super().__init__(mensaje)
        self.ruta_original = ruta_original
        self.ruta_nueva = ruta_nueva
        self.error_db = error_db
        self.error_compensacion = error_compensacion


def _validar_video_id(video_id):
    if isinstance(video_id, bool) or not isinstance(video_id, int):
        raise TypeError("video_id debe ser un entero")
    if video_id <= 0:
        raise ValueError("video_id debe ser un entero positivo")


def validar_nuevo_nombre(nuevo_nombre, nombre_actual):
    """Valida un nuevo nombre de archivo preservando extensión.

    - nuevo_nombre: texto ingresado por el usuario (con o sin extensión)
    - nombre_actual: nombre actual en DB (con extensión)

    Retorna el nombre completo validado (con extensión original preservada).

    Rechaza conservadoramente:
      vacío/ solo espacios, caracteres inválidos Windows,
      nombres reservados, trailing punto/espacio, longitud >255,
      extensión distinta.
    No sanitiza silenciosamente: si el nombre contiene caracteres
    inválidos se rechaza.
    """
    if not isinstance(nuevo_nombre, str):
        raise ValidacionError("nombre debe ser texto")
    if not isinstance(nombre_actual, str) or not nombre_actual:
        raise ValidacionError("nombre actual inválido")

    # Detectar trailing punto/espacio antes de strip: rechazo conservador
    # Si el usuario escribió trailing punto o espacio, es inválido Windows.
    if nuevo_nombre != nuevo_nombre.strip():
        # Permite leading/trailing spaces como error explícito si hay contenido?
        # Rechazar cualquier leading/trailing espacios
        raise ValidacionError("nombre no puede tener espacios al inicio o al final")
    if nuevo_nombre.endswith(" ") or nuevo_nombre.endswith("."):
        raise ValidacionError("nombre no puede terminar en punto o espacio")

    trimmed = nuevo_nombre.strip()
    if not trimmed:
        raise ValidacionError("nombre vacío")

    # Extensión original (preservar)
    ext_actual = os.path.splitext(nombre_actual)[1]
    if not ext_actual:
        raise ValidacionError("nombre actual sin extensión")
    ext_actual_norm = ext_actual.lower()

    # Separar nombre ingresado
    stem_input, ext_input = os.path.splitext(trimmed)

    # Si no hay extensión en el input, se completará con la original
    # Si hay extensión, debe coincidir con la original
    if ext_input:
        if ext_input.lower() != ext_actual_norm:
            raise ValidacionError(
                f"extensión no puede cambiarse (esperada {ext_actual!r}, recibida {ext_input!r})"
            )
        nombre_completo = trimmed
        stem = stem_input
        ext_final = ext_input
    else:
        # Sin extensión -> usar stem completo como nombre sin ext + ext original
        stem = trimmed
        ext_final = ext_actual
        nombre_completo = stem + ext_final

    if not stem:
        raise ValidacionError("nombre sin stem (solo extensión)")

    # Validar longitud total del componente (incluye extensión)
    if len(nombre_completo) > nombres_mod.MAX_COMPONENTE:
        raise ValidacionError(
            f"nombre demasiado largo ({len(nombre_completo)} > {nombres_mod.MAX_COMPONENTE})"
        )

    # Validar caracteres inválidos en el nombre completo (sin sanitizar)
    # Se valida todo el nombre_completo, no solo stem, para detectar
    # caracteres inválidos también en la extensión (ya validada arriba)
    for ch in nombre_completo:
        if ch in nombres_mod.CARACTERES_INVALIDOS or (0 <= ord(ch) <= 31):
            raise ValidacionError(f"nombre contiene carácter inválido {ch!r}")
    # Trailing punto/espacio ya verificado arriba, pero también rstrip check
    if nombre_completo.rstrip(" .") != nombre_completo:
        raise ValidacionError("nombre no puede terminar en punto o espacio")

    # Nombre reservado Windows (sobre el stem)
    if nombres_mod._es_reservado(stem):
        raise ValidacionError(f"nombre reservado Windows: {stem!r}")

    # Validar que sanitizar no cambie nada (detecta casos sutiles)
    # Si sanitizar_componente altera el nombre, había algo inválido no detectado
    # pero por seguridad lo rechazamos
    # Solo aplicamos sobre el nombre completo sin forzar prefijo reservado
    # ya que _es_reservado ya lo rechazó.
    # Comparamos stem: sanitizado debe ser idéntico
    # (sanitizar_componente reemplazaría inválidos por _, aquí ya rechazamos)
    # Esta verificación es defensiva.
    try:
        sanitizado = nombres_mod.sanitizar_componente(nombre_completo)
    except Exception as exc:
        raise ValidacionError(str(exc)) from exc
    if sanitizado != nombre_completo:
        # Si difiere solo por prefijo "_" de reservado ya lo manejamos,
        # pero aquí ya rechazamos reservados, así que cualquier diferencia es error
        raise ValidacionError("nombre contiene forma no permitida Windows")

    # No permitir nombre idéntico al actual (case-insensitive?)
    # Se considera colisión/operación innecesaria: se rechaza como validación
    if nombre_completo.lower() == nombre_actual.lower():
        # Si es exactamente igual (mismo case) también es no-op; lo tratamos como error
        # para evitar rename innecesario. El caller puede decidir ignorar.
        # Pero si difiere solo en case, en Windows es el mismo archivo; también rechazar.
        raise ValidacionError("el nuevo nombre es idéntico al actual")

    return nombre_completo


def _nombre_seguro_b71(nombre):
    """Replica escanear_videos._nombre_seguro para cache (sin ciclo)."""
    return nombre.replace(os.sep, "_").replace("/", "_")


def _calcular_renombres_cache(nombre_actual, nombre_nuevo, carpeta_mini=None):
    """Lista de (src, dst) para cache miniaturas/previews de un video.

    Solo mueve archivos cuyo sufijo tras el prefijo sea _<digits> o
    _preview_<digits> (evita mover colisiones de prefijo como video vs
    video_realista). No toca exploración (video_id).
    """
    if carpeta_mini is None:
        try:
            carpeta_mini = rutas_mod.ruta_carpeta_miniaturas()
        except Exception:
            return []
    if not isinstance(carpeta_mini, str) or not carpeta_mini:
        return []
    if not os.path.isdir(carpeta_mini):
        return []
    prefijo_old = _nombre_seguro_b71(os.path.splitext(nombre_actual)[0])
    prefijo_new = _nombre_seguro_b71(os.path.splitext(nombre_nuevo)[0])
    if prefijo_old == prefijo_new:
        return []
    renombres = []
    try:
        archivos = os.listdir(carpeta_mini)
    except OSError:
        return []
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
                if src != dst:
                    renombres.append((src, dst))
            continue
        if base.startswith(prefijo_old + "_"):
            suffix = base[len(prefijo_old):]  # _NN
            rest = suffix[1:]  # sin _
            if rest.isdigit():
                new_name = prefijo_new + suffix + ext
                src = os.path.join(carpeta_mini, fname)
                dst = os.path.join(carpeta_mini, new_name)
                if src != dst:
                    renombres.append((src, dst))
    return renombres


def _obtener_video_por_id(conn, video_id):
    fila = conn.execute(
        "SELECT id, nombre, ruta FROM videos WHERE id = ?", (video_id,)
    ).fetchone()
    if fila is None:
        return None
    return {"id": fila[0], "nombre": fila[1], "ruta": fila[2]}


def renombrar_video(video_id, nuevo_nombre, ruta_db=None):
    """Renombra un video catalogado de forma segura (B7.1).

    Secuencia:
      1. Validar video_id y nuevo_nombre (preservando extensión).
      2. Cargar registro actual.
      3. Prevalidar colisión FS (os.path.exists) y UNIQUE(nombre) en DB antes de tocar FS.
      4. os.rename en filesystem.
      5. UPDATE en SQLite (transacción corta).
      6. Si SQLite falla tras rename FS, compensar con rename inverso.

    Retorna dict:
      {ok: bool, video_id, nombre, ruta, nombre_anterior, ruta_anterior, error, compensacion_fallo}

    No lanza CompensacionFalloError silenciosamente: lo encapsula en el dict
    con ok=False y compensacion_fallo=True para que la tarea lo propague via error.
    Para uso directo (tests/servicio), lanza excepciones tipadas.
    """
    _validar_video_id(video_id)
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")

    # Cargar registro
    conn0 = sqlite3.connect(ruta_db)
    try:
        # Asegurar tablas existen
        try:
            from escanear_videos import _asegurar_columnas_videos, _asegurar_tablas_derivados, _asegurar_tabla_marcadores, _asegurar_tabla_segmentos
            # conectar_bd ya asegura, pero aquí solo garantizar videos existe
            conn0.execute("SELECT 1 FROM videos LIMIT 1")
        except sqlite3.OperationalError as exc:
            raise RenombradoError(f"tabla videos no disponible: {exc}") from exc

        video = _obtener_video_por_id(conn0, video_id)
        if video is None:
            raise ValidacionError(f"video_id {video_id} no existe")
        nombre_actual = video["nombre"]
        ruta_actual = video["ruta"]
    finally:
        conn0.close()

    # Validar nuevo nombre preservando extensión
    nombre_nuevo = validar_nuevo_nombre(nuevo_nombre, nombre_actual)

    # Construir nueva ruta (mismo directorio que la actual)
    directorio = os.path.dirname(os.path.abspath(ruta_actual))
    # Si ruta_actual no tiene directorio (relativa), usar dirname de ruta_actual
    if not directorio or directorio == os.path.abspath(ruta_actual):
        directorio = os.path.dirname(ruta_actual) or "."
    nueva_ruta = os.path.join(directorio, nombre_nuevo)
    # Normalizar a absoluta si la original era absoluta
    if os.path.isabs(ruta_actual):
        nueva_ruta = os.path.abspath(nueva_ruta)
        ruta_actual_abs = os.path.abspath(ruta_actual)
    else:
        ruta_actual_abs = ruta_actual
        # nueva_ruta ya es join relativo; mantener coherencia
        if os.path.isabs(nueva_ruta) and not os.path.isabs(ruta_actual):
            # Si original era relativa, mantener relativa
            nueva_ruta = os.path.join(os.path.dirname(ruta_actual), nombre_nuevo)

    # Prevalidaciones antes de tocar FS
    # 1) FS colisión: no sobrescribir
    if os.path.exists(nueva_ruta):
        # En Windows normcase para evitar colisión case-insensitive
        try:
            if os.path.normcase(os.path.normpath(nueva_ruta)) != os.path.normcase(os.path.normpath(ruta_actual_abs)):
                raise ColisionError(f"ya existe un archivo en destino: {nueva_ruta!r}")
            else:
                # Es el mismo archivo (mismo path normalizado) — ya validado como idéntico
                raise ValidacionError("el nuevo nombre es idéntico al actual")
        except ColisionError:
            raise
        except ValidacionError:
            raise
        # Si es el mismo archivo exacto, ya se rechazó arriba
        raise ColisionError(f"ya existe un archivo en destino: {nueva_ruta!r}")

    # 2) DB UNIQUE(nombre) colisión
    conn_chk = sqlite3.connect(ruta_db)
    try:
        fila_dup = conn_chk.execute(
            "SELECT id FROM videos WHERE nombre = ? AND id != ?", (nombre_nuevo, video_id)
        ).fetchone()
        if fila_dup is not None:
            raise ColisionError(
                f"ya existe otro video con nombre {nombre_nuevo!r} (id {fila_dup[0]})"
            )
        # También verificar si el archivo origen existe
        if not os.path.isfile(ruta_actual_abs):
            # Si la ruta en DB es absoluta y existe check con esa ruta
            # Si no existe, aún podemos intentar rename pero fallará; reportar antes
            if not os.path.isfile(ruta_actual):
                raise RenombradoError(f"archivo origen no encontrado: {ruta_actual!r}")
    finally:
        conn_chk.close()

    # 2b) Cache destino colisión (no sobrescribir miniaturas/previews existentes con nuevo prefijo)
    renombres_cache = _calcular_renombres_cache(nombre_actual, nombre_nuevo)
    for _src, _dst in renombres_cache:
        if os.path.exists(_dst):
            # Si el destino ya existe (colisión), tratamos como error conservador antes de tocar FS
            # No sobrescribir: el rename se aborta sin tocar FS
            if os.path.normcase(os.path.normpath(_dst)) != os.path.normcase(os.path.normpath(_src)):
                raise ColisionError(f"colisión en cache destino ya existe: {_dst!r}")
            # si es mismo archivo (no debería), ignorar

    # 3) FS rename (video)
    try:
        os.rename(ruta_actual_abs if os.path.isabs(ruta_actual_abs) and os.path.isfile(ruta_actual_abs) else ruta_actual, nueva_ruta)
    except OSError as exc:
        # DB intacta
        raise RenombradoError(f"fallo al renombrar en filesystem: {exc}") from exc

    # 3b) Renombrado de cache (preservar miniaturas/previews sin regenerar)
    cache_renombrados = []  # para compensación
    try:
        for src, dst in renombres_cache:
            # Si src ya no existe (carrera), saltar
            if not os.path.isfile(src):
                continue
            # Si dst ya existe, ya fallamos arriba, pero por seguridad skip
            if os.path.exists(dst):
                continue
            os.rename(src, dst)
            cache_renombrados.append((src, dst))
    except OSError as exc:
        # Fallo al renombrar cache tras mover video: compensar video + cache ya movidos
        # Revertir cache ya movidos
        for s, d in reversed(cache_renombrados):
            try:
                if os.path.isfile(d) and not os.path.exists(s):
                    os.rename(d, s)
            except OSError:
                pass
        # Revertir video
        try:
            os.rename(nueva_ruta, ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual)
        except OSError as exc_comp:
            raise CompensacionFalloError(
                f"fallo al renombrar cache tras rename video y la compensación de video también falló: {exc} | compensación: {exc_comp}",
                ruta_original=ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual,
                ruta_nueva=nueva_ruta,
                error_db=str(exc),
                error_compensacion=str(exc_comp),
            ) from exc_comp
        raise RenombradoError(f"fallo al renombrar cache de miniaturas: {exc}") from exc

    # Para el caso donde ruta_actual era relativa y renombramos con ruta_abs,
    # determinar cuál es la ruta real usada
    # Si usamos ruta_actual_abs, el filesystem ya movió ese archivo.
    # La nueva_ruta es la que corresponde.

    # 4) Persistencia DB (transacción corta)
    conn = sqlite3.connect(ruta_db)
    try:
        conn.execute("BEGIN")
        # Verificar nuevamente UNIQUE dentro de la transacción (carrera)
        fila_dup2 = conn.execute(
            "SELECT id FROM videos WHERE nombre = ? AND id != ?", (nombre_nuevo, video_id)
        ).fetchone()
        if fila_dup2 is not None:
            conn.rollback()
            # Compensación: restaurar cache y FS
            for s, d in reversed(cache_renombrados):
                try:
                    if os.path.isfile(d) and not os.path.exists(s):
                        os.rename(d, s)
                except OSError:
                    pass
            try:
                os.rename(nueva_ruta, ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual)
            except OSError as exc_comp:
                raise CompensacionFalloError(
                    f"fallo SQLite (colisión) y la compensación también falló: {exc_comp}",
                    ruta_original=ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual,
                    ruta_nueva=nueva_ruta,
                    error_db=f"colisión UNIQUE nombre {nombre_nuevo!r}",
                    error_compensacion=str(exc_comp),
                ) from exc_comp
            raise ColisionError(f"ya existe otro video con nombre {nombre_nuevo!r} (carrera)")

        cur = conn.execute(
            "UPDATE videos SET nombre = ?, ruta = ? WHERE id = ?",
            (nombre_nuevo, nueva_ruta, video_id),
        )
        if cur.rowcount == 0:
            conn.rollback()
            # Compensación: restaurar cache y FS
            for s, d in reversed(cache_renombrados):
                try:
                    if os.path.isfile(d) and not os.path.exists(s):
                        os.rename(d, s)
                except OSError:
                    pass
            try:
                os.rename(nueva_ruta, ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual)
            except OSError as exc_comp:
                raise CompensacionFalloError(
                    f"video_id {video_id} no encontrado en DB tras rename FS y compensación falló",
                    ruta_original=ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual,
                    ruta_nueva=nueva_ruta,
                    error_db="UPDATE rowcount 0",
                    error_compensacion=str(exc_comp),
                ) from exc_comp
            raise RenombradoError(f"video_id {video_id} no encontrado para actualizar")

        # Verificar que la fila quedó correcta
        conn.commit()
    except (sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        # Compensación obligatoria: restaurar cache y FS
        for s, d in reversed(cache_renombrados):
            try:
                if os.path.isfile(d) and not os.path.exists(s):
                    os.rename(d, s)
            except OSError:
                pass
        try:
            os.rename(nueva_ruta, ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual)
        except OSError as exc_comp:
            raise CompensacionFalloError(
                f"fallo SQLite tras rename FS y la compensación también falló: {exc} | compensación: {exc_comp}",
                ruta_original=ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual,
                ruta_nueva=nueva_ruta,
                error_db=str(exc),
                error_compensacion=str(exc_comp),
            ) from exc_comp
        raise RenombradoError(f"fallo al persistir renombrado en DB (FS restaurado): {exc}") from exc
    except RenombradoError:
        # Ya manejado colisión carrera con compensación
        raise
    except CompensacionFalloError:
        raise
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        # Intentar compensar cache y FS para cualquier otro error
        for s, d in reversed(cache_renombrados):
            try:
                if os.path.isfile(d) and not os.path.exists(s):
                    os.rename(d, s)
            except OSError:
                pass
        try:
            os.rename(nueva_ruta, ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual)
        except OSError as exc_comp:
            raise CompensacionFalloError(
                f"fallo inesperado tras rename FS y compensación falló: {exc} | compensación: {exc_comp}",
                ruta_original=ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual,
                ruta_nueva=nueva_ruta,
                error_db=str(exc),
                error_compensacion=str(exc_comp),
            ) from exc_comp
        raise RenombradoError(f"fallo inesperado al renombrar: {exc}") from exc
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return {
        "ok": True,
        "video_id": video_id,
        "nombre": nombre_nuevo,
        "ruta": nueva_ruta,
        "nombre_anterior": nombre_actual,
        "ruta_anterior": ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual,
        "error": None,
    }
