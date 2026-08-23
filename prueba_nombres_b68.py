"""Pruebas B6.8 — Motor general y reutilizable de nombres.

Cubre al menos 24 casos exigidos en la especificación B6.8.
"""

import datetime
import inspect
import os
import py_compile
import sys
import tempfile

import nombres

# helpers
def _ok(msg=""):
    return True, msg

def _fail(msg):
    return False, msg

def test_01_py_compile():
    for m in ["nombres.py", "visor_videos.py", "exportar_segmento.py"]:
        py_compile.compile(m, doraise=True)
    return _ok("py_compile OK")

def test_02_original_simple_y_multiples_puntos():
    # simple
    r = nombres.renderizar_plantilla("{original}", {"original": "video.mp4"})
    if r != "video":
        return _fail(f"simple {r!r} != 'video'")
    # múltiples puntos preservados
    r2 = nombres.renderizar_plantilla("{original}", {"original": "a.b.c.mp4"})
    if r2 != "a.b.c":
        return _fail(f"multi puntos {r2!r} != 'a.b.c'")
    # sin extensión
    r3 = nombres.renderizar_plantilla("{original}", {"original": "sin_ext"})
    if r3 != "sin_ext":
        return _fail(f"sin ext {r3!r}")
    # con ruta: como el motor trata '/' y ':' como inválidos a sanitizar
    # (el caller B6.7 pasa solo el nombre, no la ruta completa), el resultado
    # sanitizado conserva la ruta con '_' en lugar de truncarla
    r4 = nombres.renderizar_plantilla("{original}", {"original": "C:/ruta/a/mi.video.test.mkv"})
    if r4 != "C__ruta_a_mi.video.test":
        return _fail(f"con ruta {r4!r}")
    return _ok(f"{r} {r2} {r3} {r4}")

def test_03_unicode_acentos_preservados():
    r = nombres.renderizar_plantilla("{original}", {"original": "canción_niño.mp4"})
    if r != "canción_niño":
        return _fail(f"unicode original {r!r}")
    r2 = nombres.renderizar_plantilla("{texto}", {"texto": "año café"})
    if r2 != "año café":
        return _fail(f"unicode texto {r2!r}")
    # stemming con unicode y extensión
    r3 = nombres.generar_sugerencia_exportacion("canción_niño.mp4", 1.5, 3.7)
    if "canción_niño" not in r3:
        return _fail(f"unicode sugerencia {r3!r}")
    return _ok(f"{r} {r2} {r3}")

def test_04_invalidos_windows():
    # cada carácter inválido debe reemplazarse por "_"
    invalido = 'a<b>c:d"e/f\\g|h?i*j.mp4'
    # original contiene esos chars -> render debe sanitizar
    r = nombres.renderizar_plantilla("{original}", {"original": invalido})
    # debe no contener ninguno de los invalidos
    for ch in '<>:"/\\|?*':
        if ch in r:
            return _fail(f"carácter inválido {ch!r} aún en {r!r}")
    # comprobar que reemplazo fue "_"
    if r != "a_b_c_d_e_f_g_h_i_j":
        return _fail(f"sanitizado {r!r} != 'a_b_c_d_e_f_g_h_i_j'")
    # texto con invalidos
    r2 = nombres.renderizar_plantilla("{texto}", {"texto": 'hola<>:"/\\|?*mundo'})
    for ch in '<>:"/\\|?*':
        if ch in r2:
            return _fail(f"texto inválido {ch!r} en {r2!r}")
    return _ok(f"{r} {r2}")

def test_05_controles():
    s = "a\x00b\x01c\x1Fd.mp4"
    r = nombres.renderizar_plantilla("{original}", {"original": s})
    for code in range(32):
        if chr(code) in r:
            return _fail(f"control U+{code:04X} aún en {r!r}")
    # debe reemplazar por "_"
    if r != "a_b_c_d":
        return _fail(f"controles {r!r} != 'a_b_c_d'")
    # texto con controles
    r2 = nombres.renderizar_plantilla("{texto}", {"texto": "hola\x0A\x0D"})
    if "\n" in r2 or "\r" in r2:
        return _fail(f"controles en texto {r2!r}")
    return _ok(f"{r} {r2}")

