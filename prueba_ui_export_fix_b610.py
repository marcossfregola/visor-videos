"""Pruebas de regresión B6.10 UI fix — valida corrección _al_resultado_export compartido.

Cubre (mandato TASK_ID beta6-b610-ui-regresion-fix-001):
- B6.7 individual conserva títulos/mensajes en éxito, error y cancelación
- B6.9 lote conserva resumen/flujo
- B6.10 secuencia usa títulos/mensajes propios
- discriminación no depende del nombre del archivo de salida
- botones Exportar segmentos / Unir segmentos se restauran correctamente
- detección frágil eliminada (no "secuencia" in filename ni _segmentos)
- restauración idempotente tras resultado/error/finalizada
"""
import inspect
import os
import sys
import tempfile
import time
from unittest import mock

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

import visor_videos

def _crear_visor_minimo():
    # crear app si no existe
    app = QApplication.instance() or QApplication(sys.argv)
    # usar dirs temporales para evitar tocar DB/config reales
    tmpdir = tempfile.mkdtemp(prefix="visor_fix_test_")
    # VisorVideos requiere carpeta y config; usar temporales
    # intentamos construir con carpeta vacía y ruta_config temporal
    ruta_config = os.path.join(tmpdir, "config.json")
    # VisorVideos __init__ puede requerir _ruta_db etc; lo instanciamos y luego parcheamos lo mínimo
    try:
        v = visor_videos.VisorVideos()
    except TypeError:
        # fallback si requiere args
        v = visor_videos.VisorVideos.__new__(visor_videos.VisorVideos)
        # intentar init mínimo manual: evitar ejecutar __init__ completo si falla
        # en su lugar crear atributos esenciales
        from PySide6.QtWidgets import QMainWindow
        QMainWindow.__init__(v)
        # crear botones mínimos necesarios para los handlers
        from PySide6.QtWidgets import QPushButton, QLabel, QProgressBar
        v.boton_exportar_lote = QPushButton("Exportar segmentos…")
        v.boton_exportar_secuencia = QPushButton("Unir segmentos…")
        v.boton_cancelar_export = QPushButton("Cancelar")
        v.barra_progreso = QProgressBar()
        v.estado_escaneo = QLabel()
        v._export_tipo = None
        v._export_lote_activo = False
        v._export_segmento_actual = None
        v._export_destino_actual = None
        v._pipeline_activo = False
        from tareas import GestorTareas
        v.gestor_export = GestorTareas(v)
        v.gestor = GestorTareas(v)
        v._ruta_db = os.path.join(tmpdir, "db.sqlite")
        # stubs para progreso
        v._mostrar_progreso = lambda txt: v.barra_progreso.setVisible(True)
        v._ocultar_progreso = lambda: v.barra_progreso.setVisible(False)
        v._tmpdir = tmpdir
        return v, app, tmpdir
    # si VisorVideos se creó ok, asegurar atributos
    if not hasattr(v, "_export_tipo"):
        v._export_tipo = None
    v._tmpdir = tmpdir
    # asegurar que botones están habilitados al inicio
    if hasattr(v, "boton_exportar_lote"):
        v.boton_exportar_lote.setEnabled(True)
    if hasattr(v, "boton_exportar_secuencia"):
        v.boton_exportar_secuencia.setEnabled(True)
    if hasattr(v, "boton_cancelar_export"):
        v.boton_cancelar_export.setVisible(False)
    app.processEvents()
    return v, app, tmpdir


def _capturar_msgbox():
    capturas = []
    orig_info = QMessageBox.information
    orig_warn = QMessageBox.warning
    def fake_info(parent, titulo, texto, *a, **kw):
        capturas.append(("info", titulo, texto))
        return QMessageBox.Ok
    def fake_warn(parent, titulo, texto, *a, **kw):
        capturas.append(("warn", titulo, texto))
        return QMessageBox.Ok
    return capturas, fake_info, fake_warn, orig_info, orig_warn


