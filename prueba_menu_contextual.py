import os
import sys
import tempfile
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog

import apertura_videos
import visor_videos
from visor_videos import Tarjeta, VisorVideos

_CONTADOR = [0]
_FALLOS = [0]


def _paso():
    _CONTADOR[0] += 1
    return _CONTADOR[0]


def ok(mensaje):
    print(f"T{_paso():02d} OK - {mensaje}")


def falla(mensaje, extra=None):
    _FALLOS[0] += 1
    texto = f"T{_CONTADOR[0]:02d} ERROR - {mensaje}"
    if extra is not None:
        texto += f" ({extra})"
    print(texto)


def verifica(condicion, descripcion):
    if condicion:
        ok(descripcion)
    else:
        falla(descripcion)


def _derecho(tarjeta):
    punto = tarjeta.rect().center()
    evento = QMouseEvent(
        QMouseEvent.MouseButtonPress,
        punto,
        Qt.RightButton,
        Qt.RightButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(tarjeta, evento)
    QApplication.processEvents()


def main():
    app = QApplication(sys.argv)

    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")

    from tareas_videos import conectar_bd, guardar_videos
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    guardar_videos(
        [
            {
                "nombre": f"v{i:03d}.mp4",
                "ruta": os.path.join(temp.name, f"v{i:03d}.mp4"),
                "extension": ".mp4",
                "fecha_importacion": "2026-08-05T00:00:00",
            }
            for i in range(1, 6)
        ],
        ruta_db,
    )

    _CONFIG = tempfile.TemporaryDirectory()
    os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG.name, "config.json")

    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.resize(720, 540)
    ventana.show()

    def esperar(predicado, intentos=200):
        for _ in range(intentos):
            QApplication.processEvents()
            if predicado():
                return True
            time.sleep(0.02)
        QApplication.processEvents()
        return predicado()

    esperar(lambda: ventana._carga_completada and ventana.gestor.hilo is None)

    _CONTADOR[0] = 0

    # --- senial menu_contextual existe en Tarjeta ---
    verifica(
        hasattr(Tarjeta, "menu_contextual"),
        "Tarjeta tiene senial menu_contextual",
    )

    # Desconectar menu_contextual de todas las tarjetas para evitar
    # que QMenu.exec() bloquee durante las pruebas de eventos.
    for _, tarjeta in ventana.tarjetas:
        try:
            tarjeta.menu_contextual.disconnect()
        except RuntimeError:
            pass

    # --- clic derecho sobre tarjeta no seleccionada la selecciona ---
    ventana._limpiar_seleccion()
    nombres = [nombre for nombre, _ in ventana.tarjetas]
    tarjeta_0 = ventana.tarjetas[0][1]
    verifica(
        not tarjeta_0._seleccionada,
        "tarjeta no seleccionada inicialmente",
    )
    _derecho(tarjeta_0)
    verifica(
        len(ventana._nombres_seleccionados) == 1,
        "clic derecho en no seleccionada: 1 elemento seleccionado",
    )
    verifica(
        nombres[0] in ventana._nombres_seleccionados,
        "clic derecho en no seleccionada: nombre correcto",
    )
    verifica(
        tarjeta_0._seleccionada,
        "clic derecho en no seleccionada: tarjeta marcada",
    )

    # --- clic derecho sobre seleccion multiple la conserva ---
    ventana._limpiar_seleccion()
    ventana._al_seleccionar_tarjeta(nombres[0], False)
    ventana._al_seleccionar_tarjeta(nombres[2], True)
    tarjeta_2 = ventana.tarjetas[2][1]
    verifica(
        len(ventana._nombres_seleccionados) == 2,
        "seleccion multiple previa: 2 elementos",
    )
    _derecho(tarjeta_2)
    verifica(
        len(ventana._nombres_seleccionados) == 2,
        "clic derecho en seleccion multiple: 2 elementos conservados",
    )
    verifica(
        nombres[0] in ventana._nombres_seleccionados
        and nombres[2] in ventana._nombres_seleccionados,
        "clic derecho en seleccion multiple: ambos nombres conservados",
    )

    # --- clic derecho emite menu_contextual con el nombre correcto ---
    recibidos = []

    def capturar_menu(nombre):
        recibidos.append(nombre)

    tarjeta_0.menu_contextual.connect(capturar_menu)
    _derecho(tarjeta_0)
    verifica(
        len(recibidos) == 1 and (recibidos[0] == tarjeta_0.nombre or recibidos[0] == tarjeta_0._video_id),
        "menu_contextual emite nombre correcto al clic derecho",
    )
    tarjeta_0.menu_contextual.disconnect(capturar_menu)

    # --- _abrir_carpeta llama os.startfile con la carpeta ---
    carpeta_temp = tempfile.TemporaryDirectory()
    try:
        for nombre_arch in ["x001.mp4"]:
            with open(os.path.join(carpeta_temp.name, nombre_arch), "w") as f:
                f.write("contenido")
        original_startfile = os.startfile
        llamadas = []

        def _startfile_prueba(ruta):
            llamadas.append(ruta)

        os.startfile = _startfile_prueba
        try:
            ventana.carpeta_seleccionada = carpeta_temp.name
            ventana._abrir_carpeta("x001.mp4")
            carpeta_esperada = os.path.abspath(carpeta_temp.name)
            verifica(
                llamadas == [carpeta_esperada],
                "_abrir_carpeta llama os.startfile con la carpeta",
            )
        finally:
            os.startfile = original_startfile
    finally:
        carpeta_temp.cleanup()

    # --- _abrir_carpeta sin carpeta seleccionada no falla ---
    ventana.carpeta_seleccionada = None
    try:
        ventana._abrir_carpeta("x001.mp4")
        verifica(True, "_abrir_carpeta sin carpeta no lanza excepcion")
    except Exception as exc:
        falla(f"_abrir_carpeta sin carpeta lanzo {type(exc).__name__}")

    # --- _copiar_ruta pone la ruta en el portapapeles ---
    carpeta_temp2 = tempfile.TemporaryDirectory()
    try:
        with open(os.path.join(carpeta_temp2.name, "y001.mp4"), "w") as f:
            f.write("contenido")
        ventana.carpeta_seleccionada = carpeta_temp2.name
        ventana._copiar_ruta("y001.mp4")
        ruta_esperada = os.path.abspath(
            os.path.join(carpeta_temp2.name, "y001.mp4")
        )
        clipboard = QApplication.clipboard().text()
        verifica(
            clipboard == ruta_esperada,
            "_copiar_ruta: ruta en portapapeles correcta",
        )
    finally:
        carpeta_temp2.cleanup()

    # --- _copiar_ruta sin carpeta seleccionada no falla ---
    ventana.carpeta_seleccionada = None
    QApplication.clipboard().setText("")
    try:
        ventana._copiar_ruta("x001.mp4")
        verifica(
            QApplication.clipboard().text() == "",
            "_copiar_ruta sin carpeta no modifica el portapapeles",
        )
    except Exception as exc:
        falla(f"_copiar_ruta sin carpeta lanzo {type(exc).__name__}")

    # --- doble clic sigue funcionando tras agregar menu contextual ---
    doble_recibido = []

    def capturar_doble(nombre):
        doble_recibido.append(nombre)

    tarjeta_0.doble_clic.connect(capturar_doble)
    QTest.mouseDClick(tarjeta_0, Qt.LeftButton)
    QApplication.processEvents()
    verifica(
        len(doble_recibido) == 1 and (doble_recibido[0] == tarjeta_0.nombre or doble_recibido[0] == tarjeta_0._video_id),
        "doble clic sigue funcionando con menu contextual",
    )

    # --- clic izquierdo sin Ctrl sigue funcionando ---
    ventana._limpiar_seleccion()
    QTest.mouseClick(tarjeta_0, Qt.LeftButton)
    QApplication.processEvents()
    verifica(
        len(ventana._nombres_seleccionados) == 1,
        "clic izquierdo sin Ctrl sigue seleccionando",
    )

    # --- _mostrar_menu_contextual existe ---
    verifica(
        hasattr(ventana, "_mostrar_menu_contextual"),
        "VisorVideos tiene metodo _mostrar_menu_contextual",
    )

    # --- _abrir_carpeta existe ---
    verifica(
        hasattr(ventana, "_abrir_carpeta"),
        "VisorVideos tiene metodo _abrir_carpeta",
    )

    # --- _copiar_ruta existe ---
    verifica(
        hasattr(ventana, "_copiar_ruta"),
        "VisorVideos tiene metodo _copiar_ruta",
    )

    ventana.close()
    ventana.gestor.cerrar()
    ventana.gestor_previews.cerrar()
    temp.cleanup()
    _CONFIG.cleanup()

    total = _CONTADOR[0]
    errores = _FALLOS[0]
    print(f"TOTAL={total - errores}/{total}")
    if errores == 0:
        print("RESULTADO_FINAL=OK")
    else:
        print("RESULTADO_FINAL=ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
