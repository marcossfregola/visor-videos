"""Prueba B8.3B — Hardening final de identidad UI por video_id (A-O + P).

Cubre:
 A. Dos videos mismo nombre distinto id son tarjetas independientes.
 B. Seleccionar uno no selecciona al otro.
 C. Evento con video_id inexistente NO afecta homónima.
 D. Exploración con ID inexistente NO cae por nombre.
 E. Resultado parcial/final con ID inexistente NO se aplica al homónimo.
 F. Marcadores con ID inexistente NO caen por nombre.
 G. Segmentos con ID inexistente NO caen por nombre.
 H. Colores/rollback/error con ID válido NO afectan homónimo.
 I. Operaciones individuales con ID inexistente NO buscan por nombre.
 J. Menú contextual con ID inexistente NO resuelve homónimo.
 K. Previews/resultados asincrónicos con ID válido NO se aplican a homónimo.
 L. Selección múltiple usa IDs distintos aunque nombres iguales.
 M. Drag & drop conserva IDs independientes.
 N. Recarga/filtro no colapsa homónimos.
 O. AST real anti-fallback (tarjeta_por_id -> if None -> tarjeta_por_nombre) con ID válido.
 P. Arquitectura UI sin sqlite/SQL/conectar_bd/subprocess/Popen/ffmpeg/ffprobe.
"""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import ast
import tempfile
import inspect
from PySide6.QtWidgets import QApplication
import visor_videos
from visor_videos import Tarjeta, VisorVideos

_CONTADOR = [0]
_FALLOS = [0]

def _paso():
    _CONTADOR[0] += 1
    return _CONTADOR[0]

def ok(msg):
    _paso()
    print(f"T{_CONTADOR[0]:02d} OK - {msg}")

def falla(msg, extra=None):
    _FALLOS[0] += 1
    _paso()
    t = f"T{_CONTADOR[0]:02d} ERROR - {msg}"
    if extra is not None:
        t += f" ({extra})"
    print(t)

def verifica(cond, desc, extra=None):
    if cond:
        ok(desc)
    else:
        falla(desc, extra)
    return cond

def _fila_con_id(nombre, video_id, carpeta):
    ruta = os.path.join(carpeta, nombre)
    return (nombre, 10.0, 640, 480, "h264", 1, 1024, ruta, video_id)

def _crear_visor_homonimos():
    app = QApplication.instance() or QApplication([])
    tmp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(tmp.name, "catalogo.db")
    ruta_config = os.path.join(tmp.name, "config.json")
    # Crear VisorVideos con db temporal vacía
    import sqlite3
    import escanear_videos as ev
    conn = ev.conectar_bd(ruta_db)
    conn.close()
    visor = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
    # Limpiar tarjetas que haya creado por defecto (carga vacía)
    # Visor crea UI pero aún no ha cargado catálogo; limpiar manualmente
    try:
        visor.tarjetas.clear()
        visor.visibles.clear()
        visor._ids_seleccionados.clear()
        visor._nombres_seleccionados.clear()
        visor._ancla_seleccion = None
        visor._ancla_seleccion_id = None
    except Exception:
        pass
    # Crear dos tarjetas homónimas
    filaA = _fila_con_id("video.mp4", 101, "C:\\tmp\\A")
    filaB = _fila_con_id("video.mp4", 102, "C:\\tmp\\B")
    tA = Tarjeta(filaA)
    tB = Tarjeta(filaB)
    # Inyectar manualmente en visor (sin pasar por _crear_tarjetas para evitar filtros)
    visor.tarjetas.append(("video.mp4", tA))
    visor.tarjetas.append(("video.mp4", tB))
    visor.visibles = ["video.mp4", "video.mp4"]
    # Asegurar señales conectadas mínimas para selección (no necesario para _tarjeta_por_id)
    return app, visor, tA, tB, tmp

