import ast
import os
import sys
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, qInstallMessageHandler
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QFileDialog

import visor_videos
from visor_videos import ESTILO_SELECCIONADA, Tarjeta, VisorVideos

QT_MENSAJES = []


def _mensaje_qt(tipo, contexto, texto):
    QT_MENSAJES.append(str(texto))


qInstallMessageHandler(_mensaje_qt)

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

    verifica(
        hasattr(ventana, "_nombres_seleccionados"),
        "_nombres_seleccionados existe",
    )
    verifica(
        len(ventana._nombres_seleccionados) == 0,
        "seleccion vacia al inicio",
    )
    verifica(
        len(ventana.nombres_seleccionados) == 0,
        "nombres_seleccionados (propiedad) vacia al inicio",
    )
    verifica(
        hasattr(Tarjeta, "seleccionada"),
        "Tarjeta tiene senial seleccionada",
    )
    verifica(
        hasattr(Tarjeta, "marcar_seleccionada"),
        "Tarjeta tiene metodo marcar_seleccionada",
    )

    nombres_tarjetas = [nombre for nombre, _ in ventana.tarjetas]
    primer_nombre = nombres_tarjetas[0]

    # --- seleccion simple ---
    ventana._al_seleccionar_tarjeta(primer_nombre, False)
    verifica(
        len(ventana._nombres_seleccionados) == 1,
        "seleccion simple: 1 elemento seleccionado",
    )
    verifica(
        primer_nombre in ventana._nombres_seleccionados,
        "seleccion simple: nombre correcto en conjunto",
    )
    verifica(
        ventana.tarjetas[0][1]._seleccionada,
        "seleccion simple: tarjeta marcada como _seleccionada",
    )

    # --- seleccion simple reemplaza ---
    segundo_nombre = nombres_tarjetas[1]
    ventana._al_seleccionar_tarjeta(segundo_nombre, False)
    verifica(
        len(ventana._nombres_seleccionados) == 1,
        "seleccion simple reemplaza: 1 elemento",
    )
    verifica(
        segundo_nombre in ventana._nombres_seleccionados,
        "seleccion simple reemplaza: segundo seleccionado",
    )
    verifica(
        primer_nombre not in ventana._nombres_seleccionados,
        "seleccion simple reemplaza: primero deseleccionado",
    )

    # --- Ctrl+click agrega ---
    tercer_nombre = nombres_tarjetas[2]
    ventana._al_seleccionar_tarjeta(tercer_nombre, True)
    verifica(
        len(ventana._nombres_seleccionados) == 2,
        "Ctrl+click agrega: 2 elementos seleccionados",
    )
    verifica(
        segundo_nombre in ventana._nombres_seleccionados
        and tercer_nombre in ventana._nombres_seleccionados,
        "Ctrl+click agrega: ambos nombres en conjunto",
    )

    # --- Ctrl+click quita ---
    ventana._al_seleccionar_tarjeta(segundo_nombre, True)
    verifica(
        len(ventana._nombres_seleccionados) == 1,
        "Ctrl+click quita: 1 elemento restante",
    )
    verifica(
        tercer_nombre in ventana._nombres_seleccionados,
        "Ctrl+click quita: tercero sigue seleccionado",
    )
    verifica(
        segundo_nombre not in ventana._nombres_seleccionados,
        "Ctrl+click quita: segundo removido",
    )

    # --- _limpiar_seleccion ---
    ventana._limpiar_seleccion()
    verifica(
        len(ventana._nombres_seleccionados) == 0,
        "_limpiar_seleccion vacia el conjunto",
    )

    # --- Estilo visual ---
    tarjeta = ventana.tarjetas[0][1]
    tarjeta.marcar_seleccionada(True)
    verifica(
        tarjeta._seleccionada,
        "marcar_seleccionada(True): flag interno",
    )
    verifica(
        ESTILO_SELECCIONADA in tarjeta.styleSheet(),
        "marcar_seleccionada(True): stylesheet aplicado",
    )
    tarjeta.marcar_seleccionada(False)
    verifica(
        not tarjeta._seleccionada,
        "marcar_seleccionada(False): flag interno falso",
    )
    verifica(
        tarjeta.styleSheet() == "",
        "marcar_seleccionada(False): stylesheet vacio",
    )

    # --- mousePressEvent emite senial ---
    seniales_recibidas = []

    def capturar(nombre, ctrl):
        seniales_recibidas.append((nombre, ctrl))

    tarjeta.seleccionada.connect(capturar)
    punto = tarjeta.rect().center()
    evento_sin_ctrl = QMouseEvent(
        QMouseEvent.MouseButtonPress,
        punto,
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(tarjeta, evento_sin_ctrl)
    verifica(
        len(seniales_recibidas) == 1 and not seniales_recibidas[0][1],
        "mousePressEvent sin Ctrl emite (nombre, ctrl=False)",
    )

    seniales_recibidas.clear()
    evento_con_ctrl = QMouseEvent(
        QMouseEvent.MouseButtonPress,
        punto,
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.ControlModifier,
    )
    QApplication.sendEvent(tarjeta, evento_con_ctrl)
    verifica(
        len(seniales_recibidas) == 1 and seniales_recibidas[0][1],
        "mousePressEvent con Ctrl emite (nombre, ctrl=True)",
    )

    seniales_recibidas.clear()

    # --- doble clic sigue funcionando ---
    doble_recibido = []

    def capturar_doble(nombre):
        doble_recibido.append(nombre)

    tarjeta.doble_clic.connect(capturar_doble)

    evento_doble = QMouseEvent(
        QMouseEvent.MouseButtonDblClick,
        punto,
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(tarjeta, evento_doble)
    verifica(
        len(doble_recibido) == 1 and doble_recibido[0] == tarjeta.nombre,
        "doble clic sigue emitiendo doble_clic",
    )

    # --- seleccion persiste a traves del filtro ---
    ventana._limpiar_seleccion()
    ventana._al_seleccionar_tarjeta(nombres_tarjetas[0], False)
    ventana._al_seleccionar_tarjeta(nombres_tarjetas[2], True)
    seleccion_previa = set(ventana._nombres_seleccionados)
    ventana.filtrar("v001")
    seleccion_post = set(ventana._nombres_seleccionados)
    verifica(
        seleccion_previa == seleccion_post,
        "seleccion persiste tras filtrar",
    )

    # --- _reemplazar_tarjetas restaura la seleccion ---
    ventana._al_seleccionar_tarjeta(nombres_tarjetas[0], False)
    ventana._reemplazar_tarjetas([(nombres_tarjetas[0], None, None, None, None, None, None)])
    verifica(
        len(ventana._nombres_seleccionados) == 1,
        "_reemplazar_tarjetas restaura la seleccion",
    )
    verifica(
        nombres_tarjetas[0] in ventana._nombres_seleccionados,
        "_reemplazar_tarjetas: nombre restaurado correcto",
    )
    verifica(
        ventana.tarjetas[0][1]._seleccionada,
        "_reemplazar_tarjetas: tarjeta restaurada marcada",
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