def test_01_b67_individual_ok():
    v, app, tmpdir = _crear_visor_minimo()
    caps, fi, fw, oi, ow = _capturar_msgbox()
    try:
        with mock.patch.object(QMessageBox, "information", side_effect=fi):
            with mock.patch.object(QMessageBox, "warning", side_effect=fw):
                v._export_tipo = "individual"
                v.boton_exportar_lote.setEnabled(False)
                v.boton_exportar_secuencia.setEnabled(False)
                v.boton_cancelar_export.setVisible(True)
                v.barra_progreso.setVisible(True)
                res = {"ok": True, "salida": "C:/tmp/video_secuencia_123.mp4", "duracion": 2.5, "cancelado": False}
                # debe usar Segmento exportado aunque filename contenga "secuencia"
                v._al_resultado_export(res)
                # verificar captura
                assert caps, "no se llamó QMessageBox"
                kind, titulo, texto = caps[-1]
                assert titulo == "Segmento exportado", f"individual ok título incorrecto {titulo!r}"
                assert "Segmento exportado" in texto
                # botones restaurados
                assert v.boton_exportar_lote.isEnabled(), "lote no restaurado tras individual ok"
                assert v.boton_exportar_secuencia.isEnabled(), "secuencia no restaurado tras individual ok"
                assert not v.boton_cancelar_export.isVisible(), "cancel visible tras ok"
        return True, "B6.7 individual ok título Segmento exportado ok"
    except Exception as e:
        import traceback
        return False, f"{e}\n{traceback.format_exc()[:800]}"
    finally:
        try:
            v.close()
        except: pass
        import shutil; shutil.rmtree(tmpdir, ignore_errors=True)
        QApplication.processEvents()

def test_02_b67_individual_cancel():
    v, app, tmpdir = _crear_visor_minimo()
    caps, fi, fw, oi, ow = _capturar_msgbox()
    try:
        with mock.patch.object(QMessageBox, "information", side_effect=fi):
            with mock.patch.object(QMessageBox, "warning", side_effect=fw):
                v._export_tipo = "individual"
                v.boton_exportar_lote.setEnabled(False)
                v.boton_exportar_secuencia.setEnabled(False)
                res = {"ok": False, "cancelado": True, "salida": "C:/out2.mp4"}
                v._al_resultado_export(res)
                assert caps
                kind, titulo, texto = caps[-1]
                assert titulo == "Exportar segmento", f"individual cancel título {titulo!r}"
                assert "cancelada" in texto.lower()
                assert v.boton_exportar_lote.isEnabled()
                assert v.boton_exportar_secuencia.isEnabled()
        return True, "B6.7 individual cancel Exportar segmento ok"
    except Exception as e:
        import traceback
        return False, f"{e}\n{traceback.format_exc()[:600]}"
    finally:
        try: v.close()
        except: pass
        import shutil; shutil.rmtree(tmpdir, ignore_errors=True)

def test_03_b67_individual_error():
    v, app, tmpdir = _crear_visor_minimo()
    caps, fi, fw, oi, ow = _capturar_msgbox()
    try:
        with mock.patch.object(QMessageBox, "information", side_effect=fi):
            with mock.patch.object(QMessageBox, "warning", side_effect=fw):
                v._export_tipo = "individual"
                res = {"ok": False, "error": "algo falló", "cancelado": False}
                v._al_resultado_export(res)
                assert caps
                kind, titulo, texto = caps[-1]
                assert kind == "warn"
                assert titulo == "Exportar segmento", f"individual error título {titulo!r}"
                assert v.boton_exportar_lote.isEnabled() and v.boton_exportar_secuencia.isEnabled()
        return True, "B6.7 individual error Exportar segmento ok"
    except Exception as e:
        import traceback
        return False, f"{e}\n{traceback.format_exc()[:600]}"
    finally:
        try: v.close()
        except: pass
        import shutil; shutil.rmtree(tmpdir, ignore_errors=True)

def test_04_b610_secuencia_ok():
    v, app, tmpdir = _crear_visor_minimo()
    caps, fi, fw, oi, ow = _capturar_msgbox()
    try:
        with mock.patch.object(QMessageBox, "information", side_effect=fi):
            with mock.patch.object(QMessageBox, "warning", side_effect=fw):
                v._export_tipo = "secuencia"
                v.boton_exportar_lote.setEnabled(False)
                v.boton_exportar_secuencia.setEnabled(False)
                res = {"ok": True, "salida": "C:/tmp/mi_video.mp4", "duracion": 5.0}
                v._al_resultado_export(res)
                assert caps
                kind, titulo, texto = caps[-1]
                assert titulo == "Secuencia exportada", f"secuencia ok título {titulo!r}"
                assert "Secuencia exportada" in texto
                assert v.boton_exportar_lote.isEnabled() and v.boton_exportar_secuencia.isEnabled()
        return True, "B6.10 secuencia ok Secuencia exportada ok"
    except Exception as e:
        import traceback
        return False, f"{e}\n{traceback.format_exc()[:600]}"
    finally:
        try: v.close()
        except: pass
        import shutil; shutil.rmtree(tmpdir, ignore_errors=True)