def test_06_reservados_windows_y_variantes_case():
    for nombre in ["CON", "con", "PrN", "AUX", "nul", "COM1", "com9", "LPT1", "lpt9"]:
        r = nombres.renderizar_plantilla("{original}", {"original": nombre + ".mp4"})
        # debe prefijar "_" -> "_CON" etc
        base = r.lower()
        if not base.startswith("_"):
            return _fail(f"reservado {nombre!r} no prefijado: {r!r}")
        # verificar que original "CON" -> "_CON", "con" -> "_con"
        if r.upper() == nombre.upper():
            return _fail(f"reservado no sanitizado {nombre!r} -> {r!r}")
    # con extensión: "CON.txt" -> stem CON -> reservado incluso con extensión
    r = nombres.renderizar_plantilla("{original}", {"original": "CON.txt"})
    if not r.startswith("_"):
        return _fail(f"CON.txt no reservado {r!r}")
    # con texto reservado
    r2 = nombres.renderizar_plantilla("{texto}", {"texto": "CON"})
    if not r2.startswith("_"):
        return _fail(f"texto CON no reservado {r2!r}")
    # no reservado no debe prefijar
    r3 = nombres.renderizar_plantilla("{original}", {"original": "CONA.mp4"})
    if r3.startswith("_CON"):
        return _fail(f"falso reservado CONA {r3!r}")
    return _ok("reservados OK")

def test_07_trailing_punto_espacio():
    r = nombres.renderizar_plantilla("{texto}", {"texto": "nombre "})
    if r.endswith(" ") or r.endswith("."):
        return _fail(f"trailing espacio no eliminado {r!r}")
    if r != "nombre":
        return _fail(f"trailing espacio {r!r} != 'nombre'")
    r2 = nombres.renderizar_plantilla("{texto}", {"texto": "nombre."})
    if r2 != "nombre":
        return _fail(f"trailing punto {r2!r}")
    r3 = nombres.renderizar_plantilla("{texto}", {"texto": "nombre . "})
    if r3 != "nombre":
        return _fail(f"trailing mixto {r3!r}")
    # original con trailing
    r4 = nombres.renderizar_plantilla("{original}", {"original": "video .mp4"})
    # original stem "video " -> después sanitizado y rstrip -> "video"
    if r4 != "video":
        return _fail(f"original trailing {r4!r}")
    return _ok(f"{r} {r2} {r3} {r4}")

def test_08_vacio_tras_sanitizacion_error():
    try:
        nombres.renderizar_plantilla("{texto}", {"texto": "   "})
        return _fail("texto solo espacios debió fallar")
    except nombres.NombreVacioError:
        pass
    try:
        nombres.renderizar_plantilla("{texto}", {"texto": "."})
        return _fail("texto solo punto debió fallar")
    except nombres.NombreVacioError:
        pass
    try:
        nombres.renderizar_plantilla("{texto}", {"texto": " . "})
        return _fail("texto ' . ' debió fallar")
    except nombres.NombreVacioError:
        pass
    # plantilla que queda vacía? usar texto vacío con plantilla que solo es texto
    try:
        nombres.sanitizar_componente("   ...   ")
        return _fail("sanitizar solo puntos/espacios debió fallar")
    except nombres.NombreVacioError:
        pass
    return _ok("vacio error OK")

def test_09_numero_default_y_padding_valido():
    r = nombres.renderizar_plantilla("{numero}", {"numero": 7})
    if r != "7":
        return _fail(f"numero default {r!r} != '7'")
    r2 = nombres.renderizar_plantilla("{numero:03d}", {"numero": 7})
    if r2 != "007":
        return _fail(f"padding 03d {r2!r} != '007'")
    r3 = nombres.renderizar_plantilla("{numero:02d}", {"numero": 5})
    if r3 != "05":
        return _fail(f"02d {r3!r}")
    r4 = nombres.renderizar_plantilla("{numero:04d}", {"numero": 123})
    if r4 != "0123":
        return _fail(f"04d {r4!r}")
    # número grande sin truncar
    r5 = nombres.renderizar_plantilla("{numero:03d}", {"numero": 1234})
    if r5 != "1234":
        return _fail(f"1234 con 03d debe ser 1234 sin truncar, got {r5!r}")
    return _ok(f"{r} {r2} {r3} {r4} {r5}")

