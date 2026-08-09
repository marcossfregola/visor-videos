"""Lógica pura de exploración temporal (etapas B4.1 y B4.3.1).

Convierte la posición horizontal del cursor en un instante temporal
proporcional a la duración del video, selecciona la preview más cercana,
calcula la densidad de la caché densa de exploración y el orden
progresivo de los fotogramas objetivo.

Sin Qt, sin FFmpeg, sin SQLite, sin archivos y sin caché persistente.
"""

import bisect

# Densidad de la caché densa de exploración (aprobada provisionalmente
# en el diseño de B4.3): un fotograma cada dos segundos, con piso y techo.
PASO_SEGUNDOS = 2.0
MINIMO_FOTOGRAMAS = 40
MAXIMO_FOTOGRAMAS = 200


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


def cantidad_fotogramas(duracion):
    """Número de fotogramas objetivo para la caché densa de exploración.

    Fórmula aprobada: `clamp(round(duracion / PASO_SEGUNDOS), mínimo,
    máximo)`. Una duración inválida (no numérica, cero, negativa o
    booleana) devuelve 0, que significa "sin caché posible".
    """
    if not duracion_valida(duracion):
        return 0
    estimado = round(float(duracion) / PASO_SEGUNDOS)
    return max(MINIMO_FOTOGRAMAS, min(MAXIMO_FOTOGRAMAS, estimado))


def tiempos_objetivo(duracion, cantidad):
    """Instantes (milisegundos) objetivo en orden progresivo de cobertura.

    La cobertura crece por bisección de huecos: primero el punto medio
    (50 %), después los cuartos (25 % y 75 %), después los octavos
    (12.5 %, 37.5 %, 62.5 % y 87.5 %) y así sucesivamente, de izquierda
    a derecha en cada nivel. El orden devuelto es el orden de generación
    recomendado: pocos fotogramas bien repartidos al inicio y densidad
    creciente después.

    Los valores son milisegundos enteros y se descartan duplicados que
    aparezcan tras redondear. La generación se detiene al alcanzar
    `cantidad` o cuando ya no quedan milisegundos nuevos que añadir.
    Devuelve [] si la duración es inválida o `cantidad` no es un entero
    positivo.
    """
    if not duracion_valida(duracion):
        return []
    if isinstance(cantidad, bool) or not isinstance(cantidad, int):
        return []
    if cantidad <= 0:
        return []
    duracion_ms = max(1, round(float(duracion) * 1000))
    resultado = []
    vistos = set()
    nivel = 0
    while len(resultado) < cantidad:
        nivel += 1
        divisor = 2 ** nivel
        agregados_en_nivel = 0
        for i in range(1, divisor):
            ms = round(duracion_ms * i / divisor)
            if ms <= 0 or ms >= duracion_ms:
                continue
            if ms in vistos:
                continue
            vistos.add(ms)
            resultado.append(ms)
            agregados_en_nivel += 1
            if len(resultado) >= cantidad:
                break
        if agregados_en_nivel == 0:
            break
    return resultado


def fotograma_mas_cercano(ms_existentes, instante):
    """Milisegundo del fotograma más cercano al instante pedido.

    - `ms_existentes` es una colección de milisegundos enteros (los de
      la caché densa); no es necesario que venga ordenada.
    - `instante` se expresa en segundos y se convierte a milisegundos.
    - Usa `bisect` sobre la lista ordenada; en empate de distancia se
      elige el fotograma anterior (menor instante).
    - Devuelve None si no hay fotogramas válidos o el instante es
      inválido.
    """
    if not _posicion_valida(instante):
        return None
    if isinstance(ms_existentes, (str, bytes, bytearray)):
        return None
    try:
        lista = iter(ms_existentes)
    except TypeError:
        return None
    ordenados = sorted(
        ms for ms in lista
        if isinstance(ms, int) and not isinstance(ms, bool) and ms >= 0
    )
    if not ordenados:
        return None
    objetivo = round(float(instante) * 1000)
    i = bisect.bisect_left(ordenados, objetivo)
    if i < len(ordenados) and ordenados[i] == objetivo:
        return ordenados[i]
    if i == 0:
        return ordenados[0]
    if i == len(ordenados):
        return ordenados[-1]
    distancia_izquierda = objetivo - ordenados[i - 1]
    distancia_derecha = ordenados[i] - objetivo
    if distancia_izquierda <= distancia_derecha:
        return ordenados[i - 1]
    return ordenados[i]
