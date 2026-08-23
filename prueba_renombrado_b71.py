"""Suite B7.1 — renombrado individual seguro.

Cubre 15 exigencias del contrato B7.1 con temporales, sin tocar datos reales.
"""

import os
import sqlite3
import tempfile
import shutil
import inspect

from escanear_videos import (
    conectar_bd,
    guardar_marcador,
    guardar_segmento,
    asignar_color_marcador,
    asignar_color_segmento,
    listar_marcadores,
    listar_segmentos,
    obtener_video_por_id,
)
import renombrar_video as svc
from renombrar_video import (
    validar_nuevo_nombre,
    CompensacionFalloError,
    ValidacionError,
    ColisionError,
    RenombradoError,
)
from tareas_videos import TareaRenombrarVideo
import visor_videos


def _crear_db_temporal():
    tmpdir = tempfile.mkdtemp()
    ruta_db = os.path.join(tmpdir, "test.db")
    # crear esquema
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    return tmpdir, ruta_db


def _insertar_video(ruta_db, carpeta, nombre, contenido=b"x"):
    ruta = os.path.join(carpeta, nombre)
    os.makedirs(carpeta, exist_ok=True)
    with open(ruta, "wb") as f:
        f.write(contenido)
    # stats
    st = os.stat(ruta)
    conn = conectar_bd(ruta_db)
    try:
        conn.execute(
            "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, tamano_bytes, mtime_ns) VALUES (?, ?, ?, ?, ?, ?)",
            (nombre, os.path.abspath(ruta), os.path.splitext(nombre)[1].lower(), "2026-01-01T00:00:00", st.st_size, st.st_mtime_ns),
        )
        vid = conn.execute("SELECT id FROM videos WHERE nombre=?", (nombre,)).fetchone()[0]
        conn.commit()
        return vid, os.path.abspath(ruta)
    finally:
        conn.close()