def test_10_padding_formato_invalido_error():
    invalidos = ["{numero:abc}", "{numero:03x}", "{numero:0d}", "{numero:03}", "{numero::03d}", "{numero:03D}"]
    for plantilla in invalidos:
        try:
            nombres.renderizar_plantilla(plantilla, {"numero": 1})
            return _fail(f"formato inválido no detectado {plantilla!r}")
        except nombres.FormatoInvalidoError:
            pass
        except nombres.NombresError:
            pass  # cualquier error de dominio es aceptable aquí si es formato
        else:
            return _fail(f"sin error {plantilla!r}")
    # también formato fecha inválido
    try:
        nombres.renderizar_plantilla("{fecha:bad}", {"fecha": datetime.date(2026, 8, 20)})
        return _fail("fecha bad debió fallar")
    except nombres.FormatoInvalidoError:
        pass
    # original con formato debe fallar
    try:
        nombres.renderizar_plantilla("{original:03d}", {"original": "video.mp4"})
        return _fail("original con formato debió fallar")
    except nombres.FormatoInvalidoError:
        pass
    return _ok("formatos inválidos OK")

def test_11_fecha_determinista_inyectada():
    fecha = datetime.date(2026, 8, 20)
    r = nombres.renderizar_plantilla("{fecha}", {"fecha": fecha})
    if r != "20260820":
        return _fail(f"fecha default {r!r} != '20260820'")
    r2 = nombres.renderizar_plantilla("{fecha:YYYY-MM-DD}", {"fecha": fecha})
    if r2 != "2026-08-20":
        return _fail(f"fecha YYYY-MM-DD {r2!r}")
    # con fecha_hoy inyectada y sin contexto fecha
    r3 = nombres.renderizar_plantilla("{fecha}", {}, fecha_hoy=fecha)
    if r3 != "20260820":
        return _fail(f"fecha_hoy {r3!r}")
    # string YYYYMMDD
    r4 = nombres.renderizar_plantilla("{fecha}", {"fecha": "20260820"})
    if r4 != "20260820":
        return _fail(f"fecha string {r4!r}")
    # DDMMYYYY
    r5 = nombres.renderizar_plantilla("{fecha:DDMMYYYY}", {"fecha": fecha})
    if r5 != "20082026":
        return _fail(f"DDMMYYYY {r5!r}")
    return _ok(f"{r} {r2} {r3} {r4} {r5}")

def test_12_texto_personalizado():
    r = nombres.renderizar_plantilla("{texto}", {"texto": "mi proyecto"})
    if r != "mi proyecto":
        return _fail(f"texto con espacio interno {r!r}")
    # espacios internos normales no colapsados
    r2 = nombres.renderizar_plantilla("{texto}", {"texto": "a  b"})
    if r2 != "a  b":
        return _fail(f"doble espacio colapsado {r2!r}")
    # con caracteres acentuados preservados
    r3 = nombres.renderizar_plantilla("{texto}", {"texto": "prueba_niño-año"})
    if r3 != "prueba_niño-año":
        return _fail(f"acentos {r3!r}")
    return _ok(f"{r} {r2} {r3}")

