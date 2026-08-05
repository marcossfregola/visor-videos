import os
import sys
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QFileDialog

import visor_videos
from visor_videos import VisorVideos


def main():
    app = QApplication(sys.argv)

    def esperar(predicado, intentos=400):
        for _ in range(intentos):
            QApplication.processEvents()
            if predicado():
                return True
            time.sleep(0.02)
        QApplication.processEvents()
        return predicado()

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
            for i in range(1, 5)
        ],
        ruta_db,
    )

    _CONFIG = tempfile.TemporaryDirectory()
    os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG.name, "config.json")

    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.resize(720, 540)
    ventana.show()

    esperar(lambda: ventana._carga_completada and ventana.gestor.hilo is None)

    nombres = [n for n, _ in ventana.tarjetas]
    print(f"tarjetas_cargadas={len(nombres)}")

    print(f"seleccion_inicial={len(ventana._nombres_seleccionados)}")

    def click(tarjeta, ctrl=False):
        m = Qt.ControlModifier if ctrl else Qt.NoModifier
        punto = tarjeta.rect().center()
        evento = QMouseEvent(
            QMouseEvent.MouseButtonPress,
            punto,
            Qt.LeftButton,
            Qt.LeftButton,
            m,
        )
        QApplication.sendEvent(tarjeta, evento)
        QApplication.processEvents()

    def doble_click(tarjeta):
        punto = tarjeta.rect().center()
        evento = QMouseEvent(
            QMouseEvent.MouseButtonDblClick,
            punto,
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        QApplication.sendEvent(tarjeta, evento)
        QApplication.processEvents()

    t0 = ventana.tarjetas[0][1]
    t1 = ventana.tarjetas[1][1]
    t2 = ventana.tarjetas[2][1]

    click(t0)
    sel1 = len(ventana._nombres_seleccionados)
    print(f"seleccion_simple={sel1} seleccionados={ventana._nombres_seleccionados}")

    click(t1)
    sel2 = len(ventana._nombres_seleccionados)
    print(f"seleccion_reemplaza={sel2} seleccionados={ventana._nombres_seleccionados}")

    click(t2, ctrl=True)
    sel3 = len(ventana._nombres_seleccionados)
    print(f"ctrl_agrega={sel3} seleccionados={ventana._nombres_seleccionados}")

    click(t1, ctrl=True)
    sel4 = len(ventana._nombres_seleccionados)
    print(f"ctrl_quita={sel4} seleccionados={ventana._nombres_seleccionados}")

    ventana.filtrar("v003")
    sel_filtro = len(ventana._nombres_seleccionados)
    print(f"seleccion_tras_filtro={sel_filtro} seleccionados={ventana._nombres_seleccionados}")
    ventana.filtrar("")

    doble_click(t0)
    print(f"doble_clic_mensaje={repr(ventana.mensaje_carpeta.text())}")

    ok = sel1 == 1 and sel2 == 1 and sel3 == 2 and sel4 == 1 and sel_filtro == 1
    print(f"RESULTADO_FINAL={'OK' if ok else 'ERROR'}")

    ventana.close()
    ventana.gestor.cerrar()
    ventana.gestor_previews.cerrar()
    temp.cleanup()
    _CONFIG.cleanup()


if __name__ == "__main__":
    main()