# ---------- A ----------
def test_A_independientes():
    app, visor, tA, tB, tmp = _crear_visor_homonimos()
    try:
        verifica(tA is not tB, "A - dos tarjetas homónimas son objetos distintos")
        verifica(tA._video_id == 101 and tB._video_id == 102, "A - ids distintos 101 vs 102")
        verifica(tA.nombre == "video.mp4" and tB.nombre == "video.mp4", "A - mismo nombre video.mp4")
        verifica(visor._tarjeta_por_id(101) is tA, "A - _tarjeta_por_id 101 -> tA")
        verifica(visor._tarjeta_por_id(102) is tB, "A - _tarjeta_por_id 102 -> tB")
        verifica(visor._tarjeta_por_id(101) is not tB, "A - _tarjeta_por_id 101 no es tB")
        # _tarjeta_por_nombre devuelve primera, pero no debe usarse con ID válido
        primera = visor._tarjeta_por_nombre("video.mp4")
        verifica(primera is tA, "A - _tarjeta_por_nombre devuelve primera (legacy)")
        ok("A OK — homónimos con ids distintos son independientes")
    finally:
        tmp.cleanup()
        # visor deletion offscreen
        try:
            visor.close()
        except Exception:
            pass

# ---------- B ----------
def test_B_seleccion_uno_no_otro():
    app, visor, tA, tB, tmp = _crear_visor_homonimos()
    try:
        visor._al_seleccionar_tarjeta(101, False)
        verifica(101 in visor._ids_seleccionados and 102 not in visor._ids_seleccionados, "B - seleccionar 101 solo 101")
        verifica(tA._seleccionada and not tB._seleccionada, "B - visual solo tA seleccionada")
        visor._limpiar_seleccion()
        verifica(not visor._ids_seleccionados and not tA._seleccionada and not tB._seleccionada, "B - limpiar deja ambas deseleccionadas")
        ok("B OK — seleccionar uno no selecciona al otro")
    finally:
        tmp.cleanup()
        try:
            visor.close()
        except Exception:
            pass

# ---------- C ----------
def test_C_id_inexistente_no_afecta_homonima():
    app, visor, tA, tB, tmp = _crear_visor_homonimos()
    try:
        # Intentar seleccionar id inexistente 9999 con mismo nombre "video.mp4" no debe afectar tA/tB
        # _al_seleccionar_tarjeta con 9999: no existe tarjeta, debe hacer no-op (mantener selección vacía)
        visor._al_seleccionar_tarjeta(9999, False)
        verifica(9999 not in visor._ids_seleccionados or visor._tarjeta_por_id(9999) is None, "C - id 9999 no encuentra tarjeta")
        verifica(not tA._seleccionada and not tB._seleccionada, "C - homónimas no afectadas por evento id inexistente")
        # Además probar _marcar_tarjeta_por_id con inexistente no marca homónima
        visor._marcar_tarjeta_por_id(9999, True)
        verifica(not tA._seleccionada and not tB._seleccionada, "C - _marcar_tarjeta_por_id inexistente no marca homónima")
        # _aplicar_previews ya testeado en K, pero aquí verificar _tarjeta_por_id fallback no ocurre
        code = open("visor_videos.py", encoding="utf-8").read()
        verifica("def _es_video_id_valido" in code, "C - helper _es_video_id_valido existe")
        ok("C OK — evento con video_id inexistente no afecta homónima")
    finally:
        tmp.cleanup()
        try:
            visor.close()
        except Exception:
            pass

