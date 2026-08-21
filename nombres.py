"""Motor general y reutilizable de nombres B6.8.

Diseño B6.8 — componente puro/testeable separado de UI/SQLite/FFmpeg/PySide6.
Plantillas con tokens cerrados y validados; nada de eval/format arbitrario.
Extensión separada y controlada. Colisiones resueltas sin sobrescritura.

Tokens soportados:
  {original}         -> nombre sin última extensión, preserva puntos internos
  {numero} / {numero:03d} -> número con padding seguro limitado (solo 0Nd)
  {fecha} / {fecha:YYYY-MM-DD} -> fecha estable YYYYMMDD por defecto
  {texto}            -> texto personalizado sanitizado
  {inicio} / {fin}   -> tiempos con dos decimales estables (igual B6.7)

Plantilla default exportación individual B6.7:
  "{original}_segmento_{inicio}-{fin}" + extensión ".mp4"

Sanitización Windows:
  - reemplaza <>:"/\\|?* y controles U+0000..U+001F por "_"
  - nombres reservados CON/PRN/AUX/NUL/COM1..9/LPT1..9 (case-insensitive,
    incluso con extensión) -> prefija "_"
  - elimina puntos y espacios finales (rstrip " .")
  - componentes vacíos/solo inválidos -> error
  - preserva Unicode/acentos, no translitera, no colapsa espacios internos
  - longitud máxima de componente Windows 255; valida explícitamente,
    reserva espacio para extensión y sufijo _001; si excede -> error

Colisiones:
  - sufijo determinístico _001, _002 ...
  - considera simultáneamente existe_fn(candidato) y conjunto de lote
    normalizado case-insensitive
  - sin creación de archivos, sin reemplazo atomico destructivo ni flag -y

Errores de dominio estructurados para distinguir casos B6.9/B6.10.
"""

import datetime
import math
import os
import re

# ——— Constantes ———

# Límite de componente Windows NTFS (docs Microsoft: 255 caracteres por
# componente). Se deriva de la especificación del filesystem, no es
# arbitrario. Se reserva explícitamente espacio para extensión y sufijo.
MAX_COMPONENTE = 255

EXTENSIONES_VALIDAS_DEFAULT = {".mp4", ".mkv"}

RESERVADOS = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

CARACTERES_INVALIDOS = set('<>:"/\\|?*')

PLANTILLA_DEFAULT_B67 = "{original}_segmento_{inicio}-{fin}"

TOKENS_VALIDOS = {"original", "numero", "fecha", "texto", "inicio", "fin"}

FORMATOS_FECHA_PERMITIDOS = {
    None,  # default YYYYMMDD
    "YYYYMMDD",
    "YYYY-MM-DD",
    "DDMMYYYY",
    "DD-MM-YYYY",
}

# ——— Excepciones de dominio ———

class NombresError(Exception):
    pass

class PlantillaInvalidaError(NombresError):
    pass

class TokenDesconocidoError(NombresError):
    pass

class FormatoInvalidoError(NombresError):
    pass

class ContextoFaltanteError(NombresError):
    pass

class ExtensionInvalidaError(NombresError):
    pass

class NombreVacioError(NombresError):
    pass

class ColisionNoResolubleError(NombresError):
    pass

# ——— Sanitización ———

def _es_reservado(stem):
    """True si el stem (sin extensión) es reservado Windows.
    Considera case-insensitive y stem antes del primer punto con extensión.
    """
    if not isinstance(stem, str) or not stem:
        return False
    # stem antes del primer punto (CON.txt -> CON)
    base = stem.split(".")[0]
    return base.upper() in RESERVADOS


