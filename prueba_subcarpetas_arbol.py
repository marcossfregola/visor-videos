import os
import sys
import tempfile
import time
from unittest import mock

from PySide6.QtWidgets import QApplication, QFileDialog

import arbol_navegacion
import visor_videos
from arbol_navegacion import ArbolNavegacion
from tareas_videos import conectar_bd
from visor_videos import VisorVideos


def _crear_raiz():
    raiz = tempfile.TemporaryDirectory()
    os.makedirs(os.path.join(raiz.name, "sub1"))
    os.makedirs(os.path.join(raiz.name, "sub2"))
    with open(os.path.join(raiz.name, "top.mp4"), "w") as f:
        f.write("x")
    with open(os.path.join(raiz.name, "sub1", "v1.mp4"), "w") as f:
        f.write("x")
    with open(os.path.join(raiz.name, "sub2", "v2.mkv"), "w") as f:
        f.write("x")
    return raiz


def _crear_bd():
    temp_db = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_db.name, "catalogo.db")
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    return temp_db, ruta_db


def main():
    app = QApplication(sys.argv)
    resultados = []

    def registrar(nombre, ok):
        resultados.append((nombre, bool(ok)))
        print(f"{nombre}={'OK' if ok else 'FAIL'}")

    def esperar(predicado, intentos=600):
        for _ in range(intentos):
            QApplication.processEvents()
            if predicado():
                return True
            time.sleep(0.02)
        QApplication.processEvents()
        return predicado()

    raiz = _crear_raiz()
    flat_esperado = ["top.mp4"]
    recursivo_esperado = sorted(
        ["top.mp4", os.path.join("sub1", "v1.mp4"), os.path.join("sub2", "v2.mkv")]
    )

    def escenario(origen, activado, espia):
        temp_db, ruta_db = _crear_bd()
        temp_config = tempfile.TemporaryDirectory()
        ruta_config = os.path.join(temp_config.name, "configuracion.json")
        try:
            ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
            ventana.resize(900, 600)
            ventana.show()
            esperar(
                lambda v=ventana: v._carga_completada and v.gestor.hilo is None
            )
            ventana.incluir_subcarpetas.setChecked(activado)
            if origen == "arbol":
                arbol = ventana.findChild(ArbolNavegacion)
                disco = arbol.topLevelItem(0).child(0)
                arbol.setCurrentItem(disco)
            elif origen == "boton":
                ventana.carpeta_seleccionada = raiz.name
                ventana._actualizar_botones_carpeta()
                ventana.boton_escanear.click()
            elif origen == "dialogo":
                original = QFileDialog.getExistingDirectory
                QFileDialog.getExistingDirectory = lambda *a, **k: raiz.name
                try:
                    ventana.seleccionar_carpeta()
                finally:
                    QFileDialog.getExistingDirectory = original
            esperar(
                lambda v=ventana: v.videos_detectados is not None
                and not v._escaneo_pendiente
            )
            resultado = (
                list(ventana.videos_detectados)
                if ventana.videos_detectados is not None
                else None
            )
            valor_espia = (
                espia.call_args_list[-1][0][0] if espia.call_args_list else None
            )
            ventana.close()
            ventana.gestor.cerrar()
            return resultado, valor_espia
        finally:
            temp_db.cleanup()
            temp_config.cleanup()

    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[raiz.name]
    ), mock.patch.object(
        visor_videos,
        "configurar_escaneo_recursivo",
        wraps=visor_videos.configurar_escaneo_recursivo,
    ) as espia:
        arbol_off, espia_arbol_off = escenario("arbol", False, espia)
        arbol_on, espia_arbol_on = escenario("arbol", True, espia)
        boton_off, espia_boton_off = escenario("boton", False, espia)
        boton_on, espia_boton_on = escenario("boton", True, espia)
        dialogo_off, espia_dialogo_off = escenario("dialogo", False, espia)
        dialogo_on, espia_dialogo_on = escenario("dialogo", True, espia)

    registrar("arbol_off_resultado", arbol_off == flat_esperado)
    registrar("arbol_off_configuracion", espia_arbol_off is False)
    registrar("arbol_on_resultado", arbol_on == recursivo_esperado)
    registrar("arbol_on_configuracion", espia_arbol_on is True)
    registrar("boton_off_resultado", boton_off == flat_esperado)
    registrar("boton_off_configuracion", espia_boton_off is False)
    registrar("boton_on_resultado", boton_on == recursivo_esperado)
    registrar("boton_on_configuracion", espia_boton_on is True)
    registrar("dialogo_off_resultado", dialogo_off == flat_esperado)
    registrar("dialogo_off_configuracion", espia_dialogo_off is False)
    registrar("dialogo_on_resultado", dialogo_on == recursivo_esperado)
    registrar("dialogo_on_configuracion", espia_dialogo_on is True)

    registrar(
        "igualdad_off",
        arbol_off == boton_off == dialogo_off == flat_esperado,
    )
    registrar(
        "igualdad_on",
        arbol_on == boton_on == dialogo_on == recursivo_esperado,
    )
    registrar("diferencia_off_on", arbol_off != arbol_on)

    raiz.cleanup()

    total_ok = sum(1 for _, ok in resultados if ok)
    print(f"TOTAL={total_ok}/{len(resultados)}")
    print(f"RESULTADO_FINAL={'OK' if total_ok == len(resultados) else 'FAIL'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
