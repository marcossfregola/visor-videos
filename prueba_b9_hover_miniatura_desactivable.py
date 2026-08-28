import contextlib
import json
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QDialog

import escanear_videos as escanear_mod
import visor_videos
from configuracion import (
    CLAVE_TAMANO_VISTA_AMPLIADA,
    FACTOR_VISTA_AMPLIADA_DESACTIVADO,
    guardar_tamano_vista_ampliada,
    obtener_tamano_vista_ampliada,
)
from visor_videos import (
    FACTORES_VISTA_AMPLIADA,
    FACTORES_VISTA_AMPLIADA_UI,
    TEXTOS_FACTOR_VISTA_AMPLIADA_UI,
    FACTOR_VISTA_AMPLIADA_DESACTIVADO as VV_DESACT,
    PreferenciasDialog,
    VistaAmpliada,
    VisorVideos,
    configurar_factor_vista_ampliada,
    configurar_tamano_miniaturas,
    dimensiones_miniatura,
)

_CONTADOR = [0]
_FALLOS = [0]


def _paso():
    _CONTADOR[0] += 1
    return _CONTADOR[0]


def ok(mensaje):
    _paso()
    print(f"T{_CONTADOR[0]:02d} OK - {mensaje}")


def falla(mensaje, extra=None):
    _FALLOS[0] += 1
    _paso()
    texto = f"T{_CONTADOR[0]:02d} ERROR - {mensaje}"
    if extra is not None:
        texto += f" ({extra})"
    print(texto)


def verifica(condicion, descripcion, extra=None):
    if condicion:
        ok(descripcion)
    else:
        falla(descripcion, extra)


def _crear_png(ruta):
    imagen = QImage(160, 100, QImage.Format_RGB32)
    imagen.fill(QColor("red"))
    return imagen.save(ruta, "PNG")


@contextlib.contextmanager
def _ventana_con(factor=None):
    temp = tempfile.TemporaryDirectory()
    mini = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    ruta_config = os.path.join(temp.name, "config.json")
    conn = sqlite3.connect(ruta_db)
    conn.execute(
        """
        CREATE TABLE videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            ruta TEXT NOT NULL,
            extension TEXT NOT NULL,
            fecha_importacion TEXT NOT NULL,
            duracion_segundos REAL,
            ancho INTEGER,
            alto INTEGER,
            codec_video TEXT,
            cantidad_miniaturas INTEGER,
            tamano_bytes INTEGER
        )
        """
    )
    conn.execute(
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("clip.mp4", "C:\\clip.mp4", ".mp4", "2026-08-06T00:00:00", 100.0, 1920, 1080, "h264", 1, 1024),
    )
    conn.commit()
    conn.close()

    if factor is not None:
        guardar_tamano_vista_ampliada(factor, ruta_config)

    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: mini.name
    visor_videos.ruta_carpeta_miniaturas = lambda: mini.name
    _crear_png(os.path.join(mini.name, "clip_preview_01.jpg"))
    _crear_png(os.path.join(mini.name, "clip_preview_02.jpg"))
    videos = tempfile.TemporaryDirectory()
    with open(os.path.join(videos.name, "clip.mp4"), "wb") as f:
        f.write(b"x")
    try:
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(900, 600)
        ventana.show()

        def esperar(predicado, intentos=300):
            for _ in range(intentos):
                QApplication.processEvents()
                if predicado():
                    return True
                time.sleep(0.02)
            QApplication.processEvents()
            return predicado()

        esperar(lambda: ventana._carga_completada and ventana.gestor.hilo is None)

        def _previews_aplicadas():
            return any(
                tarjeta._etiquetas_previews
                and tarjeta._etiquetas_previews[0]._pixmap_original is not None
                for _, tarjeta in ventana.tarjetas
            )

        esperar(_previews_aplicadas)
        ventana.carpeta_seleccionada = videos.name
        yield ventana, ruta_config
    finally:
        try:
            ventana.close()
            ventana.gestor.cerrar()
            ventana.gestor_previews.cerrar()
            ventana.gestor_operaciones.cerrar()
        except Exception:
            pass
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        temp.cleanup()
        mini.cleanup()
        videos.cleanup()


