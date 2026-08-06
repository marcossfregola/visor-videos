import os
import sys
import tempfile
import time

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from arbol_navegacion import TEXTO_RAIZ, ArbolNavegacion, discos_disponibles
from tareas_videos import conectar_bd, guardar_videos
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
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    guardar_videos(
        [
            {
                "nombre": f"v{i:03d}.mp4",
                "ruta": os.path.join(temp.name, f"v{i:03d}.mp4"),
                "extension": ".mp4",
                "fecha_importacion": "2026-08-03T00:00:00",
            }
            for i in range(1, 51)
        ],
        ruta_db,
    )

    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.resize(900, 600)
    ventana.show()
    esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)

    arbol = ventana.findChild(ArbolNavegacion)
    print(f"arbol_encontrado={arbol is not None}")

    discos = discos_disponibles()
    print(f"discos_sistema={discos}")

    raiz = arbol.topLevelItem(0)
    print(f"raiz_texto={raiz.text(0)}")
    print(f"raiz_es_este_equipo={raiz.text(0) == TEXTO_RAIZ}")
    print(f"raiz_expandida={raiz.isExpanded()}")
    hijos = [raiz.child(i).text(0) for i in range(raiz.childCount())]
    print(f"hijos_arbol={hijos}")
    print(f"hijos_coinciden_con_discos={hijos == discos}")

    placeholders = [
        l for l in ventana.findChildren(QLabel) if l.text() == "Panel de navegacion"
    ]
    print(f"placeholder_eliminado={len(placeholders) == 0}")

    print(f"tarjetas_cargadas={len(ventana.tarjetas)}")
    print(f"contador={ventana.contador.text()}")
    print(f"panel_derecho_funcional={len(ventana.tarjetas) == 50}")

    splitter = ventana.centralWidget()
    print(f"splitter_es_qsplitter={type(splitter).__name__ == 'QSplitter'}")
    print(f"splitter_handle_width={splitter.handleWidth()}")
    tamanos_iniciales = list(splitter.sizes())
    splitter.setSizes([300, 620])
    QApplication.processEvents()
    tamanos = list(splitter.sizes())
    print(f"splitter_tamanos_iniciales={tamanos_iniciales}")
    print(f"splitter_tamanos_tras_ajuste={tamanos}")
    print(f"splitter_redimensionable={tamanos[0] > tamanos_iniciales[0] and abs(tamanos[0] - 300) <= 1}")

    carpeta_antes = ventana.carpeta_seleccionada
    etiqueta_antes = ventana.etiqueta_carpeta.text()
    activo_antes = ventana.gestor.activo
    pendientes_antes = (
        ventana._escaneo_pendiente
        or ventana._tamanos_pendiente
        or ventana._ffprobe_pendiente
        or ventana._miniaturas_pendiente
        or ventana._guardado_pendiente
    )
    if raiz.childCount() > 0:
        item = raiz.child(0)
        rect = arbol.visualItemRect(item)
        QTest.mouseClick(
            arbol.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center()
        )
        QApplication.processEvents()
        print(f"clic_current_item_cambio={arbol.currentItem() is not None}")
        print(f"clic_carpeta_cambio={ventana.carpeta_seleccionada != carpeta_antes}")
        print(f"clic_etiqueta_cambio={ventana.etiqueta_carpeta.text() != etiqueta_antes}")
        print(f"clic_gestor_activo={ventana.gestor.activo}")
        pendientes_despues = (
            ventana._escaneo_pendiente
            or ventana._tamanos_pendiente
            or ventana._ffprobe_pendiente
            or ventana._miniaturas_pendiente
            or ventana._guardado_pendiente
        )
        print(f"clic_pendientes_cambio={pendientes_despues != pendientes_antes}")

    captura = os.path.join(temp.name, "captura.png")
    pixmap = ventana.grab()
    guardada = pixmap.save(captura)
    print(f"captura_guardada={guardada}")
    print(f"captura_ruta={captura}")

    ventana.close()
    ventana.gestor.cerrar()
    temp.cleanup()

    sys.exit(0)


if __name__ == "__main__":
    main()
