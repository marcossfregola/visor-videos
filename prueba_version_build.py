"""Pruebas de identificación visible de versión/build (mejora de diagnóstico).

Cubre:
- constantes centrales de versión y build en `configuracion`;
- texto exacto `Beta 7 - B7.13`;
- etiqueta visible en la ventana principal (status bar).

No depende de Git en tiempo de ejecución: los valores quedan embebidos en la
build desde el código fuente.
"""

import os
import sys
import tempfile

from PySide6.QtWidgets import QApplication, QLabel

import configuracion
import visor_videos
from tareas_videos import conectar_bd
from visor_videos import VisorVideos


def test_01():
    ok_producto = configuracion.VERSION_PRODUCTO == "Beta 7"
    ok_build = configuracion.BUILD_IDENTIFICADOR == "B7.13"
    return ok_producto and ok_build, (
        f"version={configuracion.VERSION_PRODUCTO} "
        f"build={configuracion.BUILD_IDENTIFICADOR}"
    )


def test_02():
    esperado = "Beta 7 - B7.13"
    ok = configuracion.TEXTO_VERSION_BUILD == esperado
    return ok, f"texto={configuracion.TEXTO_VERSION_BUILD!r} esperado={esperado!r}"


def test_03():
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    ventana = None
    try:
        ventana = VisorVideos(ruta_db=ruta_db)
        ventana.resize(720, 540)
        ventana.show()
        QApplication.processEvents()
        etiqueta = ventana.etiqueta_version
        ok_existe = isinstance(etiqueta, QLabel)
        ok_texto = etiqueta.text() == configuracion.TEXTO_VERSION_BUILD
        ok_visible = etiqueta.isVisible()
        ok_en_barra = etiqueta.parent() is ventana.statusBar()
        return ok_existe and ok_texto and ok_visible and ok_en_barra, (
            f"texto={etiqueta.text()!r} visible={ok_visible} "
            f"en_status_bar={ok_en_barra}"
        )
    finally:
        if ventana is not None:
            ventana.close()
            ventana.gestor.cerrar()
        temp.cleanup()


def main():
    app = QApplication(sys.argv)
    pruebas = [test_01, test_02, test_03]
    resultados = []
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, detalle = fn()
        except Exception as exc:
            ok, detalle = False, f"excepcion: {type(exc).__name__}: {exc}"
        resultados.append((i, ok, detalle))
        print(f"P{i:02d} {'OK' if ok else 'FALLO'} - {detalle}")

    ok_total = all(ok for _, ok, _ in resultados)
    aprobadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprobadas}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