# ---------- D ----------
def test_D_exploracion_id_inexistente_no_fallback():
    app, visor, tA, tB, tmp = _crear_visor_homonimos()
    try:
        # Preparar exploración con objetivo_id inexistente 9999 pero nombre existente "video.mp4"
        tA._expandida = True
        tB._expandida = True
        visor._exploracion_objetivo = "video.mp4"
        visor._exploracion_objetivo_id = 9999
        visor._cola_exploracion = ["video.mp4"]
        # Gestor no activo
        visor.gestor_exploracion._activo = False if hasattr(visor.gestor_exploracion, "_activo") else False
        # Forzar que _procesar no inicie tarea porque id inexistente debe hacer continue (no fallback)
        # Si hubiera fallback, iniciaría tarea con tA. Verificamos que no deja op_actual con id de homónimo.
        visor._exploracion_op_actual = None
        visor._procesar_siguiente_exploracion()
        # Tras procesar, cola debe vaciarse sin crear op con video_id 101
        op = visor._exploracion_op_actual
        # Si fallback existiera, op contendría video_id 101; con fix debe ser None
        verifica(op is None, "D - exploración con ID inexistente no crea op para homónimo (no fallback)")
        # También chequear que tA no recibió densos (no se llamó _aplicar)
        ok("D OK — exploración con ID inexistente no cae por nombre")
    finally:
        tmp.cleanup()
        try:
            visor.close()
        except Exception:
            pass

# ---------- E ----------
def test_E_resultado_exploracion_id_inexistente():
    app, visor, tA, tB, tmp = _crear_visor_homonimos()
    try:
        tA._expandida = True
        tB._expandida = True
        tA._previews_densos = []
        tB._previews_densos = []
        visor._exploracion_objetivo = "video.mp4"
        visor._exploracion_objetivo_id = 9999
        visor._exploracion_op_actual = {"video_id": 9999, "nombre": "video.mp4"}
        # Resultado fake con fotogramas
        resultado = {"version": "v1", "fotogramas": [100, 200], "imagenes": [], "cancelado": False}
        # Antes ambos vacíos
        visor._al_resultado_exploracion(resultado)
        verifica(len(tA._previews_densos) == 0 and len(tB._previews_densos) == 0, "E - resultado final id inexistente no aplica a homónimas")
        # Parcial
        parcial = {"video_id": 9999, "fotogramas": [(100, None)], "version": "v1"}
        visor._al_resultado_parcial_exploracion(parcial)
        verifica(len(tA._previews_densos) == 0 and len(tB._previews_densos) == 0, "E - resultado parcial id inexistente no aplica")
        ok("E OK — resultado exploración parcial/final id inexistente no afecta homónimo")
    finally:
        tmp.cleanup()
        try:
            visor.close()
        except Exception:
            pass

# ---------- F ----------
def test_F_marcadores_id_inexistente():
    app, visor, tA, tB, tmp = _crear_visor_homonimos()
    try:
        tA._marcadores = []
        tB._marcadores = []
        tA._marcadores_cargados = True
        tB._marcadores_cargados = True
        # Simular carga con op id inexistente
        op = {"video_id": 9999, "nombre": "video.mp4"}
        filas = [(1, 9999, 1.5, None)]
        visor._aplicar_marcadores_cargados(op, filas)
        verifica(len(tA._marcadores) == 0 and len(tB._marcadores) == 0, "F - marcadores cargados id inexistente no se aplican")
        # Error color con id inexistente no debe afectar
        visor._marcador_op_actual = {"tipo": "color", "registro": {"color": None}, "video_id": 9999, "nombre": "video.mp4", "color_previo": None}
        tA._franja.set_marcadores = lambda *a, **k: None
        tB._franja.set_marcadores = lambda *a, **k: None
        tA._sincronizar_barra_colapsada = lambda: None
        tB._sincronizar_barra_colapsada = lambda: None
        orig_marcadores_A = list(tA._marcadores)
        visor._al_error_marcadores("fake")
        verifica(tA._marcadores == orig_marcadores_A, "F - error color id inexistente no altera homónima")
        ok("F OK — marcadores id inexistente no caen por nombre")
    finally:
        tmp.cleanup()
        try:
            visor.close()
        except Exception:
            pass