def main():
    app = QApplication.instance() or QApplication(sys.argv)

    _CONTADOR[0] = 1
    configurar_factor_vista_ampliada(1.6)
    configurar_tamano_miniaturas("mediano")

    # --- A) valores históricos siguen disponibles y funcionan ---
    verifica(
        set(FACTORES_VISTA_AMPLIADA) == {1.2, 1.6, 2.0, 2.5, 3.0, 3.5},
        "FACTORES_VISTA_AMPLIADA históricos intactos (1.2-3.5)",
    )
    verifica(
        FACTORES_VISTA_AMPLIADA_UI[0] == VV_DESACT == 0
        and set(FACTORES_VISTA_AMPLIADA_UI[1:]) == {1.2, 1.6, 2.0, 2.5, 3.0, 3.5},
        "FACTORES_VISTA_AMPLIADA_UI incluye Desactivado + históricos",
    )
    verifica(
        TEXTOS_FACTOR_VISTA_AMPLIADA_UI[0] == "Desactivado" and len(TEXTOS_FACTOR_VISTA_AMPLIADA_UI) == 7,
        "TEXTOS_FACTOR incluye Desactivado al inicio (7 items)",
    )
    # preparar escala histórica sigue funcionando
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "thumb.png")
        _crear_png(ruta)
        pixmap = QPixmap(ruta)
        for factor, esperado in ((1.2, (384, 216)), (1.6, (512, 288)), (2.0, (640, 360)), (3.5, (1120, 630))):
            configurar_factor_vista_ampliada(factor)
            vista = VistaAmpliada()
            vista.preparar(pixmap)
            verifica(
                vista._tam_amp == esperado,
                f"factor {factor}: ampliación {esperado}",
                extra=vista._tam_amp,
            )
            vista.close()
    configurar_factor_vista_ampliada(1.6)

    # --- B) Desactivado aparece en el control ---
    temp_config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(temp_config.name, "config.json")
    try:
        dialogo = PreferenciasDialog(ruta_config)
        textos = [dialogo.combo_factor_vista.itemText(i) for i in range(dialogo.combo_factor_vista.count())]
        verifica(
            "Desactivado" in textos,
            "B: Desactivado aparece en el combo de tamaño",
            extra=textos,
        )
        verifica(
            dialogo.combo_factor_vista.count() == 7,
            "B: combo tiene 7 items (Desactivado + 6 factores)",
        )
        idx_des = dialogo.combo_factor_vista.findText("Desactivado")
        verifica(idx_des == 0, "B: Desactivado es el primer item (índice 0)")
        # diálogo default 1.6 cuando sin config
        verifica(
            dialogo.factor_vista_seleccionado() == 1.6,
            "B: diálogo default 1.6 sin config",
        )
        # seleccionar Desactivado retorna 0
        dialogo.combo_factor_vista.setCurrentIndex(idx_des)
        verifica(
            dialogo.factor_vista_seleccionado() == 0,
            "B: seleccionar Desactivado retorna 0",
        )
    finally:
        temp_config.cleanup()

    # --- C) seleccionar Desactivado se guarda/carga correctamente ---
    temp_config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(temp_config.name, "config.json")
    try:
        guardar_tamano_vista_ampliada(0, ruta_config)
        with open(ruta_config, encoding="utf-8") as f:
            contenido = json.load(f)
        verifica(
            contenido.get(CLAVE_TAMANO_VISTA_AMPLIADA) == 0
            and obtener_tamano_vista_ampliada(ruta_config) == 0,
            "C: persistencia Desactivado (0) round-trip",
        )
        # guardar float 0.0 también
        guardar_tamano_vista_ampliada(0.0, ruta_config)
        verifica(
            obtener_tamano_vista_ampliada(ruta_config) == 0,
            "C: guardar 0.0 también persiste como Desactivado",
        )
        # inválidos no modifican
        for invalido in (True, 1.5, "1.6", 2, -1.0, None):
            guardar_tamano_vista_ampliada(invalido, ruta_config)
            verifica(
                obtener_tamano_vista_ampliada(ruta_config) == 0,
                f"C: guardar inválido ({invalido!r}) conserva Desactivado",
            )
        # sin archivo default 1.6
        ruta_no = os.path.join(temp_config.name, "inexistente.json")
        verifica(
            obtener_tamano_vista_ampliada(ruta_no) == 1.6,
            "C: obtener sin archivo devuelve 1.6",
        )
        # valor almacenado inválido vuelve a 1.6
        con_invalido = os.path.join(temp_config.name, "invalido.json")
        with open(con_invalido, "w", encoding="utf-8") as f:
            json.dump({CLAVE_TAMANO_VISTA_AMPLIADA: 9.9}, f)
        verifica(
            obtener_tamano_vista_ampliada(con_invalido) == 1.6,
            "C: valor almacenado inválido vuelve a 1.6",
        )
        # restauración: ventana con factor 0 aplicado al iniciar
        # probamos vía _ventana_con
    finally:
        temp_config.cleanup()

    with _ventana_con(factor=0) as (ventana, ruta_config):
        verifica(
            visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 0,
            "C: restauración con Desactivado aplica factor 0 al iniciar",
        )
        verifica(
            obtener_tamano_vista_ampliada(ruta_config) == 0,
            "C: config restaurada sigue con 0",
        )
    configurar_factor_vista_ampliada(1.6)

    with _ventana_con(factor=2.5) as (ventana, ruta_config):
        verifica(
            visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 2.5,
            "C: restauración histórica 2.5 sigue funcionando",
        )
    configurar_factor_vista_ampliada(1.6)

    # --- D) con Desactivado, hover no produce agrandado ---
    with _ventana_con(factor=0) as (ventana, ruta_config):
        tarjeta = dict(ventana.tarjetas)["clip.mp4"]
        etiqueta = tarjeta._etiquetas_previews[0]
        verifica(
            etiqueta._pixmap_original is not None,
            "D: preview tiene pixmap cargado para hover desactivado",
        )
        QApplication.sendEvent(etiqueta, QEvent(QEvent.Enter))
        QApplication.processEvents()
        verifica(
            not ventana._timer_vista_mostrar.isActive()
            and ventana._vista_pendiente is None
            and not ventana._vista.isVisible(),
            "D: con Desactivado no se inicia timer ni aparece popup",
        )
        # recorrer varias previews
        for e in tarjeta._etiquetas_previews:
            QApplication.sendEvent(e, QEvent(QEvent.Enter))
            QApplication.sendEvent(e, QEvent(QEvent.Leave))
        QApplication.processEvents()
        verifica(
            not ventana._vista.isVisible() and ventana._vista_pendiente is None,
            "D: recorrer previews con Desactivado no produce acción",
        )
        # incluso disparando timeout no aparece
        ventana._timer_vista_mostrar.timeout.emit()
        QApplication.processEvents()
        verifica(not ventana._vista.isVisible(), "D: timeout con Desactivado no muestra popup")

    # --- E) reactivar tamaño vuelve a habilitar sin reinicio ---
    with _ventana_con(factor=0) as (ventana, ruta_config):
        tarjeta = dict(ventana.tarjetas)["clip.mp4"]
        etiqueta = tarjeta._etiquetas_previews[0]
        # verificar desactivado
        QApplication.sendEvent(etiqueta, QEvent(QEvent.Enter))
        ventana._timer_vista_mostrar.timeout.emit()
        QApplication.processEvents()
        verifica(not ventana._vista.isVisible(), "E: precondición desactivado no muestra")
        # reactivar a 1.6 sin reinicio
        ventana._aplicar_tamano_vista_ampliada(1.6)
        verifica(
            visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 1.6
            and obtener_tamano_vista_ampliada(ruta_config) == 1.6,
            "E: reactivar a 1.6 actualiza estado y persistencia sin reinicio",
        )
        QApplication.sendEvent(etiqueta, QEvent(QEvent.Enter))
        verifica(
            ventana._vista_pendiente is not None and ventana._timer_vista_mostrar.isActive(),
            "E: reactivado timer se inicia",
        )
        ventana._timer_vista_mostrar.timeout.emit()
        QApplication.processEvents()
        verifica(ventana._vista.isVisible(), "E: reactivado popup vuelve a aparecer")
        ventana._ocultar_vista()
        # reactivar a 2.0 también funciona
        ventana._aplicar_tamano_vista_ampliada(2.0)
        verifica(visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 2.0, "E: reactivar a 2.0 funciona")
        QApplication.sendEvent(etiqueta, QEvent(QEvent.Enter))
        ventana._timer_vista_mostrar.timeout.emit()
        QApplication.processEvents()
        verifica(ventana._vista.isVisible(), "E: popup con 2.0 visible")

    # --- F) cambiar a Desactivado con popup visible lo oculta inmediatamente ---
    with _ventana_con(factor=1.6) as (ventana, ruta_config):
        tarjeta = dict(ventana.tarjetas)["clip.mp4"]
        etiqueta = tarjeta._etiquetas_previews[0]
        QApplication.sendEvent(etiqueta, QEvent(QEvent.Enter))
        ventana._timer_vista_mostrar.timeout.emit()
        QApplication.processEvents()
        verifica(ventana._vista.isVisible(), "F: precondición popup visible con 1.6")
        ventana._aplicar_tamano_vista_ampliada(0)
        QApplication.processEvents()
        verifica(
            not ventana._vista.isVisible() and not ventana._timer_vista_mostrar.isActive(),
            "F: aplicar Desactivado oculta popup inmediato y detiene timer",
        )
        # también via diálogo Preferencias
        ventana._aplicar_tamano_vista_ampliada(1.6)
        QApplication.sendEvent(etiqueta, QEvent(QEvent.Enter))
        ventana._timer_vista_mostrar.timeout.emit()
        QApplication.processEvents()
        verifica(ventana._vista.isVisible(), "F: popup visible antes de desactivar vía diálogo simulado")
        # simular diálogo aceptar Desactivado
        original_exec = visor_videos.PreferenciasDialog.exec

        def _aceptar_desactivado(self):
            self.combo_factor_vista.setCurrentIndex(self.combo_factor_vista.findText("Desactivado"))
            return QDialog.Accepted

        visor_videos.PreferenciasDialog.exec = _aceptar_desactivado
        try:
            ventana.boton_preferencias.click()
            QApplication.processEvents()
        finally:
            visor_videos.PreferenciasDialog.exec = original_exec
        verifica(
            not ventana._vista.isVisible() and visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 0,
            "F: diálogo Desactivado oculta popup y aplica sin reinicio",
        )

    # --- G) no afecta click/doble click/menu contextual ---
    with _ventana_con(factor=0) as (ventana, ruta_config):
        tarjeta = dict(ventana.tarjetas)["clip.mp4"]
        # verificar que vista está desactivada
        verifica(visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 0, "G: precondición Desactivado")
        # click selección
        recibidos_sel = []
        tarjeta.seleccionada.connect(lambda vid, ctrl: recibidos_sel.append((vid, ctrl)))
        # simular click izquierdo en tarjeta
        from PySide6.QtCore import Qt as QtCore
        from PySide6.QtGui import QMouseEvent

        # click simple: mousePressEvent izquierdo sin modificadores
        evt = QMouseEvent(QEvent.MouseButtonPress, QPoint(10, 10), QtCore.LeftButton, QtCore.LeftButton, QtCore.NoModifier)
        tarjeta.mousePressEvent(evt)
        QApplication.processEvents()
        verifica(len(recibidos_sel) >= 1, "G: click izquierdo sigue emitiendo seleccionada con Desactivado")

        recibidos_dbl = []
        tarjeta.doble_clic.connect(lambda vid: recibidos_dbl.append(vid))
        evt2 = QMouseEvent(QEvent.MouseButtonDblClick, QPoint(10, 10), QtCore.LeftButton, QtCore.LeftButton, QtCore.NoModifier)
        tarjeta.mouseDoubleClickEvent(evt2)
        QApplication.processEvents()
        verifica(len(recibidos_dbl) >= 1, "G: doble click sigue emitiendo doble_clic con Desactivado")

        recibidos_menu = []
        tarjeta.menu_contextual.connect(lambda vid: recibidos_menu.append(vid))
        evt3 = QMouseEvent(QEvent.MouseButtonPress, QPoint(10, 10), QtCore.RightButton, QtCore.RightButton, QtCore.NoModifier)
        tarjeta.mousePressEvent(evt3)
        QApplication.processEvents()
        verifica(len(recibidos_menu) >= 1, "G: click derecho sigue emitiendo menu_contextual con Desactivado")

        # verificar que retardo desactivado y tamaño desactivado son independientes (OR): reactivar tamaño pero retardo -1 sigue bloqueando
        from configuracion import guardar_retardo_vista_ampliada

        guardar_retardo_vista_ampliada(-1, ruta_config)
        ventana._retardo_vista_ampliada = -1
        ventana._aplicar_tamano_vista_ampliada(1.6)
        etiqueta = tarjeta._etiquetas_previews[0]
        QApplication.sendEvent(etiqueta, QEvent(QEvent.Enter))
        ventana._timer_vista_mostrar.timeout.emit()
        QApplication.processEvents()
        verifica(not ventana._vista.isVisible(), "G: retardo Desactivado bloquea aun con tamaño activo (OR)")
        # restaurar retardo y verificar que tamaño desactivado bloquea
        guardar_retardo_vista_ampliada(400, ruta_config)
        ventana._retardo_vista_ampliada = 400
        ventana._timer_vista_mostrar.setInterval(400)
        ventana._aplicar_tamano_vista_ampliada(0)
        QApplication.sendEvent(etiqueta, QEvent(QEvent.Enter))
        ventana._timer_vista_mostrar.timeout.emit()
        QApplication.processEvents()
        verifica(not ventana._vista.isVisible(), "G: tamaño Desactivado bloquea aun con retardo activo")

    # --- H) HOVER DESACTIVABLE — BOOL FALSE NO DEBE SER SENTINEL 0 ---
    # A: guardar False/True no cambia valor válido previo
    temp_config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(temp_config.name, "config.json")
    try:
        guardar_tamano_vista_ampliada(1.6, ruta_config)
        verifica(
            obtener_tamano_vista_ampliada(ruta_config) == 1.6,
            "H.A: precondición 1.6 válido",
        )
        res_false = guardar_tamano_vista_ampliada(False, ruta_config)
        verifica(
            res_false is None and obtener_tamano_vista_ampliada(ruta_config) == 1.6,
            "H.A: guardar False no cambia valor válido previo (conserva 1.6)",
            extra=res_false,
        )
        res_true = guardar_tamano_vista_ampliada(True, ruta_config)
        verifica(
            res_true is None and obtener_tamano_vista_ampliada(ruta_config) == 1.6,
            "H.A: guardar True no cambia valor válido previo (conserva 1.6)",
            extra=res_true,
        )
        # también con 2.5
        guardar_tamano_vista_ampliada(2.5, ruta_config)
        guardar_tamano_vista_ampliada(False, ruta_config)
        verifica(
            obtener_tamano_vista_ampliada(ruta_config) == 2.5,
            "H.A: guardar False conserva 2.5",
        )
        with open(ruta_config, encoding="utf-8") as f:
            contenido = json.load(f)
        verifica(
            contenido.get(CLAVE_TAMANO_VISTA_AMPLIADA) == 2.5,
            "H.A: JSON no fue sobrescrito por False",
            extra=contenido.get(CLAVE_TAMANO_VISTA_AMPLIADA),
        )
    finally:
        temp_config.cleanup()

    # B: JSON false/true leído por obtener devuelve 1.6 (default histórico)
    temp_config = tempfile.TemporaryDirectory()
    try:
        # json false -> Python False
        ruta_false = os.path.join(temp_config.name, "false.json")
        with open(ruta_false, "w", encoding="utf-8") as f:
            json.dump({CLAVE_TAMANO_VISTA_AMPLIADA: False}, f)
        verifica(
            obtener_tamano_vista_ampliada(ruta_false) == 1.6,
            "H.B: JSON false leído devuelve 1.6 (no 0)",
            extra=obtener_tamano_vista_ampliada(ruta_false),
        )
        ruta_true = os.path.join(temp_config.name, "true.json")
        with open(ruta_true, "w", encoding="utf-8") as f:
            json.dump({CLAVE_TAMANO_VISTA_AMPLIADA: True}, f)
        verifica(
            obtener_tamano_vista_ampliada(ruta_true) == 1.6,
            "H.B: JSON true leído devuelve 1.6 (no 0)",
            extra=obtener_tamano_vista_ampliada(ruta_true),
        )
        # verificar que 0 sí se persiste y se lee como Desactivado
        ruta_zero = os.path.join(temp_config.name, "zero.json")
        with open(ruta_zero, "w", encoding="utf-8") as f:
            json.dump({CLAVE_TAMANO_VISTA_AMPLIADA: 0}, f)
        verifica(
            obtener_tamano_vista_ampliada(ruta_zero) == 0,
            "H.B: JSON 0 int sigue devolviendo 0 (Desactivado)",
        )
        ruta_zero_float = os.path.join(temp_config.name, "zerof.json")
        with open(ruta_zero_float, "w", encoding="utf-8") as f:
            json.dump({CLAVE_TAMANO_VISTA_AMPLIADA: 0.0}, f)
        verifica(
            obtener_tamano_vista_ampliada(ruta_zero_float) == 0,
            "H.B: JSON 0.0 float sigue devolviendo 0 (Desactivado)",
        )
    finally:
        temp_config.cleanup()

    # C: configurar_factor_vista_ampliada(False) conserva factor previo
    configurar_factor_vista_ampliada(1.6)
    verifica(visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 1.6, "H.C: precondición factor 1.6")
    configurar_factor_vista_ampliada(False)
    verifica(
        visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 1.6,
        "H.C: configurar False conserva 1.6 (no desactiva)",
        extra=visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL,
    )
    configurar_factor_vista_ampliada(True)
    verifica(
        visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 1.6,
        "H.C: configurar True conserva 1.6 (no desactiva)",
        extra=visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL,
    )
    configurar_factor_vista_ampliada(2.0)
    verifica(visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 2.0, "H.C: configurar 2.0 válido")
    configurar_factor_vista_ampliada(False)
    verifica(
        visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 2.0,
        "H.C: configurar False conserva 2.0",
        extra=visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL,
    )
    # además False no debe habilitar desactivado si estaba activo: hover debe seguir funcionando
    # no testeamos hover aquí, solo factor

    # D: 0 y 0.0 siguen representando Desactivado correctamente
    temp_config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(temp_config.name, "config.json")
    try:
        guardar_tamano_vista_ampliada(1.6, ruta_config)
        res0 = guardar_tamano_vista_ampliada(0, ruta_config)
        verifica(
            res0 == 0 and obtener_tamano_vista_ampliada(ruta_config) == 0,
            "H.D: guardar 0 persiste Desactivado",
            extra=res0,
        )
        # verificar JSON int 0
        with open(ruta_config, encoding="utf-8") as f:
            contenido = json.load(f)
        verifica(contenido.get(CLAVE_TAMANO_VISTA_AMPLIADA) == 0, "H.D: JSON 0 int persistido")
        # 0.0 también
        res0f = guardar_tamano_vista_ampliada(0.0, ruta_config)
        verifica(
            res0f == 0 and obtener_tamano_vista_ampliada(ruta_config) == 0,
            "H.D: guardar 0.0 persiste Desactivado",
            extra=res0f,
        )
        # configurar_factor con 0 y 0.0 debe desactivar
        configurar_factor_vista_ampliada(1.6)
        configurar_factor_vista_ampliada(0)
        verifica(
            visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 0,
            "H.D: configurar 0 desactiva (factor 0)",
        )
        configurar_factor_vista_ampliada(1.6)
        configurar_factor_vista_ampliada(0.0)
        verifica(
            visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 0,
            "H.D: configurar 0.0 desactiva (factor 0)",
        )
        # round-trip 0 via guardar + configurar
        guardar_tamano_vista_ampliada(0, ruta_config)
        val = obtener_tamano_vista_ampliada(ruta_config)
        configurar_factor_vista_ampliada(val)
        verifica(visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 0, "H.D: round-trip 0 -> configurar 0")
    finally:
        temp_config.cleanup()

    configurar_factor_vista_ampliada(1.6)
    configurar_tamano_miniaturas("mediano")

    total = _CONTADOR[0] - 1
    errores = _FALLOS[0]
    print(f"TOTAL={total - errores}/{total}")
    if errores == 0:
        print("RESULTADO_FINAL=OK")
    else:
        print("RESULTADO_FINAL=ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