def test_05_b610_secuencia_cancel():
    v, app, tmpdir = _crear_visor_minimo()
    caps, fi, fw, oi, ow = _capturar_msgbox()
    try:
        with mock.patch.object(QMessageBox, "information", side_effect=fi):
            with mock.patch.object(QMessageBox, "warning", side_effect=fw):
                v._export_tipo = "secuencia"
                res = {"ok": False, "cancelado": True}
                v._al_resultado_export(res)
                assert caps
                kind, titulo, _ = caps[-1]
                assert titulo == "Unir segmentos", f"secuencia cancel título {titulo!r}"
        return True, "B6.10 secuencia cancel Unir segmentos ok"
    except Exception as e:
        import traceback
        return False, f"{e}\n{traceback.format_exc()[:600]}"
    finally:
        try: v.close()
        except: pass
        import shutil; shutil.rmtree(tmpdir, ignore_errors=True)

def test_06_b610_secuencia_error():
    v, app, tmpdir = _crear_visor_minimo()
    caps, fi, fw, oi, ow = _capturar_msgbox()
    try:
        with mock.patch.object(QMessageBox, "information", side_effect=fi):
            with mock.patch.object(QMessageBox, "warning", side_effect=fw):
                v._export_tipo = "secuencia"
                res = {"ok": False, "error": "fallo seq", "cancelado": False}
                v._al_resultado_export(res)
                assert caps
                kind, titulo, texto = caps[-1]
                assert kind == "warn" and titulo == "Unir segmentos", f"secuencia error título {titulo!r}"
        return True, "B6.10 secuencia error Unir segmentos ok"
    except Exception as e:
        import traceback
        return False, f"{e}\n{traceback.format_exc()[:600]}"
    finally:
        try: v.close()
        except: pass
        import shutil; shutil.rmtree(tmpdir, ignore_errors=True)

def test_07_b69_lote():
    v, app, tmpdir = _crear_visor_minimo()
    caps, fi, fw, oi, ow = _capturar_msgbox()
    try:
        with mock.patch.object(QMessageBox, "information", side_effect=fi):
            with mock.patch.object(QMessageBox, "warning", side_effect=fw):
                v._export_tipo = "lote"
                v._export_lote_activo = True
                res = {"total": 3, "exitos": ["a","b"], "fallos": [], "omitidos": [], "cancelados": [], "cancelado": False}
                v._al_resultado_export(res)
                assert caps
                kind, titulo, texto = caps[-1]
                assert titulo == "Exportar segmentos", f"lote título {titulo!r}"
                assert "2 exitosos" in texto or "2" in texto
                assert v.boton_exportar_lote.isEnabled() and v.boton_exportar_secuencia.isEnabled()
        return True, "B6.9 lote Exportar segmentos ok"
    except Exception as e:
        import traceback
        return False, f"{e}\n{traceback.format_exc()[:600]}"
    finally:
        try: v.close()
        except: pass
        import shutil; shutil.rmtree(tmpdir, ignore_errors=True)

def test_08_discriminacion_no_filename():
    v, app, tmpdir = _crear_visor_minimo()
    caps, fi, fw, oi, ow = _capturar_msgbox()
    try:
        with mock.patch.object(QMessageBox, "information", side_effect=fi):
            # individual con filename que contiene "secuencia" debe seguir siendo Segmento exportado
            v._export_tipo = "individual"
            res = {"ok": True, "salida": "C:/tmp/MI_SECUENCIA_final.MP4", "duracion": 1.0}
            v._al_resultado_export(res)
            kind, titulo, _ = caps[-1]
            assert titulo == "Segmento exportado", f"discriminación filename individual falló {titulo!r}"
            caps.clear()
            # secuencia con filename sin "secuencia" debe ser Secuencia exportada
            v._export_tipo = "secuencia"
            res2 = {"ok": True, "salida": "C:/tmp/out.mp4", "duracion": 1.0}
            v._al_resultado_export(res2)
            kind, titulo2, _ = caps[-1]
            assert titulo2 == "Secuencia exportada", f"discriminación filename secuencia falló {titulo2!r}"
            # error individual con nombre que contiene secuencia
            v._export_tipo = "individual"
            caps.clear()
            with mock.patch.object(QMessageBox, "warning", side_effect=fw):
                v._al_resultado_export({"ok": False, "error": "e", "cancelado": False, "salida": "c:/tmp/secUENCIA.mp4"})
                kind, titulo3, _ = caps[-1]
                assert titulo3 == "Exportar segmento", f"error discriminación falló {titulo3!r}"
        return True, "discriminación no depende de filename ok"
    except Exception as e:
        import traceback
        return False, f"{e}\n{traceback.format_exc()[:600]}"
    finally:
        try: v.close()
        except: pass
        import shutil; shutil.rmtree(tmpdir, ignore_errors=True)