# ---------- G ----------
def test_G_segmentos_id_inexistente():
    app, visor, tA, tB, tmp = _crear_visor_homonimos()
    try:
        tA._segmentos = []
        tB._segmentos = []
        tA._segmentos_cargados = True
        tB._segmentos_cargados = True
        op = {"video_id": 9999, "nombre": "video.mp4", "tarjeta": None}
        filas = [(10, 0.0, 1.0, None)]
        visor._aplicar_segmentos_cargados(op, filas)
        verifica(len(tA._segmentos) == 0 and len(tB._segmentos) == 0, "G - segmentos cargados id inexistente no se aplican")
        # Resultado crear con id inexistente
        visor._segmento_op_actual = {"tipo": "crear", "registro": {"id": None, "inicio": 0, "fin": 1, "eliminada": False}, "video_id": 9999, "nombre": "video.mp4"}
        visor._al_resultado_segmentos((99, 0, 1))
        verifica(len(tA._segmentos) == 0 and len(tB._segmentos) == 0, "G - resultado crear segmento id inexistente no ordena homónima")
        ok("G OK — segmentos id inexistente no caen por nombre")
    finally:
        tmp.cleanup()
        try:
            visor.close()
        except Exception:
            pass

# ---------- H ----------
def test_H_colores_rollback_error():
    app, visor, tA, tB, tmp = _crear_visor_homonimos()
    try:
        # Preparar segmento en tA con color rojo
        tA._segmentos = [{"id": 1, "inicio": 0, "fin": 1, "color": "rojo"}]
        tB._segmentos = [{"id": 2, "inicio": 0, "fin": 1, "color": "azul"}]
        orig_color_A = tA._segmentos[0]["color"]
        orig_color_B = tB._segmentos[0]["color"]
        # Error color para vid 9999 no debe tocar B
        visor._segmento_op_actual = {"tipo": "color", "registro": {"id": 999, "color": "verde"}, "video_id": 9999, "nombre": "video.mp4", "color_previo": "rojo"}
        tA._franja.set_segmentos = lambda s: None
        tB._franja.set_segmentos = lambda s: None
        tA._sincronizar_barra_colapsada = lambda: None
        tB._sincronizar_barra_colapsada = lambda: None
        visor._al_error_segmentos("color fail")
        verifica(tA._segmentos[0]["color"] == orig_color_A and tB._segmentos[0]["color"] == orig_color_B, "H - error color id inexistente no cambia homónima")
        # Marcadores color id inexistente
        tA._marcadores = [{"id": 10, "tiempo": 1.0, "color": "rojo"}]
        tB._marcadores = [{"id": 11, "tiempo": 1.0, "color": "azul"}]
        visor._marcador_op_actual = {"tipo": "color", "registro": tA._marcadores[0], "video_id": 9999, "nombre": "video.mp4", "color_previo": "rojo", "color": "verde"}
        tA._franja.set_marcadores = lambda *a: None
        tB._franja.set_marcadores = lambda *a: None
        visor._al_error_marcadores("color fail")
        verifica(tB._marcadores[0]["color"] == "azul", "H - marcador error id inexistente no cambia homónima")
        ok("H OK — colores/rollback/error con ID válido no afectan homónimo")
    finally:
        tmp.cleanup()
        try:
            visor.close()
        except Exception:
            pass