def sanitizar_componente(nombre):
    """Sanitiza un componente de nombre Windows y valida.

    - reemplaza caracteres <>:"/\\|?* y controles U+0000..U+001F por "_"
    - elimina puntos y espacios finales
    - prefija "_" si es reservado
    - preserva Unicode, no colapsa espacios internos
    - vacío tras sanitización -> NombreVacioError
    """
    if not isinstance(nombre, str):
        raise NombreVacioError("nombre debe ser texto")
    # reemplazo de inválidos y controles
    resultado = []
    for ch in nombre:
        if ch in CARACTERES_INVALIDOS or (0 <= ord(ch) <= 31):
            resultado.append("_")
        else:
            resultado.append(ch)
    s = "".join(resultado)
    # eliminar puntos y espacios finales (Windows no permite)
    s = s.rstrip(" .")
    if not s:
        raise NombreVacioError("nombre vacío tras sanitización (solo inválidos/espacios/puntos)")
    # nombres reservados -> prefijar "_"
    # considerar stem antes del primer punto; también el nombre completo sin extensión
    if _es_reservado(s):
        s = "_" + s
        # re-validar no vacío después de prefijo
        if not s.rstrip(" ."):
            raise NombreVacioError("nombre reservado vacío tras ajuste")
    # validar que no quedaron caracteres inválidos (por seguridad)
    # (ya reemplazados)
    # No truncado silencioso; la longitud se valida en capas superiores
    return s


def sanitizar_texto_personalizado(texto):
    """Sanitiza texto personalizado y valida no vacío."""
    if not isinstance(texto, str):
        raise NombreVacioError("texto debe ser cadena")
    # recortar espacios de borde para texto? Preservamos internos, pero
    # el texto personalizado se sanitiza igual que componente
    s = sanitizar_componente(texto)
    return s

# ——— Extensión ———

def normalizar_extension(extension):
    """Normaliza extensión a forma '.mp4' minúscula.

    Acepta con o sin punto inicial, con mayúsculas. Devuelve forma
    normalizada con punto.
    """
    if not isinstance(extension, str) or not extension.strip():
        raise ExtensionInvalidaError("extensión vacía")
    ext = extension.strip()
    if not ext.startswith("."):
        ext = "." + ext
    ext = ext.lower()
    # validar caracteres: solo alfanuméricos después del punto
    if not re.match(r"^\.[a-z0-9]+$", ext):
        raise ExtensionInvalidaError(f"extensión con caracteres inválidos: {extension!r}")
    return ext


def validar_extension(extension, permitidas=None):
    """Valida que la extensión esté en el conjunto permitido."""
    if permitidas is None:
        permitidas = EXTENSIONES_VALIDAS_DEFAULT
    ext = normalizar_extension(extension)
    # comparación case-insensitive ya normalizada
    permitidas_norm = {normalizar_extension(e) for e in permitidas}
    if ext not in permitidas_norm:
        raise ExtensionInvalidaError(f"extensión no permitida {ext!r} (permitidas: {sorted(permitidas_norm)})")
    return ext


def asegurar_extension(ruta, extensiones_validas=None, default=".mp4"):
    """Asegura que ruta tenga extensión válida; si no tiene, agrega default.

    - Sin extensión -> agrega default validado.
    - Con extensión permitida -> normaliza a minúsculas.
    - Con extensión explícita no permitida -> lanza ExtensionInvalidaError
      (no oculta agregando otra extensión).
    Usa validación estricta sin sanitizar el resto de la ruta.
    """
    if not isinstance(ruta, str) or not ruta.strip():
        raise NombreVacioError("ruta vacía")
    if extensiones_validas is None:
        extensiones_validas = EXTENSIONES_VALIDAS_DEFAULT
    ext_actual = os.path.splitext(ruta)[1]
    if not ext_actual:
        # sin extensión -> agregar default
        default_norm = validar_extension(default, extensiones_validas)
        return ruta + default_norm
    # con extensión explícita -> validar estrictamente, rechazar si no permitida
    ext_norm = validar_extension(ext_actual, extensiones_validas)
    base = ruta[: -len(ext_actual)] if ext_actual else ruta
    return base + ext_norm

# ——— Plantilla ———

_RE_TOKEN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([^}]*))?\}")

def _validar_formato_numero(fmt):
    if fmt is None:
        return None
    # formato seguro limitado: solo 0Nd donde N 1..4 (ej 03d, 02d, 4d)
    # Permitimos: "02d", "03d", "04d", "2d" etc. No permitimos formatos arbitrarios Python.
    if not re.match(r"^0?[1-9]\d{0,2}d$", fmt):
        raise FormatoInvalidoError(f"formato de numero inválido {fmt!r} (esperado ej '03d')")
    # extraer width
    m = re.match(r"^0?(\d+)d$", fmt)
    width = int(m.group(1))
    if width < 1 or width > 5:
        raise FormatoInvalidoError(f"ancho de numero fuera de rango {fmt!r}")
    return fmt