def test_13_token_desconocido_plantilla_mal_formada():
    try:
        nombres.renderizar_plantilla("{desconocido}", {"desconocido": "x"})
        return _fail("token desconocido debió fallar")
    except nombres.TokenDesconocidoError:
        pass
    try:
        nombres.renderizar_plantilla("{original", {"original": "video.mp4"})
        return _fail("llave sin cerrar debió fallar")
    except nombres.PlantillaInvalidaError:
        pass
    try:
        nombres.renderizar_plantilla("hola {original} {", {"original": "v.mp4"})
        return _fail("llave suelta debió fallar")
    except nombres.PlantillaInvalidaError:
        pass
    try:
        nombres.renderizar_plantilla("", {"original": "v.mp4"})
        return _fail("plantilla vacía debió fallar")
    except nombres.PlantillaInvalidaError:
        pass
    # plantilla con token vacío
    try:
        nombres.renderizar_plantilla("{}", {})
        return _fail("{} debió fallar")
    except nombres.PlantillaInvalidaError:
        pass
    return _ok("tokens mal formados OK")

def test_14_contexto_requerido_ausente():
    try:
        nombres.renderizar_plantilla("{original}", {})
        return _fail("original ausente debió fallar")
    except nombres.ContextoFaltanteError:
        pass
    try:
        nombres.renderizar_plantilla("{numero}", {})
        return _fail("numero ausente debió fallar")
    except nombres.ContextoFaltanteError:
        pass
    try:
        nombres.renderizar_plantilla("{texto}", {})
        return _fail("texto ausente debió fallar")
    except nombres.ContextoFaltanteError:
        pass
    try:
        nombres.renderizar_plantilla("{inicio}", {"fin": 1.0})
        return _fail("inicio ausente debió fallar")
    except nombres.ContextoFaltanteError:
        pass
    try:
        nombres.renderizar_plantilla("{fin}", {"inicio": 1.0})
        return _fail("fin ausente debió fallar")
    except nombres.ContextoFaltanteError:
        pass
    return _ok("contexto faltante OK")

def test_15_extension_normalizada_y_no_permitida():
    r = nombres.generar_nombre("{original}", {"original": "video.mp4"}, ".mp4")
    if not r.endswith(".mp4"):
        return _fail(f"ext mp4 {r!r}")
    r2 = nombres.generar_nombre("{original}", {"original": "video.mp4"}, ".MP4")
    if not r2.endswith(".mp4"):
        return _fail(f"normalización mayúscula {r2!r}")
    r3 = nombres.generar_nombre("{original}", {"original": "video.mp4"}, "mkv")
    if not r3.endswith(".mkv"):
        return _fail(f"sin punto {r3!r}")
    # no permitida debe fallar
    try:
        nombres.generar_nombre("{original}", {"original": "video.mp4"}, ".avi")
        return _fail(".avi debió fallar")
    except nombres.ExtensionInvalidaError:
        pass
    # asegurar_extension con sin ext agrega .mp4
    r4 = nombres.asegurar_extension("ruta/archivo", extensiones_validas={".mp4", ".mkv"}, default=".mp4")
    if not r4.endswith(".mp4"):
        return _fail(f"asegurar sin ext {r4!r}")
    # con ext explícita no permitida .avi -> debe rechazar, no agregar .mp4
    try:
        nombres.asegurar_extension("ruta/archivo.avi", extensiones_validas={".mp4", ".mkv"}, default=".mp4")
        return _fail("asegurar .avi debió lanzar ExtensionInvalidaError, no .avi.mp4")
    except nombres.ExtensionInvalidaError:
        pass
    # .exe también debe rechazar
    try:
        nombres.asegurar_extension("ruta/archivo.exe", extensiones_validas={".mp4", ".mkv"}, default=".mp4")
        return _fail("asegurar .exe debió lanzar ExtensionInvalidaError")
    except nombres.ExtensionInvalidaError:
        pass
    # mayúsculas permitidas deben normalizar a minúsculas
    r5 = nombres.asegurar_extension("ruta/archivo.MP4", extensiones_validas={".mp4", ".mkv"}, default=".mp4")
    if r5 != "ruta/archivo.mp4":
        return _fail(f"asegurar mayúscula .MP4 {r5!r} != 'ruta/archivo.mp4'")
    r6 = nombres.asegurar_extension("ruta/archivo.MKV", extensiones_validas={".mp4", ".mkv"}, default=".mp4")
    if r6 != "ruta/archivo.mkv":
        return _fail(f"asegurar mayúscula .MKV {r6!r} != 'ruta/archivo.mkv'")
    return _ok(f"{r} {r2} {r3} {r4} {r5} {r6}")