def test_09_botones_restauran():
    v, app, tmpdir = _crear_visor_minimo()
    caps, fi, fw, oi, ow = _capturar_msgbox()
    try:
        with mock.patch.object(QMessageBox, "information", side_effect=fi):
            with mock.patch.object(QMessageBox, "warning", side_effect=fw):
                # simular inicio individual: botones deshabilitados
                v._export_tipo = "individual"
                v.boton_exportar_lote.setEnabled(False)
                v.boton_exportar_secuencia.setEnabled(False)
                v.boton_cancelar_export.setVisible(True)
                # error
                v._al_error_export("boom")
                assert v.boton_exportar_lote.isEnabled() and v.boton_exportar_secuencia.isEnabled(), "botones no restaurados tras _al_error_export"
                assert not v.boton_cancelar_export.isVisible(), "cancel visible tras error"
                # luego finalizada debe ser idempotente
                v._export_tipo = "secuencia"
                v.boton_exportar_lote.setEnabled(False)
                v.boton_exportar_secuencia.setEnabled(False)
                v._al_export_finalizada()
                assert v.boton_exportar_lote.isEnabled() and v.boton_exportar_secuencia.isEnabled(), "botones no restaurados tras finalizada"
                assert v._export_tipo is None, "tipo no limpiado en finalizada"
                # doble finalizada no debe fallar
                v._al_export_finalizada()
                assert v.boton_exportar_lote.isEnabled()
        return True, "botones restauran tras error/finalizada ok"
    except Exception as e:
        import traceback
        return False, f"{e}\n{traceback.format_exc()[:600]}"
    finally:
        try: v.close()
        except: pass
        import shutil; shutil.rmtree(tmpdir, ignore_errors=True)

def test_10_fragil_eliminada():
    src = inspect.getsource(visor_videos.VisorVideos._al_resultado_export)
    # no debe contener inferencia frágil por filename ni _segmentos privado
    if "secuencia" in src.lower() and "in str(salida)" in src:
        return False, "aún contiene inferencia por filename"
    if "_segmentos" in src:
        return False, "aún contiene _segmentos frágil"
    # debe usar _export_tipo explícito
    if "_export_tipo" not in src:
        return False, "no usa _export_tipo explícito"
    # _al_error_export también debe discriminar
    src2 = inspect.getsource(visor_videos.VisorVideos._al_error_export)
    if "_export_tipo" not in src2:
        return False, "_al_error_export no discrimina por tipo"
    return True, "inferencia frágil eliminada, usa _export_tipo"

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    tests = [test_01_b67_individual_ok, test_02_b67_individual_cancel, test_03_b67_individual_error, test_04_b610_secuencia_ok, test_05_b610_secuencia_cancel, test_06_b610_secuencia_error, test_07_b69_lote, test_08_discriminacion_no_filename, test_09_botones_restauran, test_10_fragil_eliminada]
    res=[]
    for i, fn in enumerate(tests, start=1):
        try:
            ok, det = fn()
        except Exception as e:
            import traceback
            ok, det = False, f"ex {e}\n{traceback.format_exc()[:600]}"
        res.append((i, ok, det))
        print(f"P{i:02d} {'OK' if ok else 'FALLO'} - {det}")
        sys.stdout.flush()
        QApplication.processEvents()
        time.sleep(0.05)
    total_ok = sum(1 for _,ok,_ in res if ok)
    print(f"TOTAL={total_ok}/{len(res)}")
    print(f"RESULTADO_FINAL={'OK' if total_ok==len(res) else 'FALLO'}")
    return 0 if total_ok==len(res) else 1

if __name__ == "__main__":
    sys.exit(main())