def _formatear_numero(valor, fmt):
    if not isinstance(valor, int) or isinstance(valor, bool):
        raise ContextoFaltanteError(f"numero debe ser entero, got {valor!r}")
    if valor < 0:
        raise ContextoFaltanteError("numero no puede ser negativo")
    if fmt is None:
        return str(valor)
    # fmt validado, ej "03d" -> width 3
    width = int(re.match(r"^0?(\d+)d$", fmt).group(1))
    # usar padding 0
    return f"{valor:0{width}d}"


def _validar_y_formatear_fecha(contexto_fecha, fmt, fecha_hoy=None):
    # contexto_fecha puede ser None, date, datetime, o string YYYYMMDD
    if fmt not in FORMATOS_FECHA_PERMITIDOS:
        raise FormatoInvalidoError(f"formato de fecha no permitido {fmt!r} (permitidos: YYYYMMDD, YYYY-MM-DD, DDMMYYYY, DD-MM-YYYY)")
    # resolver fecha
    fecha = contexto_fecha
    if fecha is None:
        if fecha_hoy is not None:
            fecha = fecha_hoy
        else:
            fecha = datetime.date.today()
    # si es string, intentar parsear YYYYMMDD
    if isinstance(fecha, str):
        s = fecha.strip()
        # aceptar YYYYMMDD o YYYY-MM-DD
        try:
            if re.match(r"^\d{8}$", s):
                fecha = datetime.datetime.strptime(s, "%Y%m%d").date()
            elif re.match(r"^\d{4}-\d{2}-\d{2}$", s):
                fecha = datetime.datetime.strptime(s, "%Y-%m-%d").date()
            else:
                raise ContextoFaltanteError(f"fecha string con formato no reconocido {fecha!r}")
        except ValueError as exc:
            raise ContextoFaltanteError(f"fecha inválida {fecha!r}: {exc}")
    elif isinstance(fecha, datetime.datetime):
        fecha = fecha.date()
    elif isinstance(fecha, datetime.date):
        pass
    else:
        raise ContextoFaltanteError(f"fecha debe ser date/datetime o string YYYYMMDD, got {type(fecha)}")
    # formatear según fmt
    if fmt is None or fmt == "YYYYMMDD":
        return fecha.strftime("%Y%m%d")
    elif fmt == "YYYY-MM-DD":
        return fecha.strftime("%Y-%m-%d")
    elif fmt == "DDMMYYYY":
        return fecha.strftime("%d%m%Y")
    elif fmt == "DD-MM-YYYY":
        return fecha.strftime("%d-%m-%Y")
    else:
        raise FormatoInvalidoError(f"formato fecha no soportado {fmt!r}")


def _validar_plantilla(plantilla):
    if not isinstance(plantilla, str):
        raise PlantillaInvalidaError("plantilla debe ser texto")
    if not plantilla:
        raise PlantillaInvalidaError("plantilla vacía")
    # detectar llaves desbalanceadas: contar sin regex
    # Buscar tokens con regex; luego verificar que no queden llaves sueltas
    tokens = list(_RE_TOKEN.finditer(plantilla))
    # construir string sin tokens y ver si queda { o }
    sin_tokens = _RE_TOKEN.sub("", plantilla)
    if "{" in sin_tokens or "}" in sin_tokens:
        raise PlantillaInvalidaError(f"plantilla mal formada (llaves sueltas): {plantilla!r}")
    # verificar cada token conocido y formato
    for m in tokens:
        nombre = m.group(1)
        fmt = m.group(2)  # puede ser None
        if nombre not in TOKENS_VALIDOS:
            raise TokenDesconocidoError(f"token desconocido {{{nombre}}} (permitidos: {sorted(TOKENS_VALIDOS)})")
        # validar formatos por token
        if nombre == "original":
            if fmt is not None:
                raise FormatoInvalidoError(f"token {{original}} no admite formato {fmt!r}")
        elif nombre == "numero":
            _validar_formato_numero(fmt)
        elif nombre == "fecha":
            if fmt not in FORMATOS_FECHA_PERMITIDOS and fmt is not None:
                # intentar validar como formato fecha permitido
                raise FormatoInvalidoError(f"formato de fecha no permitido {fmt!r}")
            # también validar que fmt sea uno de los permitidos si no es None
            if fmt is not None and fmt not in FORMATOS_FECHA_PERMITIDOS:
                raise FormatoInvalidoError(f"formato fecha no permitido {fmt!r}")
        elif nombre == "texto":
            if fmt is not None:
                raise FormatoInvalidoError(f"token {{texto}} no admite formato {fmt!r}")
        elif nombre in ("inicio", "fin"):
            if fmt is not None:
                raise FormatoInvalidoError(f"token {{{nombre}}} no admite formato arbitrario {fmt!r} (default dos decimales)")


