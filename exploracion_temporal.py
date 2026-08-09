"""Lógica pura de exploración temporal (etapa B4.1).

Convierte la posición horizontal del cursor en un instante temporal
proporcional a la duración del video y selecciona, entre las previews
ya disponibles, la que corresponde al instante más cercano.

Sin Qt, sin FFmpeg, sin SQLite, sin archivos y sin caché persistente.
"""


def ancho_valido(ancho):
    return (
        isinstance(ancho, (int, float))
        and not isinstance(ancho, bool)
        and ancho > 0
    )


def duracion_valida(duracion):
    return (
        isinstance(duracion, (int, float))
        and not isinstance(duracion, bool)
        and duracion > 0
    )


def _posicion_valida(posicion):
    return (
        isinstance(posicion, (int, float))
        and not isinstance(posicion, bool)
    )


def normalizar_posicion(posicion, ancho):
    """Acota una posición horizontal (px) al intervalo [0, ancho].

    Devuelve None si el ancho o la posición no son valores válidos.
    """
    if not ancho_valido(ancho):
        return None
    if not _posicion_valida(posicion):
        return None
    if posicion <= 0:
        return 0.0
    if posicion >= ancho:
        return float(ancho)
    return float(posicion)


def posicion_a_tiempo(posicion, ancho, duracion):
    """Convierte una posición horizontal (px) en un instante (segundos).

    x = 0 -> 0; x = ancho -> duracion; posiciones fuera de rango se
    acotan. Devuelve None si ancho o duración no son válidos.
    """
    x = normalizar_posicion(posicion, ancho)
    if x is None:
        return None
    if not duracion_valida(duracion):
        return None
    return duracion * x / ancho


def tiempo_a_posicion(instante, ancho, duracion):
    """Convierte un instante (segundos) en posición horizontal (px).

    instante 0 -> 0; instante == duracion -> ancho; valores fuera de
    rango se acotan. Devuelve None si ancho, duración o instante no son
    válidos.
    """
    if not ancho_valido(ancho):
        return None
    if not duracion_valida(duracion):
        return None
    if not _posicion_valida(instante):
        return None
    proporcion = max(0.0, min(1.0, float(instante) / duracion))
    return proporcion * ancho


def agregar_marcador_ordenado(instante, marcadores, tolerancia=0.0):
    """Inserta `instante` conservando el orden temporal y sin duplicados cercanos.

    Devuelve `(marcadores, agregado)`. Si `instante` está dentro de
    `tolerancia` de un marcador existente, no se agrega. Los marcadores
    se devuelven ordenados de menor a mayor. Guarda el instante real
    calculado, nunca índices de preview ni representaciones derivadas.
    """
    validos = sorted(
        m for m in marcadores
        if isinstance(m, (int, float)) and not isinstance(m, bool)
    )
    if not _posicion_valida(instante):
        return validos, False
    objetivo = float(instante)
    for m in validos:
        if abs(m - objetivo) <= tolerancia:
            return validos, False
    nuevos = validos + [objetivo]
    nuevos.sort()
    return nuevos, True


def preview_mas_cercana(instantes, instante):
    """Índice de la preview (en `instantes`) más cercana al instante pedido.

    - `instantes` es la lista de instantes de cada preview; los valores
      None se descartan (preview sin instante asociado).
    - Devuelve el índice dentro de la lista original (para poder acceder
      a la misma posición en la estructura paralela de pixmaps).
    - En empate de distancia se elige la preview anterior (menor índice).
    - Devuelve None si el instante pedido es inválido o no hay instantes
      disponibles.
    """
    if not _posicion_valida(instante):
        return None
    candidatos = []
    for indice, tiempo in enumerate(instantes):
        if not _posicion_valida(tiempo):
            continue
        candidatos.append((indice, float(tiempo)))
    if not candidatos:
        return None
    objetivo = float(instante)
    mejor = min(
        candidatos,
        key=lambda par: (abs(par[1] - objetivo), par[0]),
    )
    return mejor[0]