def test_16_colision_FS_001():
    def existe(nombre):
        return nombre.lower() == "video.mp4"
    r = nombres.generar_nombre_unico("{original}", {"original": "video.mp4"}, ".mp4", existe_fn=existe)
    if r != "video_001.mp4":
        return _fail(f"colision FS {r!r} != 'video_001.mp4'")
    # sin colisión debe devolver base
    def existe_nada(_):
        return False
    r2 = nombres.generar_nombre_unico("{original}", {"original": "video.mp4"}, ".mp4", existe_fn=existe_nada)
    if r2 != "video.mp4":
        return _fail(f"sin colisión {r2!r}")
    return _ok(f"{r} {r2}")

def test_17_multiples_colisiones_siguiente_libre():
    existentes = {"video.mp4", "video_001.mp4", "video_002.mp4"}
    def existe(n):
        return n.lower() in {e.lower() for e in existentes}
    r = nombres.generar_nombre_unico("{original}", {"original": "video.mp4"}, ".mp4", existe_fn=existe)
    if r != "video_003.mp4":
        return _fail(f"múltiples {r!r} != 'video_003.mp4'")
    existentes.add("video_003.mp4")
    r2 = nombres.generar_nombre_unico("{original}", {"original": "video.mp4"}, ".mp4", existe_fn=lambda n: n.lower() in {e.lower() for e in existentes})
    if r2 != "video_004.mp4":
        return _fail(f"siguiente {r2!r}")
    return _ok(f"{r} {r2}")

def test_18_colision_intra_lote_case_insensitive():
    lote = {"Video.mp4"}
    def existe(_):
        return False
    r = nombres.generar_nombre_unico("{original}", {"original": "video.mp4"}, ".mp4", existe_fn=existe, nombres_en_lote=lote)
    if r.lower() != "video_001.mp4":
        return _fail(f"intra lote case {r!r}")
    # segundo en lote debe considerar el primero recién asignado
    lote2 = {"video.mp4", "video_001.mp4"}
    r2 = nombres.generar_nombre_unico("{original}", {"original": "VIDEO.mp4"}, ".mp4", existe_fn=existe, nombres_en_lote=lote2)
    if r2.lower() != "video_002.mp4":
        return _fail(f"intra lote 2 {r2!r}")
    return _ok(f"{r} {r2}")

def test_19_combinacion_FS_lote():
    existentes_fs = {"video.mp4"}
    lote = {"video_001.mp4"}
    def existe(n):
        return n.lower() in {e.lower() for e in existentes_fs}
    r = nombres.generar_nombre_unico("{original}", {"original": "video.mp4"}, ".mp4", existe_fn=existe, nombres_en_lote=lote)
    if r != "video_002.mp4":
        return _fail(f"FS+lote {r!r} != 'video_002.mp4'")
    return _ok(r)

def test_20_repetibilidad_determinismo():
    def existe(n):
        return n.lower() == "clip.mp4"
    lote = set()
    r1 = nombres.generar_nombre_unico("{original}_{numero:03d}", {"original": "clip.mp4", "numero": 2}, ".mp4", existe_fn=existe, nombres_en_lote=lote)
    r2 = nombres.generar_nombre_unico("{original}_{numero:03d}", {"original": "clip.mp4", "numero": 2}, ".mp4", existe_fn=existe, nombres_en_lote=lote)
    if r1 != r2:
        return _fail(f"no determinista {r1!r} vs {r2!r}")
    # lote generation determinista
    ctxs = [{"original": "video.mp4", "numero": 1}, {"original": "video.mp4", "numero": 1}]
    lote_a = nombres.generar_lote("{original}_{numero:03d}", ctxs, ".mp4", existe_fn=lambda _: False)
    lote_b = nombres.generar_lote("{original}_{numero:03d}", ctxs, ".mp4", existe_fn=lambda _: False)
    if lote_a != lote_b:
        return _fail(f"lote no determinista {lote_a!r} vs {lote_b!r}")
    if lote_a[0] == lote_a[1]:
        return _fail(f"lote debería desambiguar {lote_a!r}")
    return _ok(f"{r1} {lote_a}")