def renderizar_plantilla(plantilla, contexto, fecha_hoy=None):
    """Renderiza plantilla a stem sanitizado (sin extensión).

    contexto: dict con claves opcionales según tokens usados:
      original: str (nombre de archivo con o sin ruta)
      numero: int
      fecha: date/datetime/str o None (usa fecha_hoy o today)
      texto: str
      inicio, fin: números (float/int) finitos

    fecha_hoy: date para determinismo en tests; si None usa today.

    Sanitiza el resultado completo (Windows). Lanza excepciones de dominio.
    """
    _validar_plantilla(plantilla)
    if not isinstance(contexto, dict):
        raise ContextoFaltanteError("contexto debe ser dict")

    def _reemplazo(match):
        nombre = match.group(1)
        fmt = match.group(2)
        if nombre == "original":
            val = contexto.get("original")
            if val is None:
                raise ContextoFaltanteError("contexto requiere 'original' para plantilla con {original}")
            if not isinstance(val, str) or not val.strip():
                raise ContextoFaltanteError("original debe ser texto no vacío")
            # quitar última extensión, preservando puntos internos.
            # No usar os.path.basename para no interpretar '/' o '\' como
            # separador de directorio cuando el carácter es parte del nombre
            # inválido a sanitizar (ej "a<b>c:d\"e/f\\g|h?i*j.mp4").
            # El caller (B6.7) pasa solo el nombre de archivo, no una ruta
            # completa; si se pasa una ruta, se toma tal cual y la
            # sanitización reemplazará los separadores.
            base = val
            stem, _ext = os.path.splitext(base)
            # si el basename es solo extensión? splitext maneja
            if not stem:
                # caso ".mp4" -> stem vacío, usar base sin punto?
                stem = base
                # quitar extensión si existe?
                if stem.startswith("."):
                    stem = stem[1:]
            # stem puede contener caracteres inválidos, se sanitizará después a nivel global
            # pero preservamos puntos internos tal cual
            return stem
        elif nombre == "numero":
            if "numero" not in contexto:
                raise ContextoFaltanteError("contexto requiere 'numero' para plantilla con {numero}")
            return _formatear_numero(contexto["numero"], fmt)
        elif nombre == "fecha":
            # fecha puede estar ausente -> usa fecha_hoy/today
            val = contexto.get("fecha", fecha_hoy if fecha_hoy is not None else None)
            # si contexto tiene fecha explícita, usarla; si no, pasar fecha_hoy
            # Para determinismo, si fecha_hoy se pasa y contexto no tiene fecha, usar fecha_hoy
            if "fecha" not in contexto and fecha_hoy is not None:
                val = fecha_hoy
            return _validar_y_formatear_fecha(val, fmt, fecha_hoy=fecha_hoy)
        elif nombre == "texto":
            if "texto" not in contexto:
                raise ContextoFaltanteError("contexto requiere 'texto' para plantilla con {texto}")
            txt = contexto["texto"]
            if not isinstance(txt, str):
                raise ContextoFaltanteError("texto debe ser cadena")
            # sanitizar texto individual antes de insertar? luego sanitización global también
            # preservamos pero si texto vacío tras strip?
            txt_s = txt.strip()
            if not txt_s:
                raise NombreVacioError("texto personalizado vacío")
            # sanitizar caracteres inválidos dentro del texto
            # usamos sanitizar pero permitiendo que luego global vuelva a sanitizar
            # para evitar doble prefijo de reservados, sanitizamos simple reemplazo
            tmp = []
            for ch in txt_s:
                if ch in CARACTERES_INVALIDOS or (0 <= ord(ch) <= 31):
                    tmp.append("_")
                else:
                    tmp.append(ch)
            txt_sanit = "".join(tmp).rstrip(" .")
            if not txt_sanit:
                raise NombreVacioError("texto vacío tras sanitización")
            return txt_sanit
        elif nombre == "inicio":
            if "inicio" not in contexto:
                raise ContextoFaltanteError("contexto requiere 'inicio' para plantilla con {inicio}")
            v = contexto["inicio"]
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ContextoFaltanteError(f"inicio debe ser número finito, got {v!r}")
            if not math.isfinite(float(v)):
                raise ContextoFaltanteError("inicio debe ser finito")
            if float(v) < 0:
                raise ContextoFaltanteError("inicio no puede ser negativo")
            return f"{float(v):.2f}"
        elif nombre == "fin":
            if "fin" not in contexto:
                raise ContextoFaltanteError("contexto requiere 'fin' para plantilla con {fin}")
            v = contexto["fin"]
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ContextoFaltanteError(f"fin debe ser número finito, got {v!r}")
            if not math.isfinite(float(v)):
                raise ContextoFaltanteError("fin debe ser finito")
            if float(v) < 0:
                raise ContextoFaltanteError("fin no puede ser negativo")
            return f"{float(v):.2f}"
        else:
            raise TokenDesconocidoError(f"token no soportado {nombre!r}")

    # Reemplazo
    try:
        intermedio = _RE_TOKEN.sub(_reemplazo, plantilla)
    except NombresError:
        raise
    except Exception as exc:
        raise PlantillaInvalidaError(f"error al renderizar plantilla: {exc}") from exc

    # Sanitización global del stem resultante
    # El intermedio puede contener caracteres inválidos provenientes de original/texto
    sanitizado = sanitizar_componente(intermedio)

    # Validación de longitud: stem + extensión se valida en capa superior;
    # aquí validamos que stem solo no exceda MAX_COMPONENTE (sin extensión)
    # y que no quede vacío (ya validado)
    if len(sanitizado) > MAX_COMPONENTE:
        raise NombreVacioError(f"nombre demasiado largo ({len(sanitizado)} > {MAX_COMPONENTE})")

    return sanitizado