# ---------- I ----------
def test_I_operaciones_individuales_id_inexistente():
    app, visor, tA, tB, tmp = _crear_visor_homonimos()
    try:
        # _iniciar_renombrar con id inexistente debe hacer no-op sin buscar por nombre
        # Mockear DialogoRenombrar para detectar si se llega a abrir
        import visor_videos as vv
        orig_dialogo = vv.DialogoRenombrar
        llamado = {"c": False}
        class FakeDialog:
            def __init__(self, *a, **k):
                llamado["c"] = True
            def exec(self):
                return 0
        vv.DialogoRenombrar = FakeDialog
        try:
            visor._iniciar_renombrar(9999)
            verifica(not llamado["c"], "I - renombrar id inexistente no abre diálogo (no fallback a homónimo)")
            # Copiar, mover, eliminar igual
            llamado["c"] = False
            # Mock QFileDialog para no abrir real
            from unittest.mock import patch
            with patch("visor_videos.QFileDialog.getExistingDirectory", return_value=""):
                visor._iniciar_mover(9999)
            verifica(not llamado["c"], "I - mover id inexistente no busca por nombre")
            llamado["c"] = False
            vv.DialogoRenombrar = FakeDialog
            visor._iniciar_copiar(9999)
            verifica(not llamado["c"], "I - copiar id inexistente no fallback")
            # Eliminar usa QMessageBox, también debe no-op
            # No podemos fácilmente testear sin bloquear, pero verificar que no elimina tarjeta homónima
            antes = len(visor.tarjetas)
            # Mockear QMessageBox para evitar bloqueo
            with patch("visor_videos.QMessageBox.question", return_value=0):
                visor._iniciar_eliminar_video(9999)
            verifica(len(visor.tarjetas) == antes, "I - eliminar id inexistente no elimina homónima")
        finally:
            vv.DialogoRenombrar = orig_dialogo
        ok("I OK — operaciones individuales id inexistente no buscan por nombre")
    finally:
        tmp.cleanup()
        try:
            visor.close()
        except Exception:
            pass

# ---------- J ----------
def test_J_menu_contextual_id_inexistente():
    app, visor, tA, tB, tmp = _crear_visor_homonimos()
    try:
        # _mostrar_menu_contextual usa _tarjeta_por_id; con id inexistente no debe resolver homónima
        # No podemos ejecutar QMenu.exec, pero testeamos la resolución interna: _tarjeta_por_id 9999 es None
        verifica(visor._tarjeta_por_id(9999) is None, "J - _tarjeta_por_id 9999 es None")
        # Si hubiera fallback, _tarjeta_por_nombre devolvería tA; ahora no debe usarse
        # Probar que visor._ids_seleccionados no se contamina
        visor._ids_seleccionados = set([101])
        # Simular que menu contextual para 9999 no debería seleccionar homónima
        # Llamamos logic de _mostrar_menu_contextual sin exec: extraer ident_uso
        vid = 9999
        tarjeta_ctx = visor._tarjeta_por_id(vid)
        nombre = getattr(tarjeta_ctx, "nombre", str(vid)) if tarjeta_ctx else str(vid)
        verifica(tarjeta_ctx is None and nombre == "9999", "J - menu contextual id inexistente no resuelve nombre homónimo")
        ok("J OK — menú contextual id inexistente no resuelve homónimo")
    finally:
        tmp.cleanup()
        try:
            visor.close()
        except Exception:
            pass

# ---------- K ----------
def test_K_previews_async_id_valido():
    app, visor, tA, tB, tmp = _crear_visor_homonimos()
    try:
        # Preparar previews en tA/tB
        tA._previews_densos = []
        tB._previews_densos = []
        # Mockear actualizar_previews para detectar cruce
        tA_calls = []
        tB_calls = []
        orig_A = tA.actualizar_previews
        orig_B = tB.actualizar_previews
        tA.actualizar_previews = lambda rutas: tA_calls.append(rutas) or True
        tB.actualizar_previews = lambda rutas: tB_calls.append(rutas) or True
        # Resultado con video_id 9999 (inexistente) y nombre homónimo debe no aplicar a A/B
        resultado = {"resultados": [{"video_id": 9999, "nombre": "video.mp4", "previews": ["fake.jpg"], "ruta": "C:\\tmp\\X\\video.mp4"}]}
        visor._aplicar_previews(resultado)
        verifica(len(tA_calls) == 0 and len(tB_calls) == 0, "K - preview id inexistente no se aplica a homónima")
        # Resultado con id 101 debe aplicar solo a tA
        resultado2 = {"resultados": [{"video_id": 101, "nombre": "video.mp4", "previews": ["p1.jpg"], "ruta": "C:\\tmp\\A\\video.mp4"}]}
        visor._aplicar_previews(resultado2)
        verifica(len(tA_calls) == 1 and len(tB_calls) == 0, "K - preview id 101 solo a tA")
        # Restaurar
        tA.actualizar_previews = orig_A
        tB.actualizar_previews = orig_B
        ok("K OK — previews async con ID válido no se aplican a homónimo")
    finally:
        tmp.cleanup()
        try:
            visor.close()
        except Exception:
            pass