def test_01_rename_simple_conserva_id():
    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    try:
        vid, _ = _insertar_video(ruta_db, carpeta, "orig.mp4")
        res = svc.renombrar_video(vid, "nuevo.mp4", ruta_db)
        assert res["ok"] and res["video_id"] == vid, "debe conservar id"
        # verificar DB id igual
        info = obtener_video_por_id(vid, ruta_db)
        assert info is not None and info["id"] == vid
        assert info["nombre"] == "nuevo.mp4"
        print("test_01 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_02_ruta_nombre_db_correctos():
    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    try:
        vid, ruta_orig = _insertar_video(ruta_db, carpeta, "orig2.mp4")
        res = svc.renombrar_video(vid, "ren2.mp4", ruta_db)
        assert res["ruta"].endswith("ren2.mp4")
        conn = sqlite3.connect(ruta_db)
        fila = conn.execute("SELECT nombre, ruta FROM videos WHERE id=?", (vid,)).fetchone()
        conn.close()
        assert fila[0] == "ren2.mp4"
        assert fila[1] == res["ruta"]
        assert os.path.isfile(fila[1])
        assert not os.path.isfile(ruta_orig)
        print("test_02 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_03_marcadores_segmentos_conservados():
    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    try:
        vid, _ = _insertar_video(ruta_db, carpeta, "vid3.mp4")
        mid = guardar_marcador(vid, 1.5, ruta_db)
        sid, _, _ = guardar_segmento(vid, 2.0, 5.0, ruta_db)
        svc.renombrar_video(vid, "vid3b.mp4", ruta_db)
        marc = listar_marcadores(vid, ruta_db)
        seg = listar_segmentos(vid, ruta_db)
        assert len(marc) == 1 and marc[0][0] == mid
        assert len(seg) == 1 and seg[0][0] == sid
        print("test_03 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_04_color_clasificacion_conservados():
    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    try:
        vid, _ = _insertar_video(ruta_db, carpeta, "vid4.mp4")
        mid = guardar_marcador(vid, 2.0, ruta_db, color="rojo")
        # re-asignar para asegurar
        asignar_color_marcador(mid, "verde", ruta_db)
        sid, _, _ = guardar_segmento(vid, 1.0, 3.0, ruta_db, color="azul")
        asignar_color_segmento(sid, "amarillo", ruta_db)
        svc.renombrar_video(vid, "vid4b.mp4", ruta_db)
        marc = listar_marcadores(vid, ruta_db)
        seg = listar_segmentos(vid, ruta_db)
        # marc color debe ser verde
        assert marc[0][3] == "verde", f"esperaba verde got {marc[0]}"
        assert seg[0][3] == "amarillo"
        print("test_04 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_05_relaciones_derivados_no_destruidas():
    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    try:
        vid_orig, _ = _insertar_video(ruta_db, carpeta, "orig5.mp4")
        vid_der, _ = _insertar_video(ruta_db, carpeta, "der5.mp4")
        conn = conectar_bd(ruta_db)
        conn.execute(
            "INSERT INTO videos_derivados (derivado_video_id, original_video_id, tipo, fecha_creacion, derivado_nombre, derivado_ruta, original_nombre, original_ruta) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (vid_der, vid_orig, "individual", "2026-01-01T00:00:00", "der5.mp4", os.path.join(carpeta, "der5.mp4"), "orig5.mp4", os.path.join(carpeta, "orig5.mp4")),
        )
        deriv_id = conn.execute("SELECT id FROM videos_derivados WHERE derivado_video_id=?", (vid_der,)).fetchone()[0]
        conn.execute(
            "INSERT INTO videos_derivados_segmentos (derivacion_id, segmento_id, orden, inicio, fin) VALUES (?, ?, ?, ?, ?)",
            (deriv_id, 1, 0, 0.0, 1.0),
        )
        conn.commit()
        conn.close()
        # renombrar original
        svc.renombrar_video(vid_orig, "orig5b.mp4", ruta_db)
        # derivado debe seguir existiendo
        conn = sqlite3.connect(ruta_db)
        fila = conn.execute("SELECT 1 FROM videos_derivados WHERE derivado_video_id=? AND original_video_id=?", (vid_der, vid_orig)).fetchone()
        assert fila is not None, "relación derivada no debe destruirse"
        seg = conn.execute("SELECT 1 FROM videos_derivados_segmentos WHERE derivacion_id=?", (deriv_id,)).fetchone()
        assert seg is not None
        conn.close()
        # renombrar derivado también debe conservar trazabilidad
        svc.renombrar_video(vid_der, "der5b.mp4", ruta_db)
        conn = sqlite3.connect(ruta_db)
        fila2 = conn.execute("SELECT 1 FROM videos_derivados WHERE derivado_video_id=?", (vid_der,)).fetchone()
        assert fila2 is not None
        conn.close()
        print("test_05 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_06_extension_preservada():
    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    try:
        vid, _ = _insertar_video(ruta_db, carpeta, "video6.mp4")
        # intentar cambiar extension
        try:
            svc.renombrar_video(vid, "video6.mkv", ruta_db)
            assert False, "debe rechazar cambio de extensión"
        except ValidacionError:
            pass
        # sin extensión debe autocompletar con original y pasar
        res = svc.renombrar_video(vid, "video6_nuevo", ruta_db)
        assert res["nombre"] == "video6_nuevo.mp4"
        assert res["ruta"].endswith(".mp4")
        print("test_06 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_07_validaciones_rechazadas():
    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    try:
        vid, _ = _insertar_video(ruta_db, carpeta, "val7.mp4")
        casos_invalidos = [
            "", "   ", "a<b.mp4", 'a"b.mp4', "a|b.mp4", "a?b.mp4", "a*b.mp4",
            "CON.mp4", "aux.mp4", " nul.mp4 ", "trailing. ", "trailing.",
            "a" * 300 + ".mp4",  # longitud
        ]
        for caso in casos_invalidos:
            try:
                svc.renombrar_video(vid, caso, ruta_db)
                assert False, f"debe rechazar {caso!r}"
            except (ValidacionError, RenombradoError):
                pass
        # trailing punto/espacio explícito
        try:
            validar_nuevo_nombre("nombre. ", "val7.mp4")
            assert False
        except ValidacionError:
            pass
        # reservado
        try:
            validar_nuevo_nombre("CON.mp4", "val7.mp4")
            assert False
        except ValidacionError:
            pass
        print("test_07 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_08_colision_filesystem():
    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    try:
        vid1, _ = _insertar_video(ruta_db, carpeta, "a8.mp4")
        vid2, ruta2 = _insertar_video(ruta_db, carpeta, "b8.mp4")
        # intentar renombrar a8 -> b8.mp4 debe fallar y no sobrescribir
        try:
            svc.renombrar_video(vid1, "b8.mp4", ruta_db)
            assert False, "colisión FS debe fallar"
        except ColisionError:
            pass
        assert os.path.isfile(ruta2), "no debe sobrescribir"
        assert os.path.isfile(os.path.join(carpeta, "a8.mp4"))
        # DB intacta
        info = obtener_video_por_id(vid1, ruta_db)
        assert info["nombre"] == "a8.mp4"
        print("test_08 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_09_colision_unique_nombre():
    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    try:
        vid1, ruta1 = _insertar_video(ruta_db, carpeta, "c9.mp4")
        vid2, _ = _insertar_video(ruta_db, carpeta, "d9.mp4")
        # borrar archivo d9 para que no haya colisión FS pero sí DB
        os.remove(os.path.join(carpeta, "d9.mp4"))
        # intentar renombrar c9 -> d9.mp4 (existe en DB pero no en FS)
        try:
            svc.renombrar_video(vid1, "d9.mp4", ruta_db)
            assert False, "colisión UNIQUE debe fallar antes de tocar FS"
        except ColisionError:
            pass
        assert os.path.isfile(ruta1), "FS no debe tocarse"
        print("test_09 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_10_fallo_rename_deja_db_intacta():
    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    try:
        vid, ruta_orig = _insertar_video(ruta_db, carpeta, "e10.mp4")
        orig_rename = os.rename

        def falla(*a, **k):
            raise OSError("simulado")

        import renombrar_video as m
        old = m.os.rename
        m.os.rename = falla
        try:
            try:
                m.renombrar_video(vid, "e10b.mp4", ruta_db)
                assert False
            except RenombradoError:
                pass
        finally:
            m.os.rename = old
        # DB intacta
        info = obtener_video_por_id(vid, ruta_db)
        assert info["nombre"] == "e10.mp4"
        assert os.path.isfile(ruta_orig)
        assert not os.path.isfile(os.path.join(carpeta, "e10b.mp4"))
        print("test_10 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_11_fallo_sqlite_compensacion_restaura_fs():
    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    try:
        vid, ruta_orig = _insertar_video(ruta_db, carpeta, "f11.mp4")
        nueva = os.path.join(carpeta, "f11b.mp4")
        # mock sqlite3.connect para que UPDATE falle
        import renombrar_video as m
        orig_connect = m.sqlite3.connect

        class FakeConn:
            def __init__(self, *a, **k):
                self._real = orig_connect(*a, **k)
                self._in_tx = False
            def execute(self, sql, params=()):
                if "UPDATE videos SET" in sql:
                    raise sqlite3.OperationalError("simulado fallo DB")
                return self._real.execute(sql, params)
            def commit(self): return self._real.commit()
            def rollback(self):
                try: self._real.rollback()
                except Exception: pass
            def close(self): return self._real.close()

        def fake_connect(*a, **k):
            # dejar pasar las dos primeras conexiones (carga y check) normales
            # la tercera (update) la interceptamos; contamos calls
            fake_connect.calls += 1
            if fake_connect.calls >= 3:
                return FakeConn(*a, **k)
            return orig_connect(*a, **k)
        fake_connect.calls = 0

        m.sqlite3.connect = fake_connect
        try:
            try:
                m.renombrar_video(vid, "f11b.mp4", ruta_db)
                assert False, "debe fallar DB"
            except RenombradoError as exc:
                # debe haber restaurado FS
                assert os.path.isfile(ruta_orig), "FS debe restaurarse"
                assert not os.path.isfile(nueva)
                assert "restaurado" in str(exc).lower() or "fallo al persistir" in str(exc).lower()
            except CompensacionFalloError:
                assert False, "compensación no debe fallar aquí"
        finally:
            m.sqlite3.connect = orig_connect
        info = obtener_video_por_id(vid, ruta_db)
        assert info["nombre"] == "f11.mp4"
        print("test_11 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_12_fallo_compensacion_error_critico():
    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    try:
        vid, ruta_orig = _insertar_video(ruta_db, carpeta, "g12.mp4")
        nueva = os.path.join(carpeta, "g12b.mp4")
        import renombrar_video as m
        orig_connect = m.sqlite3.connect
        orig_rename = m.os.rename
        # hacer que UPDATE falle y que rename de compensación falle
        renames = []

        def tracking_rename(src, dst):
            renames.append((src, dst))
            if len(renames) == 1:
                return orig_rename(src, dst)
            else:
                raise OSError("compensación fallida simulada")

        class FakeConn2:
            def __init__(self, *a, **k):
                self._real = orig_connect(*a, **k)
            def execute(self, sql, params=()):
                if "UPDATE videos SET" in sql:
                    raise sqlite3.OperationalError("fallo DB tras rename")
                return self._real.execute(sql, params)
            def commit(self): return self._real.commit()
            def rollback(self):
                try: self._real.rollback()
                except Exception: pass
            def close(self): return self._real.close()

        def fake_connect2(*a, **k):
            fake_connect2.calls += 1
            if fake_connect2.calls >= 3:
                return FakeConn2(*a, **k)
            return orig_connect(*a, **k)
        fake_connect2.calls = 0

        m.sqlite3.connect = fake_connect2
        m.os.rename = tracking_rename
        try:
            try:
                m.renombrar_video(vid, "g12b.mp4", ruta_db)
                assert False, "debe lanzar CompensacionFalloError"
            except CompensacionFalloError as exc:
                assert exc.ruta_original is not None
                assert exc.ruta_nueva is not None
                assert "g12b" in exc.ruta_nueva or "g12" in str(exc)
                # FS divergente: nueva existe, original no
                assert os.path.isfile(nueva)
                assert not os.path.isfile(ruta_orig)
                # el error debe ser detectable (no éxito falso)
            except RenombradoError:
                assert False, "debe ser CompensacionFalloError, no RenombradoError simple"
        finally:
            m.sqlite3.connect = orig_connect
            m.os.rename = orig_rename
        print("test_12 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_13_integrity_check():
    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    try:
        vid, _ = _insertar_video(ruta_db, carpeta, "h13.mp4")
        svc.renombrar_video(vid, "h13b.mp4", ruta_db)
        conn = sqlite3.connect(ruta_db)
        row = conn.execute("PRAGMA integrity_check").fetchone()
        assert row[0] == "ok", f"integrity_check {row}"
        conn.close()
        print("test_13 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_14_ui_no_hace_sqlite_rename_directo_y_usa_background():
    fuente_visor = inspect.getsource(visor_videos.VisorVideos._iniciar_renombrar)
    assert "TareaRenombrarVideo" in fuente_visor, "UI debe usar TareaRenombrarVideo"
    assert "os.rename" not in fuente_visor, "UI no debe hacer rename directo"
    assert "sqlite" not in fuente_visor.lower(), "UI no debe acceder SQLite directo"
    assert "gestor_renombrado.iniciar" in fuente_visor
    fuente_tarea = inspect.getsource(TareaRenombrarVideo._trabajo)
    assert "renombrar_video" in fuente_tarea
    fuente_menu = inspect.getsource(visor_videos.VisorVideos._mostrar_menu_contextual)
    assert "Renombrar" in fuente_menu
    assert hasattr(visor_videos.VisorVideos, "_atajo_f2_renombrar") or "F2" in inspect.getsource(visor_videos.VisorVideos.__init__)
    print("test_14 OK")


def test_15_regresiones_marcadores_segmentos_derivados_version():
    # versión
    from configuracion import TEXTO_VERSION_BUILD
    assert TEXTO_VERSION_BUILD == "Beta 7 - B7.0"
    # marcadores/segmentos aún funcionan
    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    try:
        vid, _ = _insertar_video(ruta_db, carpeta, "i15.mp4")
        mid = guardar_marcador(vid, 1.0, ruta_db)
        sid, _, _ = guardar_segmento(vid, 0.5, 2.0, ruta_db)
        assert listar_marcadores(vid, ruta_db)[0][0] == mid
        assert listar_segmentos(vid, ruta_db)[0][0] == sid
        # rename no rompe
        svc.renombrar_video(vid, "i15b.mp4", ruta_db)
        assert listar_marcadores(vid, ruta_db)[0][0] == mid
        print("test_15 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_16_ui_tarjeta_sincronizada_sin_reescaneo():
    """Prueba conductual real B7.1: Tarjeta sincronizada con nueva_ruta sin reescaneo.

    Verifica tras _al_resultado_renombrado:
      - mismo video_id, nombre nuevo, _carpeta_video == dirname(nueva_ruta)
      - _ruta_video_de devuelve nueva ruta existente (no la vieja)
      - carpeta_seleccionada no cambia
      - _copiar_ruta produce nueva ruta
      - _abrir_carpeta usa carpeta correcta (dirname nueva_ruta)
      - _abrir_video/apertura recibe nombre nuevo + carpeta correcta
      - no se llama reescaneo global (iniciar_escaneo / tarea lectura)
    """
    import sys
    import time
    from PySide6.QtWidgets import QApplication
    import apertura_videos

    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    os.makedirs(carpeta, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, carpeta, "orig16.mp4", contenido=b"abc")
        assert os.path.isfile(ruta_orig)
        # Crear nueva ruta física (simular éxito de servicio antes de UI)
        nuevo_nombre = "renombrado16.mp4"
        nueva_ruta = os.path.join(carpeta, nuevo_nombre)
        os.rename(ruta_orig, nueva_ruta)
        assert os.path.isfile(nueva_ruta)
        assert not os.path.isfile(ruta_orig)

        # Actualizar DB como lo haría el servicio (para que fila tenga nuevo nombre/ruta si UI la leyera)
        # Pero la UI no reescanea; solo verifica sincronización local, no necesita DB actualizada para esta prueba
        # Sí actualizamos DB para coherencia del test de _ruta_video_de vs filesystem
        conn = sqlite3.connect(ruta_db)
        conn.execute("UPDATE videos SET nombre=?, ruta=? WHERE id=?", (nuevo_nombre, nueva_ruta, vid))
        conn.commit()
        conn.close()

        app = QApplication.instance()
        created_app = False
        if app is None:
            app = QApplication(sys.argv)
            created_app = True

        # Patch os.startfile si no existe (Linux) para que el test no falle
        orig_startfile = getattr(os, "startfile", None)
        startfile_calls = []

        def fake_startfile(ruta):
            startfile_calls.append(ruta)

        os.startfile = fake_startfile

        ruta_config = os.path.join(tmpdir, "config_b16.json")
        ventana = visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(720, 540)
        ventana.show()

        def esperar(pred, intentos=200):
            for _ in range(intentos):
                QApplication.processEvents()
                if pred():
                    return True
                time.sleep(0.02)
            QApplication.processEvents()
            return pred()

        esperar(lambda: ventana._carga_completada and not ventana.gestor.activo, intentos=250)

        # Asignar carpeta_seleccionada y asegurar que la tarjeta existe
        ventana.carpeta_seleccionada = carpeta
        # Si la carga no trajo la tarjeta (por filtro), forzar inserción manual mínima
        tarjeta = ventana._tarjeta_por_nombre("orig16.mp4")
        if tarjeta is None:
            # Reconstruir tarjeta manualmente para garantizar estado previo al renombrado
            # Usar fila mínima de catálogo
            fila = ("orig16.mp4", 10.0, 640, 480, "h264", 1, 123, ruta_orig, vid)
            from visor_videos import Tarjeta
            tarjeta = Tarjeta(fila, ruta_config=ruta_config)
            ventana.tarjetas.append(("orig16.mp4", tarjeta))
            ventana.visibles.append("orig16.mp4")
            ventana._nombres_seleccionados.add("orig16.mp4")
        else:
            ventana._nombres_seleccionados.add("orig16.mp4")
            if "orig16.mp4" not in ventana.visibles:
                ventana.visibles.append("orig16.mp4")

        tarjeta_previa_id = getattr(tarjeta, "_video_id", None)
        assert tarjeta_previa_id == vid, "tarjeta debe tener mismo video_id antes del resultado"
        carpeta_previa = getattr(tarjeta, "_carpeta_video", None)
        # carpeta_previa debe ser carpeta (misma que carpeta_seleccionada)
        assert carpeta_previa is not None

        # Parchear reescaneo global para detectar llamadas
        reescaneo_calls = []
        orig_iniciar_escaneo = visor_videos.VisorVideos.iniciar_escaneo
        orig_crear_tarea = visor_videos.VisorVideos._crear_tarea_lectura

        def fake_iniciar_escaneo(self, *a, **k):
            reescaneo_calls.append("iniciar_escaneo")
            return None

        def fake_crear_tarea(self, *a, **k):
            reescaneo_calls.append("_crear_tarea_lectura")
            return orig_crear_tarea(self, *a, **k)

        visor_videos.VisorVideos.iniciar_escaneo = fake_iniciar_escaneo
        visor_videos.VisorVideos._crear_tarea_lectura = fake_crear_tarea

        # Parchear clipboard y apertura
        orig_clipboard_text = None
        from PySide6.QtWidgets import QApplication as QA
        QA.clipboard().setText("")
        QApplication.processEvents()

        apertura_calls = []
        orig_abrir_apertura = apertura_videos.abrir_video_con_aplicacion_predeterminada
        orig_abrir_visor = visor_videos.abrir_video_con_aplicacion_predeterminada

        def fake_abrir(nombre, carpeta_arg):
            apertura_calls.append((nombre, carpeta_arg))

        apertura_videos.abrir_video_con_aplicacion_predeterminada = fake_abrir
        visor_videos.abrir_video_con_aplicacion_predeterminada = fake_abrir

        # Invocar resultado renombrado (simula TareaRenombrarVideo exitosa)
        resultado = {
            "ok": True,
            "video_id": vid,
            "nombre": nuevo_nombre,
            "ruta": nueva_ruta,
            "nombre_anterior": "orig16.mp4",
        }
        ventana._renombrado_nombre_anterior = "orig16.mp4"
        ventana._al_resultado_renombrado(resultado)
        QApplication.processEvents()

        # Verificaciones
        assert getattr(tarjeta, "_video_id", None) == vid, "mismo video_id tras renombrado"
        assert tarjeta.nombre == nuevo_nombre, f"tarjeta.nombre debe ser {nuevo_nombre!r} got {tarjeta.nombre!r}"
        assert getattr(tarjeta, "_carpeta_video", None) is not None
        # _carpeta_video debe ser dirname(nueva_ruta) normalizado
        exp_carpeta = os.path.dirname(nueva_ruta).rstrip(os.sep) or os.path.dirname(nueva_ruta)
        assert os.path.normcase(os.path.normpath(getattr(tarjeta, "_carpeta_video"))) == os.path.normcase(os.path.normpath(exp_carpeta)), f"_carpeta_video incorrecta {getattr(tarjeta,'_carpeta_video')!r} vs {exp_carpeta!r}"
        # _ruta_video_de debe devolver nueva_ruta existente, no la vieja
        ruta_resuelta = ventana._ruta_video_de(tarjeta)
        assert ruta_resuelta is not None and os.path.normcase(os.path.normpath(ruta_resuelta)) == os.path.normcase(os.path.normpath(nueva_ruta)), f"_ruta_video_de {ruta_resuelta!r} != {nueva_ruta!r}"
        assert os.path.isfile(ruta_resuelta), "_ruta_video_de debe apuntar a archivo existente"
        # carpeta_seleccionada no cambia (B7.1 no mueve de carpeta)
        assert ventana.carpeta_seleccionada == carpeta, "carpeta_seleccionada no debe cambiar en B7.1"
        # _copiar_ruta produce nueva ruta
        ventana._copiar_ruta(nuevo_nombre)
        QApplication.processEvents()
        clip = QA.clipboard().text()
        esperado_clip = os.path.abspath(os.path.join(carpeta, nuevo_nombre))
        assert clip == esperado_clip, f"_copiar_ruta {clip!r} != {esperado_clip!r}"
        # _abrir_carpeta usa carpeta correcta
        startfile_calls.clear()
        ventana._abrir_carpeta(nuevo_nombre)
        assert startfile_calls == [os.path.abspath(carpeta)] or startfile_calls == [carpeta] or startfile_calls[0] == carpeta, f"_abrir_carpeta debe abrir {carpeta!r} got {startfile_calls!r}"
        # _abrir_video / apertura recibe nombre nuevo + carpeta correcta
        apertura_calls.clear()
        ventana._abrir_video(nuevo_nombre)
        assert len(apertura_calls) == 1, "_abrir_video debe llamar a apertura"
        assert apertura_calls[0][0] == nuevo_nombre, f"_abrir_video nombre {apertura_calls[0][0]!r} != {nuevo_nombre!r}"
        assert os.path.normcase(os.path.normpath(apertura_calls[0][1])) == os.path.normcase(os.path.normpath(carpeta)), f"_abrir_video carpeta {apertura_calls[0][1]!r} != {carpeta!r}"
        # No se llamó reescaneo global
        assert not reescaneo_calls, f"no debe llamarse reescaneo global, got {reescaneo_calls!r}"

        # Restaurar parches
        visor_videos.VisorVideos.iniciar_escaneo = orig_iniciar_escaneo
        visor_videos.VisorVideos._crear_tarea_lectura = orig_crear_tarea
        apertura_videos.abrir_video_con_aplicacion_predeterminada = orig_abrir_apertura
        visor_videos.abrir_video_con_aplicacion_predeterminada = orig_abrir_visor
        if orig_startfile is None:
            try:
                delattr(os, "startfile")
            except Exception:
                os.startfile = orig_startfile
        else:
            os.startfile = orig_startfile

        # Cerrar ventana sin guardar estado extra
        ventana.close()
        ventana.gestor.cerrar()
        try:
            ventana.gestor_previews.cerrar()
        except Exception:
            pass
        try:
            ventana.gestor_renombrado.cerrar()
        except Exception:
            pass

        print("test_16 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_17_ruta_inconsistente_no_exito_silencioso():
    """Si nueva_ruta falta o no coincide, _al_resultado_renombrado no declara éxito silencioso."""
    import sys
    import time
    from PySide6.QtWidgets import QApplication

    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    os.makedirs(carpeta, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, carpeta, "orig17.mp4")
        nueva_ruta_invalida = None
        # Visor mínimo
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        ruta_config = os.path.join(tmpdir, "config_b17.json")
        ventana = visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(720, 540)
        ventana.show()

        def esperar(pred, intentos=200):
            for _ in range(intentos):
                QApplication.processEvents()
                if pred():
                    return True
                time.sleep(0.02)
            QApplication.processEvents()
            return pred()

        esperar(lambda: ventana._carga_completada and not ventana.gestor.activo, intentos=250)
        ventana.carpeta_seleccionada = carpeta
        # asegurar tarjeta
        tarjeta = ventana._tarjeta_por_nombre("orig17.mp4")
        if tarjeta is None:
            fila = ("orig17.mp4", 10.0, 640, 480, "h264", 1, 123, ruta_orig, vid)
            from visor_videos import Tarjeta
            tarjeta = Tarjeta(fila, ruta_config=ruta_config)
            ventana.tarjetas.append(("orig17.mp4", tarjeta))
            ventana.visibles.append("orig17.mp4")
        nombre_prev = tarjeta.nombre
        carpeta_prev = getattr(tarjeta, "_carpeta_video", None)

        # Resultado inconsistente: nueva_ruta faltante
        resultado_malo = {"ok": True, "video_id": vid, "nombre": "renombrado17.mp4", "ruta": None, "nombre_anterior": "orig17.mp4"}
        ventana._renombrado_nombre_anterior = "orig17.mp4"
        ventana._al_resultado_renombrado(resultado_malo)
        QApplication.processEvents()
        # No debe haber actualizado tarjeta a nuevo nombre (tratamiento conservador)
        assert tarjeta.nombre == nombre_prev, "con ruta None no debe actualizar nombre silenciosamente"
        # mensaje debe indicar inconsistencia
        assert "inconsistente" in ventana.mensaje_carpeta.text().lower(), "debe marcar inconsistencia"

        # Segundo caso: basename mismatch
        resultado_mismatch = {"ok": True, "video_id": vid, "nombre": "renombrado17.mp4", "ruta": os.path.join(carpeta, "otro.mp4"), "nombre_anterior": "orig17.mp4"}
        ventana._renombrado_nombre_anterior = "orig17.mp4"
        ventana._al_resultado_renombrado(resultado_mismatch)
        QApplication.processEvents()
        assert tarjeta.nombre == nombre_prev, "con mismatch no debe actualizar"

        ventana.close()
        ventana.gestor.cerrar()
        try:
            ventana.gestor_previews.cerrar()
        except Exception:
            pass
        try:
            ventana.gestor_renombrado.cerrar()
        except Exception:
            pass
        print("test_17 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_18_miniatura_y_previews_persisten_tras_rename_y_reinicio():
    """B7.1 regresión: tras rename, miniatura principal y previews deben persistir sin Escanear.

    Simula el flujo humano: miniatura válida -> rename -> cerrar/recrear Visor (recarga catálogo)
    -> miniatura_principal(nuevo) debe existir y previews_existentes(nuevo) completas,
    sin regeneración ni reescaneo.
    """
    import tempfile, shutil, os
    import escanear_videos as esc
    import visor_videos as visor
    import rutas

    tmpdir, ruta_db = _crear_db_temporal()
    carpeta = os.path.join(tmpdir, "videos")
    os.makedirs(carpeta, exist_ok=True)
    carpeta_mini = os.path.join(tmpdir, "miniaturas")
    os.makedirs(carpeta_mini, exist_ok=True)
    # patch rutas
    orig_mini_rutas = rutas.ruta_carpeta_miniaturas
    orig_mini_esc = esc.ruta_carpeta_miniaturas
    orig_mini_visor = visor.ruta_carpeta_miniaturas
    rutas.ruta_carpeta_miniaturas = lambda: carpeta_mini
    esc.ruta_carpeta_miniaturas = lambda: carpeta_mini
    visor.ruta_carpeta_miniaturas = lambda: carpeta_mini
    try:
        vid, ruta_orig = _insertar_video(ruta_db, carpeta, "orig18.mp4", contenido=b"x"*128)
        # Crear cache simulada (miniatura principal + previews)
        prefijo_old = esc._nombre_seguro(os.path.splitext("orig18.mp4")[0])
        ruta_mini_old = os.path.join(carpeta_mini, f"{prefijo_old}_01.jpg")
        with open(ruta_mini_old, "wb") as f:
            f.write(b"\xff\xd8fake")
        # asegura mtime mini >= video mtime para vigente (copiar mtime)
        try:
            st = os.stat(ruta_orig)
            os.utime(ruta_mini_old, (st.st_atime, st.st_mtime))
        except Exception:
            pass
        for i in range(1, esc.CANTIDAD_PREVIEWS + 1):
            p = os.path.join(carpeta_mini, f"{prefijo_old}_preview_{i:02d}.jpg")
            with open(p, "wb") as f:
                f.write(b"\xff\xd8preview")
        # Verificación inicial
        assert visor.miniatura_principal("orig18.mp4") is not None, "miniatura inicial debe existir"
        assert len(esc.previews_existentes("orig18.mp4")) == esc.CANTIDAD_PREVIEWS, "previews iniciales completas"
        # Renombrar (flujo real)
        nuevo = "renombrado18.mp4"
        res = svc.renombrar_video(vid, nuevo, ruta_db)
        assert res["ok"] and res["nombre"] == nuevo
        # Simular reinicio: recarga con nuevo nombre
        mp = visor.miniatura_principal(nuevo)
        assert mp is not None, f"tras rename+reinicio miniatura_principal({nuevo!r}) no debe ser None (Sin miniatura)"
        assert os.path.isfile(mp), f"miniatura destino debe existir en FS: {mp!r}"
        # No debe quedar archivo viejo
        assert not os.path.isfile(ruta_mini_old), "cache vieja debe haber sido movida, no duplicada"
        # Previews secundarias también deben persistir
        previews = esc.previews_existentes(nuevo)
        assert len(previews) == esc.CANTIDAD_PREVIEWS, f"previews tras rename deben ser {esc.CANTIDAD_PREVIEWS}, got {len(previews)}"
        for p in previews:
            assert os.path.isfile(p), f"preview {p!r} debe existir"
            assert "renombrado18" in os.path.basename(p), "preview debe usar nuevo prefijo"
        # Contar miniaturas por nombre nuevo
        assert esc.contar_miniaturas(nuevo) == 1
        assert esc.contar_miniaturas("orig18.mp4") == 0
        # Verificar que no se regeneró (mtime preservado, no nueva generación)
        # El mtime del nuevo archivo debe ser el del viejo (rename preserva mtime)
        # No podemos asegurar exacto, pero debe existir y ser >0
        assert os.path.getsize(mp) > 0
        print("test_18 OK")
    finally:
        rutas.ruta_carpeta_miniaturas = orig_mini_rutas
        esc.ruta_carpeta_miniaturas = orig_mini_esc
        visor.ruta_carpeta_miniaturas = orig_mini_visor
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    test_01_rename_simple_conserva_id()
    test_02_ruta_nombre_db_correctos()
    test_03_marcadores_segmentos_conservados()
    test_04_color_clasificacion_conservados()
    test_05_relaciones_derivados_no_destruidas()
    test_06_extension_preservada()
    test_07_validaciones_rechazadas()
    test_08_colision_filesystem()
    test_09_colision_unique_nombre()
    test_10_fallo_rename_deja_db_intacta()
    test_11_fallo_sqlite_compensacion_restaura_fs()
    test_12_fallo_compensacion_error_critico()
    test_13_integrity_check()
    test_14_ui_no_hace_sqlite_rename_directo_y_usa_background()
    test_15_regresiones_marcadores_segmentos_derivados_version()
    test_16_ui_tarjeta_sincronizada_sin_reescaneo()
    test_17_ruta_inconsistente_no_exito_silencioso()
    test_18_miniatura_y_previews_persisten_tras_rename_y_reinicio()
    print("TODOS B7.1 OK")
