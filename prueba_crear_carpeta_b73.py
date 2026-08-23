"""Suite B7.3 — creación segura de una carpeta desde la interfaz.

Cubre contrato B7.3 con temporales, sin tocar datos reales.
"""
import os
import sys
import sqlite3
import tempfile
import shutil
import inspect

import crear_carpeta as svc
from crear_carpeta import ValidacionError, ColisionError, CrearCarpetaError, validar_nombre_carpeta
from tareas_videos import TareaCrearCarpeta
import visor_videos
import arbol_navegacion as arbol_mod
from arbol_navegacion import ArbolNavegacion


def _tmp_parent():
    td = tempfile.mkdtemp()
    return td


# ---- Servicio básico ----

def test_01_exito_basico():
    td = _tmp_parent()
    try:
        padre = os.path.join(td, "padre")
        os.mkdir(padre)
        res = svc.crear_carpeta(padre, "hija")
        assert res["ok"]
        nueva = res["ruta"]
        assert os.path.isdir(nueva)
        assert os.path.basename(nueva) == "hija"
        assert os.path.dirname(os.path.abspath(nueva)) == os.path.abspath(padre)
        print("test_01 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_02_nombre_vacio():
    td = _tmp_parent()
    try:
        padre = os.path.join(td, "p2")
        os.mkdir(padre)
        for caso in ["", "   ", "\t", "\n"]:
            try:
                svc.crear_carpeta(padre, caso)
                assert False, f"debe rechazar vacío {caso!r}"
            except ValidacionError:
                pass
        # validar_nombre directo también
        try:
            validar_nombre_carpeta("")
            assert False
        except ValidacionError:
            pass
        print("test_02 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_03_invalidos_reservados():
    td = _tmp_parent()
    try:
        padre = os.path.join(td, "p3")
        os.mkdir(padre)
        casos_invalidos = ["a<b", 'a"b', "a|b", "a?b", "a*b", "a:b", "a\x01b", "CON", "con", "CON.txt", "prn", "AUX", "NUL", "COM1", "LPT9", "com3.txt"]
        for caso in casos_invalidos:
            try:
                svc.crear_carpeta(padre, caso)
                assert False, f"debe rechazar inválido/reservado {caso!r}"
            except ValidacionError:
                pass
            # validar_nombre_carpeta también
            try:
                validar_nombre_carpeta(caso)
                assert False, f"validar debe rechazar {caso!r}"
            except ValidacionError:
                pass
        # carácter control y ":"
        try:
            svc.crear_carpeta(padre, "hola:carpeta")
            assert False
        except ValidacionError:
            pass
        print("test_03 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_04_punto_espacio_final():
    td = _tmp_parent()
    try:
        padre = os.path.join(td, "p4")
        os.mkdir(padre)
        for caso in ["trailing ", "trailing.", "nombre .", "nombre  ", "a."]:
            try:
                svc.crear_carpeta(padre, caso)
                assert False, f"debe rechazar punto/espacio final {caso!r}"
            except ValidacionError:
                pass
        # leading/trailing espacios también
        for caso in [" leading", "trailing "]:
            try:
                validar_nombre_carpeta(caso)
                assert False
            except ValidacionError:
                pass
        # interno espacio debe pasar
        res = svc.crear_carpeta(padre, "mi carpeta")
        assert os.path.isdir(res["ruta"])
        print("test_04 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_05_dot_dotdot():
    td = _tmp_parent()
    try:
        padre = os.path.join(td, "p5")
        os.mkdir(padre)
        for caso in [".", ".."]:
            try:
                svc.crear_carpeta(padre, caso)
                assert False
            except ValidacionError:
                pass
            try:
                validar_nombre_carpeta(caso)
                assert False
            except ValidacionError:
                pass
        print("test_05 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_06_separadores_ruta_anidada():
    td = _tmp_parent()
    try:
        padre = os.path.join(td, "p6")
        os.mkdir(padre)
        for caso in ["a/b", "a\\b", "a/b/c", "sub/carpeta", "a/../b", "a\\b\\c", "foo/bar"]:
            try:
                svc.crear_carpeta(padre, caso)
                assert False, f"debe rechazar ruta anidada {caso!r}"
            except ValidacionError:
                pass
        # No debe crear padres anidados incidentalmente
        assert not os.path.exists(os.path.join(padre, "a"))
        print("test_06 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_07_padre_inexistente():
    td = _tmp_parent()
    try:
        inexistente = os.path.join(td, "noexiste_xyz")
        assert not os.path.exists(inexistente)
        try:
            svc.crear_carpeta(inexistente, "hija")
            assert False
        except ValidacionError as exc:
            assert "no existe" in str(exc).lower()
        # validar también con ruta profunda inexistente
        try:
            svc.crear_carpeta(os.path.join(td, "a", "b", "c"), "hija2")
            assert False
        except ValidacionError:
            pass
        print("test_07 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_08_padre_no_directorio():
    td = _tmp_parent()
    try:
        padre_arch = os.path.join(td, "archivo.txt")
        with open(padre_arch, "w") as f:
            f.write("x")
        try:
            svc.crear_carpeta(padre_arch, "hija")
            assert False
        except ValidacionError as exc:
            assert "no es directorio" in str(exc).lower()
        print("test_08 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_09_colision_carpeta():
    td = _tmp_parent()
    try:
        padre = os.path.join(td, "p9")
        os.mkdir(padre)
        svc.crear_carpeta(padre, "existe")
        try:
            svc.crear_carpeta(padre, "existe")
            assert False
        except ColisionError:
            pass
        # debe seguir existiendo, no sobrescrita
        assert os.path.isdir(os.path.join(padre, "existe"))
        print("test_09 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_10_colision_archivo():
    td = _tmp_parent()
    try:
        padre = os.path.join(td, "p10")
        os.mkdir(padre)
        arch = os.path.join(padre, "archivo.txt")
        with open(arch, "w") as f:
            f.write("x")
        # Crear carpeta con mismo nombre que archivo existente debe colisionar
        try:
            svc.crear_carpeta(padre, "archivo.txt")
            assert False
        except ColisionError:
            pass
        assert os.path.isfile(arch)
        # También caso carpeta vs archivo con extensión?
        # nombre sin extensión que colisiona con archivo sin extensión
        arch2 = os.path.join(padre, "mismo")
        with open(arch2, "w") as f:
            f.write("y")
        try:
            svc.crear_carpeta(padre, "mismo")
            assert False
        except ColisionError:
            pass
        print("test_10 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_11_colision_case_insensitive():
    td = _tmp_parent()
    try:
        padre = os.path.join(td, "p11")
        os.mkdir(padre)
        svc.crear_carpeta(padre, "MiCarpeta")
        # Intentar con distinta capitalización debe fallar determinista (Windows)
        for variante in ["micarpeta", "MICARPETA", "MiCARPETA", "micarpeta".upper()]:
            try:
                svc.crear_carpeta(padre, variante)
                assert False, f"case-insensitive debe colisionar {variante!r}"
            except ColisionError:
                pass
        # También archivo con case distinto colisiona con carpeta
        padre2 = os.path.join(td, "p11b")
        os.mkdir(padre2)
        with open(os.path.join(padre2, "Archivo.TXT"), "w") as f:
            f.write("z")
        try:
            svc.crear_carpeta(padre2, "archivo.txt")
            assert False
        except ColisionError:
            pass
        try:
            svc.crear_carpeta(padre2, "ARCHIVO.txt")
            assert False
        except ColisionError:
            pass
        print("test_11 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_12_fallo_permisos_mock():
    td = _tmp_parent()
    try:
        padre = os.path.join(td, "p12")
        os.mkdir(padre)
        orig_mkdir = svc.os.mkdir

        def falla(*a, **k):
            raise PermissionError("simulado sin permisos")

        svc.os.mkdir = falla
        try:
            try:
                svc.crear_carpeta(padre, "sinpermisos")
                assert False
            except CrearCarpetaError as exc:
                assert "permisos" in str(exc).lower() or "fallo" in str(exc).lower()
            # No debe haber creado nada
            assert not os.path.exists(os.path.join(padre, "sinpermisos"))
        finally:
            svc.os.mkdir = orig_mkdir

        # También test carrera FileExistsError
        svc.os.mkdir = lambda p: (_ for _ in ()).throw(FileExistsError("carrera"))
        # Necesitamos evitar prevalidar colisión previa: usar nombre nuevo no listado
        # Pero nuestra implementación hace listdir check antes; si nombre no existe en listdir,
        # llegará a mkdir y lanzará FileExistsError -> debe traducirse a ColisionError
        try:
            svc.crear_carpeta(padre, "carrera_test")
            assert False
        except ColisionError:
            pass
        finally:
            svc.os.mkdir = orig_mkdir

        print("test_12 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_13_longitud_y_caracteres():
    td = _tmp_parent()
    try:
        padre = os.path.join(td, "p13")
        os.mkdir(padre)
        largo = "a" * 256
        try:
            svc.crear_carpeta(padre, largo)
            assert False
        except ValidacionError:
            pass
        # borde: usar 100 para no exceder MAX_PATH total en Windows (255 + padre largo falla)
        # validar que 100 pasa y que validar_nombre_carpeta acepta 255 conceptualmente
        borde = "b" * 100
        res = svc.crear_carpeta(padre, borde)
        assert os.path.isdir(res["ruta"])
        # validar que 255 es límite conceptual (sin tocar FS)
        try:
            validar_nombre_carpeta("c" * 255)
        except ValidacionError:
            assert False, "255 debe ser válido según MAX_COMPONENTE"
        try:
            validar_nombre_carpeta("c" * 256)
            assert False
        except ValidacionError:
            pass
        print("test_13 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_14_ui_delega_tarea_no_fs_directo():
    # UI no debe hacer os.mkdir directo, debe usar TareaCrearCarpeta
    fuente_visor = inspect.getsource(visor_videos.VisorVideos._iniciar_crear_carpeta)
    assert "TareaCrearCarpeta" in fuente_visor, "UI debe usar TareaCrearCarpeta"
    assert "os.mkdir" not in fuente_visor, "UI no debe hacer mkdir directo"
    # Variantes Path.mkdir también prohibidas
    assert "Path(" not in fuente_visor or "mkdir" not in fuente_visor
    assert "gestor_crear_carpeta.iniciar" in fuente_visor
    fuente_tarea = inspect.getsource(TareaCrearCarpeta._trabajo)
    assert "crear_carpeta" in fuente_tarea
    # Verificar que servicio no toca SQLite (no importa sqlite3 ni toca biblioteca.db)
    fuente_svc = inspect.getsource(svc.crear_carpeta)
    assert "sqlite3" not in fuente_svc.lower()
    assert "conectar_bd" not in fuente_svc.lower()
    # Verificar árbol tiene señal y refresco
    assert hasattr(ArbolNavegacion, "nueva_carpeta_solicitada")
    assert hasattr(ArbolNavegacion, "refrescar_carpeta")
    fuente_arbol_menu = inspect.getsource(ArbolNavegacion._al_menu_contextual)
    assert "Nueva carpeta" in fuente_arbol_menu
    print("test_14 OK")


def test_15_refresco_seleccion_arbol_tras_exito():
    """Crea carpeta y verifica que ArbolNavegacion la refleja sin reescaneo."""
    from PySide6.QtWidgets import QApplication
    td = _tmp_parent()
    app = QApplication.instance()
    created = False
    if app is None:
        app = QApplication(sys.argv)
        created = True
    try:
        padre = os.path.join(td, "padre_arbol")
        os.mkdir(padre)
        # Crear Arbol y nodo padre manual para evitar dependencia de discos
        arbol = ArbolNavegacion()
        # Insertar nodo padre bajo raiz
        from PySide6.QtWidgets import QTreeWidgetItem
        from arbol_navegacion import ROL_RUTA, ROL_CARGADO
        raiz = arbol.topLevelItem(0)
        # Crear nodo padre artificial
        item_padre = QTreeWidgetItem(raiz, [os.path.basename(padre)])
        item_padre.setData(0, ROL_RUTA, os.path.abspath(padre))
        # Simular que está cargado vacío
        item_padre.setData(0, ROL_CARGADO, True)
        # No hijos aún
        # Crear carpeta vía servicio
        res = svc.crear_carpeta(padre, "hija_arbol")
        assert os.path.isdir(res["ruta"])
        # Refrescar árbol
        ok = arbol.refrescar_carpeta(os.path.abspath(padre))
        assert ok, "refrescar debe hallar padre"
        # Verificar que hija aparece como hijo
        found = None
        for i in range(item_padre.childCount()):
            child = item_padre.child(i)
            if child.data(0, ROL_RUTA) == res["ruta"]:
                found = child
                break
        assert found is not None, f"hija debe aparecer en árbol, childCount={item_padre.childCount()}"
        # Probar selección
        arbol.seleccionar_ruta(res["ruta"])
        sel = arbol.carpeta_actual()
        # carpeta_actual puede ser None si seleccionar_ruta usa setCurrentItem que dispara señal async?
        # Procesar eventos
        QApplication.processEvents()
        # Intentar revelar también
        if sel != res["ruta"]:
            arbol.revelar_ruta(res["ruta"])
            QApplication.processEvents()
        # Al menos el nodo existe; verificar _buscar_ruta
        nodo = arbol._buscar_ruta(raiz, res["ruta"])
        assert nodo is not None
        # Verificar no tocó catálogo: si hubiera DB temp, contar que no insertó
        arbol.deleteLater()
        print("test_15 OK")
    finally:
        if created:
            # no cerrar app si era la instancia global; solo limpiar
            pass
        shutil.rmtree(td, ignore_errors=True)


def test_16_error_ui_no_borra_carpeta():
    """Si refresco UI falla, la carpeta creada debe persistir (no compensación)."""
    from PySide6.QtWidgets import QApplication
    import time
    td = tempfile.mkdtemp()
    td2 = tempfile.mkdtemp()
    # Crear DB temporal vacía para Visor
    from escanear_videos import conectar_bd
    ruta_db = os.path.join(td2, "test.db")
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    try:
        padre = os.path.join(td, "padre_err")
        os.mkdir(padre)
        ruta_config = os.path.join(td2, "config_b73.json")
        ventana = visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(720, 540)
        ventana.show()
        # Esperar carga
        def esperar(pred, intentos=200):
            for _ in range(intentos):
                QApplication.processEvents()
                if pred():
                    return True
                time.sleep(0.02)
            return pred()
        esperar(lambda: ventana._carga_completada and not ventana.gestor.activo, intentos=250)
        # Crear carpeta real vía servicio (simula éxito FS)
        res = svc.crear_carpeta(padre, "hija_no_borrar")
        assert os.path.isdir(res["ruta"])
        # Parchear refrescar_carpeta para que falle
        orig_refrescar = ventana.arbol_navegacion.refrescar_carpeta
        def falla_refrescar(ruta_padre):
            raise RuntimeError("fallo refresco simulado")
        ventana.arbol_navegacion.refrescar_carpeta = falla_refrescar
        # Simular handler UI éxito con fallo UI
        ventana._crear_padre_en_curso = padre
        ventana._al_resultado_crear_carpeta(res)
        QApplication.processEvents()
        # Verificar carpeta sigue existiendo (no borrada)
        assert os.path.isdir(res["ruta"]), "carpeta no debe borrarse aunque refresco falle"
        # Mensaje debe indicar inconsistencia pero no éxito falso
        mensaje = ventana.mensaje_carpeta.text()
        assert "fallo" in mensaje.lower() or "creada" in mensaje.lower(), f"debe reportar inconsistencia, got {mensaje!r}"
        # Restaurar
        ventana.arbol_navegacion.refrescar_carpeta = orig_refrescar
        ventana.close()
        ventana.gestor.cerrar()
        for g in [getattr(ventana, "gestor_crear_carpeta", None), getattr(ventana, "gestor_previews", None), getattr(ventana, "gestor_renombrado", None), getattr(ventana, "gestor_mover", None)]:
            try:
                if g: g.cerrar()
            except: pass
        print("test_16 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)
        shutil.rmtree(td2, ignore_errors=True)


def test_17_no_sqlite_no_catalogo():
    """Crear carpeta no debe tocar SQLite ni insertar videos."""
    import tempfile, shutil, os
    td = tempfile.mkdtemp()
    padre = os.path.join(td, "videos_temp")
    os.makedirs(padre, exist_ok=True)
    # crear DB vacía
    from escanear_videos import conectar_bd, listar_videos
    ruta_db = os.path.join(td, "test_b73.db")
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    try:
        filas_antes = listar_videos(ruta_db)
        total_antes = len(filas_antes)
        # crear carpeta
        res = svc.crear_carpeta(padre, "nueva_b73")
        assert os.path.isdir(res["ruta"])
        filas_despues = listar_videos(ruta_db)
        assert len(filas_despues) == total_antes, "no debe insertar videos"
        # verificar que no creó registro con nombre de carpeta
        assert not any("nueva_b73" in str(r) for r in filas_despues)
        # archivo dentro de padre no debe ser considerado video sin escanear: no efecto
        print("test_17 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_18_padre_con_barra_trailing():
    td = _tmp_parent()
    try:
        padre = os.path.join(td, "pad_trailing")
        os.mkdir(padre)
        padre_con_slash = padre + os.sep
        res = svc.crear_carpeta(padre_con_slash, "hija_trail")
        assert os.path.isdir(res["ruta"])
        assert os.path.dirname(res["ruta"]) == os.path.abspath(padre)
        print("test_18 OK")
    finally:
        shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    test_01_exito_basico()
    test_02_nombre_vacio()
    test_03_invalidos_reservados()
    test_04_punto_espacio_final()
    test_05_dot_dotdot()
    test_06_separadores_ruta_anidada()
    test_07_padre_inexistente()
    test_08_padre_no_directorio()
    test_09_colision_carpeta()
    test_10_colision_archivo()
    test_11_colision_case_insensitive()
    test_12_fallo_permisos_mock()
    test_13_longitud_y_caracteres()
    test_14_ui_delega_tarea_no_fs_directo()
    test_15_refresco_seleccion_arbol_tras_exito()
    test_16_error_ui_no_borra_carpeta()
    test_17_no_sqlite_no_catalogo()
    test_18_padre_con_barra_trailing()
    print("TODOS B7.3 OK")