def validar_longitud_final(nombre_completo):
    """Valida que el nombre completo (con extensión) no exceda MAX_COMPONENTE."""
    if not isinstance(nombre_completo, str):
        raise NombreVacioError("nombre debe ser texto")
    if len(nombre_completo) > MAX_COMPONENTE:
        raise NombreVacioError(f"nombre completo excede límite de componente Windows {MAX_COMPONENTE} ({len(nombre_completo)}): {nombre_completo!r}")
    if len(nombre_completo) == 0:
        raise NombreVacioError("nombre vacío")


def resolver_colision(stem, extension, existe_fn=None, nombres_en_lote=None):
    """Resuelve colisión determinísticamente con sufijo _001, _002...

    stem: ya sanitizado sin extensión
    extension: con punto, ya normalizada
    existe_fn: callable(nombre_completo) -> bool
    nombres_en_lote: iterable de nombres completos ya asignados en el lote

    Retorna nombre completo único. No crea archivos.
    """
    ext = normalizar_extension(extension)
    # validar stem ya sanitizado
    stem_s = sanitizar_componente(stem)
    # validar longitud base
    validar_longitud_final(stem_s + ext)

    if existe_fn is None:
        def existe_fn(_):
            return False
    if nombres_en_lote is None:
        lote_set = set()
    else:
        lote_set = {str(n).lower() for n in nombres_en_lote}

    # reservar espacio para sufijo: sufijo máximo "_999" len 4
    # si stem + ext ya está al límite, debemos validar que con sufijo no exceda
    base = stem_s + ext
    if base.lower() not in lote_set and not existe_fn(base):
        return base

    for i in range(1, 1000):
        sufijo = f"_{i:03d}"
        # validar que stem + sufijo + ext no exceda límite
        # si excede, truncar stem de forma controlada? Preferimos error explícito
        # según spec: reservar espacio; si no puede hacerse correctamente, rechazar
        # Aquí calculamos longitud; si excede, lanzamos error en lugar de truncar silencioso
        candidato_stem = stem_s + sufijo
        candidato = candidato_stem + ext
        if len(candidato) > MAX_COMPONENTE:
            # intentar truncar stem para que entre? Según spec no truncar silenciosamente
            # si stem original muy largo, informar error de longitud
            raise NombreVacioError(f"nombre con sufijo excede límite {MAX_COMPONENTE}: {candidato!r} (stem {len(stem_s)} + sufijo + ext)")
        if candidato.lower() not in lote_set and not existe_fn(candidato):
            return candidato
    raise ColisionNoResolubleError("no se pudo resolver colisión tras 999 intentos")