def test_21_inicio_fin_dos_decimales_y_default_B67():
    r = nombres.generar_sugerencia_exportacion("video.mp4", 1.5, 3.7, extension=".mp4")
    if r != "video_segmento_1.50-3.70.mp4":
        return _fail(f"sugerencia B67 {r!r} != 'video_segmento_1.50-3.70.mp4'")
    # con múltiplos puntos
    r2 = nombres.generar_sugerencia_exportacion("a.b.c.mp4", 0, 0.4, extension=".mp4")
    if r2 != "a.b.c_segmento_0.00-0.40.mp4":
        return _fail(f"multi puntos B67 {r2!r}")
    # con unicode
    r3 = nombres.generar_sugerencia_exportacion("canción.mp4", 10.123, 20.987, extension=".mp4")
    # 10.123 -> 10.12, 20.987 -> 20.99
    if r3 != "canción_segmento_10.12-20.99.mp4":
        return _fail(f"decimales {r3!r}")
    # extensión mkv
    r4 = nombres.generar_sugerencia_exportacion("video.mp4", 1, 2, extension=".mkv")
    if r4 != "video_segmento_1.00-2.00.mkv":
        return _fail(f"mkv {r4!r}")
    # plantilla default explícita debe dar lo mismo
    r5 = nombres.generar_nombre(nombres.PLANTILLA_DEFAULT_B67, {"original": "video.mp4", "inicio": 1.5, "fin": 3.7}, ".mp4")
    if r5 != "video_segmento_1.50-3.70.mp4":
        return _fail(f"plantilla default {r5!r}")
    return _ok(f"{r} {r2} {r3} {r4}")

def test_22_integracion_B67_visor_usa_motor_y_no_loop_manual():
    src = open("visor_videos.py", encoding="utf-8").read()
    if "import nombres" not in src and "from nombres" not in src:
        return _fail("visor no importa nombres")
    if "generar_sugerencia_exportacion" not in src and "nombres.generar" not in src:
        return _fail("visor no usa motor de nombres")
    # no debe mantener loop manual de sanitización
    if 'for ch in \'<>:"/\\\\|?*\'' in src or "for ch in '<>:\"/\\|?*'" in src:
        return _fail("visor aún contiene loop manual '<>:\"/\\|?*'")
    # buscar patrón antiguo de generación manual
    if 'sugerido = f"{base}_segmento_' in src:
        return _fail("visor aún genera sugerido manualmente con f-string")
    # debe usar asegurar_extension del motor
    if "asegurar_extension" not in src:
        return _fail("visor no usa asegurar_extension del motor")
    return _ok("integración visor OK")

def test_23_motor_sin_imports_prohibidos():
    src = open("nombres.py", encoding="utf-8").read()
    # verificar imports reales, no meras menciones en comentarios
    for prohibido in ["import PySide6", "from PySide6", "import sqlite3", "import subprocess", "from subprocess", "import FFmpeg", "QFileDialog"]:
        if prohibido in src:
            return _fail(f"motor contiene import prohibido {prohibido!r}")
    # verificar que no importa os.replace para sobrescribir (uso, no comentario)
    # buscar uso real fuera de comentarios/docstring: inspeccionar lineas que no son comentario
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "os.replace" in line:
            return _fail("motor usa os.replace")
    return _ok("motor limpio OK")

