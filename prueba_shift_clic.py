import os
import sys
import tempfile
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

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


def _shift_clic(tarjeta):
    punto = tarjeta.rect().center()
    evento = QMouseEvent(
        QMouseEvent.MouseButtonPress,
        punto,
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.ShiftModifier,
    )
    QApplication.sendEvent(tarjeta, evento)
    QApplication.processEvents()


def _ctrl_clic(tarjeta):
    punto = tarjeta.rect().center()
    evento = QMouseEvent(
        QMouseEvent.MouseButtonPress,
        punto,
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.ControlModifier,
    )
    QApplication.sendEvent(tarjeta, evento)
    QApplication.processEvents()


def _clic(tarjeta):
    punto = tarjeta.rect().center()
    evento = QMouseEvent(
        QMouseEvent.MouseButtonPress,
        punto,
        Qt.LeftButton,
        Qt.LeftButton,
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
            for i in range(1, 9)
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

    # Desconectar seniales que bloquean (menu_contextual)
    for _, tarjeta in ventana.tarjetas:
        try:
            tarjeta.menu_contextual.disconnect()
        except RuntimeError:
            pass

    tarjetas = [t for _, t in ventana.tarjetas]
    verifica(len(tarjetas) >= 8, "hay al menos 8 tarjetas cargadas")

    # --- senial seleccion_por_rango existe ---
    verifica(
        hasattr(Tarjeta, "seleccion_por_rango"),
        "Tarjeta tiene senial seleccion_por_rango",
    )

    # --- _ancla_seleccion existe ---
    verifica(
        hasattr(ventana, "_ancla_seleccion"),
        "VisorVideos tiene atributo _ancla_seleccion",
    )

    # --- _al_seleccion_por_rango existe ---
    verifica(
        hasattr(ventana, "_al_seleccion_por_rango"),
        "VisorVideos tiene metodo _al_seleccion_por_rango",
    )

    # --- Shift+clic sin seleccion previa equivale a clic normal ---
    ventana._limpiar_seleccion()
    ventana._ancla_seleccion = None
    _shift_clic(tarjetas[3])
    verifica(
        len(ventana._nombres_seleccionados) == 1,
        "Shift+clic sin ancla: 1 elemento seleccionado",
    )
    verifica(
        tarjetas[3]._seleccionada,
        "Shift+clic sin ancla: tarjeta marcada",
    )
    verifica(
        ventana._ancla_seleccion is not None,
        "Shift+clic sin ancla: ancla establecida",
    )

    # --- Shift+clic hacia abajo desde ancla ---
    ventana._limpiar_seleccion()
    _clic(tarjetas[1])  # ancla en indice 1
    ventana._ancla_seleccion = tarjetas[1].nombre
    _shift_clic(tarjetas[4])
    verifica(
        len(ventana._nombres_seleccionados) == 4,
        "Shift+clic hacia abajo: 4 elementos (indices 1-4)",
    )
    for i in range(1, 5):
        verifica(
            tarjetas[i]._seleccionada,
            f"Shift+clic hacia abajo: tarjeta indice {i} marcada",
        )
    verifica(
        not tarjetas[0]._seleccionada,
        "Shift+clic hacia abajo: tarjeta indice 0 no marcada",
    )
    verifica(
        not tarjetas[5]._seleccionada,
        "Shift+clic hacia abajo: tarjeta indice 5 no marcada",
    )

    # --- Shift+clic hacia arriba desde ancla ---
    ventana._limpiar_seleccion()
    _clic(tarjetas[5])  # ancla en indice 5
    ventana._ancla_seleccion = tarjetas[5].nombre
    _shift_clic(tarjetas[2])
    verifica(
        len(ventana._nombres_seleccionados) == 4,
        "Shift+clic hacia arriba: 4 elementos (indices 2-5)",
    )
    for i in range(2, 6):
        verifica(
            tarjetas[i]._seleccionada,
            f"Shift+clic hacia arriba: tarjeta indice {i} marcada",
        )

    # --- ancla no se actualiza al hacer Shift+clic ---
    ventana._limpiar_seleccion()
    _clic(tarjetas[1])
    ancla_pre = ventana._ancla_seleccion
    _shift_clic(tarjetas[4])
    verifica(
        ventana._ancla_seleccion == ancla_pre,
        "Shift+clic no modifica el ancla",
    )

    # --- compatibilidad con Ctrl+clic sigue funcionando ---
    ventana._limpiar_seleccion()
    ventana._ancla_seleccion = None
    _clic(tarjetas[0])
    _ctrl_clic(tarjetas[2])
    verifica(
        len(ventana._nombres_seleccionados) == 2,
        "Ctrl+clic sigue agregando con Shift presente en codigo",
    )
    verifica(
        tarjetas[0]._seleccionada and tarjetas[2]._seleccionada,
        "Ctrl+clic: ambas tarjetas marcadas",
    )

    # --- doble clic sigue funcionando ---
    doble_recibido = []

    def capturar_doble(nombre):
        doble_recibido.append(nombre)

    tarjetas[0].doble_clic.connect(capturar_doble)
    QTest.mouseDClick(tarjetas[0], Qt.LeftButton)
    QApplication.processEvents()
    verifica(
        len(doble_recibido) == 1 and (doble_recibido[0] == tarjetas[0].nombre or doble_recibido[0] == tarjetas[0]._video_id),
        "doble clic sigue funcionando con Shift implementado",
    )

    # --- senial seleccion_por_rango se emite con Shift+clic ---
    recibidos = []

    def capturar_rango(nombre):
        recibidos.append(nombre)

    tarjetas[5].seleccion_por_rango.connect(capturar_rango)
    _shift_clic(tarjetas[5])
    verifica(
        len(recibidos) == 1 and (recibidos[0] == tarjetas[5].nombre or recibidos[0] == tarjetas[5]._video_id),
        "seleccion_por_rango emitida con nombre correcto",
    )
    tarjetas[5].seleccion_por_rango.disconnect(capturar_rango)

    # --- Shift+clic con ancla fuera de visibles equivale a clic normal ---
    ventana._limpiar_seleccion()
    ventana._ancla_seleccion = "inexistente_xyz.mp4"
    _shift_clic(tarjetas[0])
    verifica(
        len(ventana._nombres_seleccionados) == 1,
        "Shift+clic con ancla fuera de visibles: 1 elemento",
    )
    verifica(
        ventana._ancla_seleccion == tarjetas[0].nombre,
        "Shift+clic con ancla fuera de visibles: ancla actualizada",
    )

    # --- restauracion tras reemplazar limpia el ancla ---
    ventana._limpiar_seleccion()
    _clic(tarjetas[2])
    seleccion_previa = ventana._ancla_seleccion
    verifica(seleccion_previa is not None, "ancla establecida antes de reemplazar")
    ventana._reemplazar_tarjetas([])
    verifica(
        ventana._ancla_seleccion is None,
        "_reemplazar_tarjetas limpia el ancla",
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