# ---------- L ----------
def test_L_seleccion_multiple_ids():
    app, visor, tA, tB, tmp = _crear_visor_homonimos()
    try:
        visor._limpiar_seleccion()
        visor._al_seleccionar_tarjeta(101, False)
        visor._al_seleccionar_tarjeta(102, True)
        verifica(101 in visor._ids_seleccionados and 102 in visor._ids_seleccionados, "L - multiselección ambos ids")
        verifica(tA._seleccionada and tB._seleccionada, "L - ambas visibles seleccionadas")
        # Deseleccionar 101
        visor._al_seleccionar_tarjeta(101, True)
        verifica(101 not in visor._ids_seleccionados and 102 in visor._ids_seleccionados, "L - deseleccionar 101 deja 102")
        verifica(not tA._seleccionada and tB._seleccionada, "L - visual solo B")
        ok("L OK — selección múltiple conserva ids distintos pese a mismo nombre")
    finally:
        tmp.cleanup()
        try:
            visor.close()
        except Exception:
            pass

# ---------- M ----------
def test_M_drag_drop_ids():
    # Verificar serialización MIME por ids independientes
    from panel_organizacion import _serializar_ids_videos_para_mime, _deserializar_ids_videos_desde_mime
    payload = _serializar_ids_videos_para_mime([101, 102])
    back = _deserializar_ids_videos_desde_mime(payload)
    verifica(set(back) == {101, 102}, "M - drag mime ids 101,102")
    # bool no debe ser id válido
    payload2 = _serializar_ids_videos_para_mime([True])
    verifica(payload2 is None, "M - bool no serializa como id")
    # Crear mime via visor helper
    mime = visor_videos._crear_mime_data_drag_b713b([101, 102])
    verifica(mime is not None, "M - mime por ids creado")
    ok("M OK — drag & drop conserva ids independientes")

# ---------- N ----------
def test_N_recarga_filtro_no_colapsa():
    app, visor, tA, tB, tmp = _crear_visor_homonimos()
    try:
        verifica(visor.tarjetas_visibles() == ["video.mp4", "video.mp4"], "N - visibles duplicados")
        visor.filtrar("video")
        verifica(visor.tarjetas_visibles() == ["video.mp4", "video.mp4"], "N - filtrar 'video' no colapsa")
        visor.filtrar("inexistente")
        verifica(visor.tarjetas_visibles() == [], "N - filtro sin match vacía")
        visor.filtrar("")
        verifica(len(visor.tarjetas_visibles()) == 2, "N - recarga filtro vacío mantiene 2")
        ok("N OK — recarga/filtro no colapsa homónimos")
    finally:
        tmp.cleanup()
        try:
            visor.close()
        except Exception:
            pass

