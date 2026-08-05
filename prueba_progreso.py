import ast
import os
import sys
import tempfile

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtWidgets import QApplication, QProgressBar

import visor_videos
from visor_videos import VisorVideos

QT_MENSAJES = []


def _mensaje_qt(tipo, contexto, texto):
    QT_MENSAJES.append(str(texto))


qInstallMessageHandler(_mensaje_qt)

_CONTADOR = [0]


def _paso():
    _CONTADOR[0] += 1


class _Texto:
    OK = 0
    ERROR = 0

    @classmethod
    def ok(cls, mensaje):
        cls.OK += 1
        print(f"T{_paso() or _CONTADOR[0]:02d} OK - {mensaje}")

    @classmethod
    def falla(cls, mensaje):
        cls.ERROR += 1
        print(f"T{_paso() or _CONTADOR[0]:02d} ERROR - {mensaje}")


def _verificar(condicion, descripcion):
    if condicion:
        _Texto.ok(descripcion)
    else:
        _Texto.falla(descripcion)


def main():
    app = QApplication(sys.argv)

    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "cat_no_existe.db")
    _CONFIG = tempfile.TemporaryDirectory()
    os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG.name, "config.json")

    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.show()

    _verificar(
        hasattr(ventana, "barra_progreso"),
        "barra_progreso existe",
    )
    _verificar(
        isinstance(ventana.barra_progreso, QProgressBar),
        "barra_progreso es QProgressBar",
    )
    _verificar(
        ventana.barra_progreso.minimum() == 0 and ventana.barra_progreso.maximum() == 0,
        "barra_progreso modo indeterminado (rango 0-0)",
    )
    _verificar(
        not ventana.barra_progreso.isVisible(),
        "barra_progreso invisible al inicio",
    )

    _verificar(
        hasattr(ventana, "_mostrar_progreso"),
        "metodo _mostrar_progreso existe",
    )
    _verificar(
        hasattr(ventana, "_ocultar_progreso"),
        "metodo _ocultar_progreso existe",
    )
    _verificar(
        hasattr(ventana, "_pipeline_activo"),
        "bandera _pipeline_activo existe",
    )
    _verificar(
        not ventana._pipeline_activo,
        "_pipeline_activo es False al inicio",
    )

    ventana._mostrar_progreso("Probando…")
    _verificar(
        ventana.barra_progreso.isVisible(),
        "barra visible tras _mostrar_progreso()",
    )
    _verificar(
        ventana._pipeline_activo,
        "_pipeline_activo True tras _mostrar_progreso()",
    )
    _verificar(
        "Probando" in ventana.barra_progreso.format(),
        "Formato contiene texto 'Probando'",
    )

    ventana._ocultar_progreso()
    _verificar(
        not ventana.barra_progreso.isVisible(),
        "barra invisible tras _ocultar_progreso()",
    )
    _verificar(
        not ventana._pipeline_activo,
        "_pipeline_activo False tras _ocultar_progreso()",
    )

    ventana.close()
    ventana.gestor.cerrar()
    ventana.gestor_previews.cerrar()
    temp.cleanup()
    _CONFIG.cleanup()

    print(f"TOTAL={_Texto.OK}/{_Texto.OK + _Texto.ERROR}")
    if _Texto.ERROR == 0:
        print("RESULTADO_FINAL=OK")
    else:
        print("RESULTADO_FINAL=ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