def generar_nombre(plantilla, contexto, extension, fecha_hoy=None):
    """Genera nombre completo (stem sanitizado + extensión) sin resolver colisión.

    Lanza excepciones de dominio. No verifica existencia.
    """
    ext = validar_extension(extension)
    stem = renderizar_plantilla(plantilla, contexto, fecha_hoy=fecha_hoy)
    completo = stem + ext
    validar_longitud_final(completo)
    return completo


def generar_nombre_unico(plantilla, contexto, extension, existe_fn=None, nombres_en_lote=None, fecha_hoy=None):
    """Genera nombre único considerando colisiones FS y de lote."""
    ext = validar_extension(extension)
    stem = renderizar_plantilla(plantilla, contexto, fecha_hoy=fecha_hoy)
    return resolver_colision(stem, ext, existe_fn=existe_fn, nombres_en_lote=nombres_en_lote)


def generar_sugerencia_exportacion(nombre_original, inicio, fin, extension=".mp4", numero=None, texto=None, fecha_hoy=None):
    """Helper puro para B6.7: genera sugerencia inicial de exportación.

    Reproduce sustancialmente el nombre vigente:
      {original}_segmento_{inicio}-{fin} + extensión

    Sanitiza Windows, valida extensión, sin colisión (la colisión se
    resuelve en el caller si lo desea con existe_fn).
    """
    ctx = {
        "original": nombre_original,
        "inicio": inicio,
        "fin": fin,
    }
    # numero/texto/fecha opcionales para extensibilidad B6.9, no usados en default
    if numero is not None:
        ctx["numero"] = numero
    if texto is not None:
        ctx["texto"] = texto
    # plantilla default B6.7
    plantilla = PLANTILLA_DEFAULT_B67
    return generar_nombre(plantilla, ctx, extension, fecha_hoy=fecha_hoy)


def generar_sugerencia_exportacion_unica(nombre_original, inicio, fin, extension=".mp4", existe_fn=None, nombres_en_lote=None):
    """Variante que resuelve colisión determinísticamente."""
    ctx = {"original": nombre_original, "inicio": inicio, "fin": fin}
    plantilla = PLANTILLA_DEFAULT_B67
    return generar_nombre_unico(plantilla, ctx, extension, existe_fn=existe_fn, nombres_en_lote=nombres_en_lote)


def generar_lote(plantilla, contextos, extension, existe_fn=None, fecha_hoy=None):
    """Genera nombres únicos para un lote, considerando colisiones intra-lote.

    contextos: lista de dicts, cada uno con claves según plantilla.
    Retorna lista de nombres completos únicos en orden de entrada.
    """
    ext = validar_extension(extension)
    resultado = []
    lote_set = set()
    # para determinismo, existe_fn se consulta contra FS además del lote
    for ctx in contextos:
        stem = renderizar_plantilla(plantilla, ctx, fecha_hoy=fecha_hoy)
        unico = resolver_colision(stem, ext, existe_fn=existe_fn, nombres_en_lote=lote_set)
        resultado.append(unico)
        lote_set.add(unico.lower())
    return resultado