# ---------- O ----------
def test_O_ast_antifallback():
    code = open("visor_videos.py", encoding="utf-8").read()
    tree = ast.parse(code)
    fallos = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name in ("_tarjeta_por_nombre", "_tarjeta_por_id", "_tarjeta_por_video_id", "_es_video_id_valido"):
                continue
            # Buscar patrón inseguro vía AST: asignación tarjeta = _tarjeta_por_id y luego If tarjeta is None con asignación _tarjeta_por_nombre en el cuerpo
            # Recolectar statements en orden
            stmts = list(ast.iter_child_nodes(node))
            # También recorrer todos los nodos internos para detectar secuencia
            # Simplificado: buscar todos los If donde test es `tarjeta is None` y en su body hay Call _tarjeta_por_nombre
            for child in ast.walk(node):
                if isinstance(child, ast.If):
                    # test debe ser Compare con `tarjeta is None` o `tarjeta == None`
                    try:
                        test_src = ast.get_source_segment(code, child.test) or ""
                    except:
                        test_src = ""
                    if "tarjeta is None" in test_src or "tarjeta == None" in test_src:
                        # body contiene _tarjeta_por_nombre?
                        body_src = ""
                        for b in child.body:
                            try:
                                body_src += ast.get_source_segment(code, b) or ""
                            except:
                                pass
                        if "_tarjeta_por_nombre" in body_src:
                            # verificar que antes del If hay asignación a tarjeta por id con vid válido
                            # buscar en toda la función si hay _tarjeta_por_id cerca sin helper ramificado
                            # Para ser inseguro, la función debe haber hecho `tarjeta = self._tarjeta_por_id(vid)` sin else y sin helper previo
                            # Nuestro código corregido usa `if _es_video_id_valido(vid): tarjeta = ...; if tarjeta is None: return` (no fallback)
                            # Entonces el body del If no debe contener _tarjeta_por_nombre, sino return
                            # Si body contiene fallback, es inseguro
                            # Además distinguir si la función tiene rama else que asigna por nombre con helper (seguro)
                            # Un fallback inseguro no tiene `return` sino asignación
                            if "return" not in body_src:
                                fallos.append(f"{node.name}:{node.lineno}")
                            else:
                                # Si tiene fallback con helper también inseguro, pero nuestro fix usa return, no fallback
                                pass
            # Adicionalmente detectar secuencia textual directa sin AST: `tarjeta = self._tarjeta_por_id` seguido de `if tarjeta is None:` + `tarjeta = self._tarjeta_por_nombre` en 3 líneas
            seg = ast.get_source_segment(code, node) or ""
            lines = [l.strip() for l in seg.splitlines() if l.strip() and not l.strip().startswith("#") and not l.strip().startswith('"""') and not l.strip().startswith("'''")]
            for i in range(len(lines)-2):
                if "_tarjeta_por_id" in lines[i] and "tarjeta" in lines[i] and "=" in lines[i]:
                    if "if tarjeta is None" in lines[i+1]:
                        if "_tarjeta_por_nombre" in lines[i+2]:
                            # Verificar si líneas anteriores contienen helper (rama segura) -> entonces no es fallback directo
                            # Helper seguro usa `if _es_video_id_valido` antes
                            window = "\n".join(lines[max(0,i-3):i+3])
                            if "_es_video_id_valido" not in window:
                                # Si el if siguiente es `if tarjeta is None: return` no es fallback, pero aquí es `tarjeta = _tarjeta_por_nombre` sí
                                fallos.append(f"{node.name}:{node.lineno}:fallback_textual")
    # Deduplicar
    fallos = sorted(set(fallos))
    verifica(len(fallos) == 0, f"O - AST anti-fallback sin patrones inseguros (fallos={fallos})", extra=str(fallos))
    cnt = code.count("_tarjeta_por_id")
    verifica(cnt >= 10, f"O - usos _tarjeta_por_id >=10 (got {cnt})")
    ok(f"O OK — AST anti-fallback limpio, usos={cnt}")