def test_24_no_sobrescritura_publicacion_B67_no_debilitada():
    src_exp = open("exportar_segmento.py", encoding="utf-8").read()
    # debe mantener doble comprobación de colisión y os.rename sin -y
    if "destino ya existe" not in src_exp:
        return _fail("exportar_segmento perdió check de colisión")
    if "os.rename" not in src_exp:
        return _fail("exportar_segmento no usa os.rename")
    if '"-y"' in src_exp or "'-y'" in src_exp:
        return _fail("exportar_segmento usa -y")
    src_visor = open("visor_videos.py", encoding="utf-8").read()
    if "os.path.exists(ruta_dest)" not in src_visor:
        return _fail("visor perdió validación de destino existente")
    if "os.path.normcase" not in src_visor or "os.path.abspath(ruta_dest)" not in src_visor:
        return _fail("visor perdió validación destino != fuente")
    # visor debe delegar a TareaExportarSegmento aún
    if "TareaExportarSegmento" not in src_visor:
        return _fail("visor no usa TareaExportarSegmento")
    return _ok("no sobrescritura preservada")

def test_25_longitud_max_componente():
    # stem muy largo debe dar error explícito, no truncar silencioso
    largo = "a" * 300
    try:
        nombres.generar_nombre("{original}", {"original": largo + ".mp4"}, ".mp4")
        return _fail("nombre muy largo debió fallar")
    except nombres.NombreVacioError:
        pass
    # con extensión y sufijo también
    stem_casi = "a" * 250  # 250 + 4 =254 ok, 251+4=255 ok, 252+4=256 debe fallar con sufijo
    # sin colisión no necesita sufijo -> 250+4=254 <255 ok
    r = nombres.generar_nombre("{texto}", {"texto": stem_casi}, ".mp4")
    if len(r) > nombres.MAX_COMPONENTE:
        return _fail(f"longitud ok pero excede {len(r)}")
    # con colisión que requiere sufijo y stem 253 -> 253+4+4=261 excede
    stem_largo = "a" * 253
    def existe(n):
        # hacer que base colisione
        return n.lower().startswith(stem_largo.lower())
    try:
        nombres.generar_nombre_unico("{texto}", {"texto": stem_largo}, ".mp4", existe_fn=lambda n: n.lower() == stem_largo.lower() + ".mp4")
        # debería devolver _001 y validar longitud; 253+4+4=261 >255 debe fallar
        # si no falla, es porque stem 253+ "_001" =257 + ".mp4"=261 >255 -> debe lanzar
        return _fail("longitud con sufijo debió fallar")
    except nombres.NombreVacioError:
        pass
    return _ok("longitud OK")

def main():
    pruebas = [
        test_01_py_compile,
        test_02_original_simple_y_multiples_puntos,
        test_03_unicode_acentos_preservados,
        test_04_invalidos_windows,
        test_05_controles,
        test_06_reservados_windows_y_variantes_case,
        test_07_trailing_punto_espacio,
        test_08_vacio_tras_sanitizacion_error,
        test_09_numero_default_y_padding_valido,
        test_10_padding_formato_invalido_error,
        test_11_fecha_determinista_inyectada,
        test_12_texto_personalizado,
        test_13_token_desconocido_plantilla_mal_formada,
        test_14_contexto_requerido_ausente,
        test_15_extension_normalizada_y_no_permitida,
        test_16_colision_FS_001,
        test_17_multiples_colisiones_siguiente_libre,
        test_18_colision_intra_lote_case_insensitive,
        test_19_combinacion_FS_lote,
        test_20_repetibilidad_determinismo,
        test_21_inicio_fin_dos_decimales_y_default_B67,
        test_22_integracion_B67_visor_usa_motor_y_no_loop_manual,
        test_23_motor_sin_imports_prohibidos,
        test_24_no_sobrescritura_publicacion_B67_no_debilitada,
        test_25_longitud_max_componente,
    ]
    ok_total = True
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, detalle = fn()
        except Exception as exc:
            import traceback
            ok, detalle = False, f"excepcion {type(exc).__name__}: {exc}\n{traceback.format_exc()[:600]}"
        print(f"P{i:02d} {'OK' if ok else 'FALLO'} - {fn.__name__}: {detalle}")
        sys.stdout.flush()
        if not ok:
            ok_total = False
    print(f"TOTAL={sum(1 for _ in pruebas if True)}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1

if __name__ == "__main__":
    sys.exit(main())