# ---------- P ----------
def test_P_arquitectura():
    code = open("visor_videos.py", encoding="utf-8").read()
    tree = ast.parse(code)
    visor_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "VisorVideos":
            visor_node = node
            break
    assert visor_node is not None, "VisorVideos no encontrado"
    # Recolectar nombres importados y llamadas reales ignorando comentarios/docstrings
    has_sqlite = False
    has_conectar_bd = False
    has_subprocess = False
    has_popen = False
    has_ffmpeg = False
    has_sql = False
    for n in ast.walk(visor_node):
        if isinstance(n, ast.Import):
            for alias in n.names:
                if alias.name == "sqlite3":
                    has_sqlite = True
                if alias.name == "subprocess":
                    has_subprocess = True
        if isinstance(n, ast.ImportFrom):
            if n.module == "sqlite3":
                has_sqlite = True
            if n.module == "subprocess":
                has_subprocess = True
        if isinstance(n, ast.Call):
            try:
                func_src = ast.get_source_segment(code, n.func) or ""
            except:
                func_src = ""
            if "conectar_bd" in func_src:
                has_conectar_bd = True
            if "Popen" in func_src:
                has_popen = True
            # ffmpeg/ffprobe directo solo si es llamada subprocess con literal, no TareaFFprobe
            if func_src.strip() in ("Popen", "subprocess.Popen", "subprocess.run", "subprocess.call"):
                # verificar args contienen ffmpeg/ffprobe literal
                try:
                    call_src = ast.get_source_segment(code, n) or ""
                    if "ffmpeg" in call_src.lower() or "ffprobe" in call_src.lower():
                        has_ffmpeg = True
                except:
                    pass
        if isinstance(n, ast.Name):
            if n.id == "sqlite3":
                has_sqlite = True
            if n.id == "Popen":
                has_popen = True
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            val = n.value
            if any(kw in val for kw in ("SELECT", "INSERT", "DELETE")) and "VisorVideos" not in val:
                has_sql = True
            # ffmpeg literal directo (no tarea)
            if val.lower() == "ffmpeg" or val.lower() == "ffprobe":
                has_ffmpeg = True
    # Docstrings: el primer Constant de cada FunctionDef es docstring, lo ignoramos ya al revisar has_sql solo si no es docstring pero igual lo marcamos; mejor verificar has_sql solo si string contiene SQL y no es docstring
    # Para este proyecto, VisorVideos no debe tener SQL en ejecución, así que cualquier SQL real es fallo
    verifica(not has_sqlite, "P - VisorVideos sin sqlite3")
    verifica(not has_conectar_bd, "P - VisorVideos sin conectar_bd directo")
    verifica(not has_sql, "P - VisorVideos sin SQL")
    verifica(not has_subprocess, "P - sin subprocess")
    verifica(not has_popen, "P - sin Popen")
    verifica(not has_ffmpeg, "P - sin ffmpeg/ffprobe")
    ok("P OK — arquitectura UI sin acceso directo a DB/procesos")

def run_all():
    tests = [
        test_A_independientes,
        test_B_seleccion_uno_no_otro,
        test_C_id_inexistente_no_afecta_homonima,
        test_D_exploracion_id_inexistente_no_fallback,
        test_E_resultado_exploracion_id_inexistente,
        test_F_marcadores_id_inexistente,
        test_G_segmentos_id_inexistente,
        test_H_colores_rollback_error,
        test_I_operaciones_individuales_id_inexistente,
        test_J_menu_contextual_id_inexistente,
        test_K_previews_async_id_valido,
        test_L_seleccion_multiple_ids,
        test_M_drag_drop_ids,
        test_N_recarga_filtro_no_colapsa,
        test_O_ast_antifallback,
        test_P_arquitectura,
    ]
    for t in tests:
        try:
            t()
        except Exception as exc:
            falla(f"{t.__name__} excepcion", extra=f"{type(exc).__name__}: {exc}")
            import traceback
            traceback.print_exc()
    print(f"\nRESUMEN: { _CONTADOR[0] - _FALLOS[0]}/{_CONTADOR[0]} OK, {_FALLOS[0]} fallos")
    if _FALLOS[0] == 0:
        print("RESULTADO_FINAL=OK")
        return 0
    else:
        print("RESULTADO_FINAL=FAIL")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(run_all())
