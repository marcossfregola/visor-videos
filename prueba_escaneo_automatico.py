import json
import os
import sys
import tempfile
import time
from unittest import mock

from PySide6.QtWidgets import QApplication, QFileDialog

import arbol_navegacion
import visor_videos
from arbol_navegacion import ArbolNavegacion
from configuracion import (
    guardar_preferencia_escaneo_automatico,
    obtener_preferencia_escaneo_automatico,
)
from tareas_videos import conectar_bd
from visor_videos import VisorVideos


def _crear_raiz():
    raiz = tempfile.TemporaryDirectory()
    os.makedirs(os.path.join(raiz.name, "sub1"))
    os.makedirs(os.path.join(raiz.name, "sub2"))
    for nombre in ["top.mp4"]:
        with open(os.path.join(raiz.name, nombre), "w") as f:
            f.write("x")
    for nombre in ["v1.mp4"]:
        with open(os.path.join(raiz.name, "sub1", nombre), "w") as f:
            f.write("x")
    for nombre in ["v2.mkv"]:
        with open(os.path.join(raiz.name, "sub2", nombre), "w") as f:
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

    # --- Parte A: persistencia de la preferencia ---
    temp_a = tempfile.TemporaryDirectory()
    ruta_config_a = os.path.join(temp_a.name, "configuracion.json")
    registrar(
        "default_true",
        obtener_preferencia_escaneo_automatico(ruta_config_a) is True,
    )
    guardar_preferencia_escaneo_automatico(True, ruta_config_a)
    registrar(
        "guardar_true",
        obtener_preferencia_escaneo_automatico(ruta_config_a) is True,
    )
    guardar_preferencia_escaneo_automatico(False, ruta_config_a)
    registrar(
        "guardar_false",
        obtener_preferencia_escaneo_automatico(ruta_config_a) is False,
    )
    with open(ruta_config_a, "w", encoding="utf-8") as f:
        json.dump({"ultima_carpeta": "C:\\x"}, f)
    registrar(
        "clave_ausente_true",
        obtener_preferencia_escaneo_automatico(ruta_config_a) is True,
    )
    with open(ruta_config_a, "w", encoding="utf-8") as f:
        json.dump({"escaneo_automatico": "si"}, f)
    registrar(
        "valor_no_bool_true",
        obtener_preferencia_escaneo_automatico(ruta_config_a) is True,
    )

    # --- Parte B: restauracion de la casilla y persistencia al cambiar ---
    temp_b = tempfile.TemporaryDirectory()
    ruta_config_b = os.path.join(temp_b.name, "configuracion.json")
    temp_db_b, ruta_db_b = _crear_bd()
    guardar_preferencia_escaneo_automatico(False, ruta_config_b)
    v_b = VisorVideos(ruta_db=ruta_db_b, ruta_config=ruta_config_b)
    v_b.resize(900, 600)
    v_b.show()
    esperar(lambda v=v_b: v._carga_completada and v.gestor.hilo is None)
    registrar("casilla_restaurada_false", not v_b.escaneo_automatico.isChecked())
    v_b.escaneo_automatico.setChecked(True)
    registrar(
        "cambio_persiste",
        obtener_preferencia_escaneo_automatico(ruta_config_b) is True,
    )
    v_b.close()
    v_b.gestor.cerrar()

    v_b2 = VisorVideos(ruta_db=ruta_db_b, ruta_config=ruta_config_b)
    v_b2.resize(900, 600)
    v_b2.show()
    esperar(lambda v=v_b2: v._carga_completada and v.gestor.hilo is None)
    registrar("casilla_restaurada_true", v_b2.escaneo_automatico.isChecked())
    v_b2.close()
    v_b2.gestor.cerrar()

    # --- Parte C: gating del auto-escaneo (espi'a) ---
    raiz_c = _crear_raiz()
    temp_c = tempfile.TemporaryDirectory()
    ruta_config_c = os.path.join(temp_c.name, "configuracion.json")
    temp_db_c, ruta_db_c = _crear_bd()

    def construir(escaneo_auto):
        v = VisorVideos(ruta_db=ruta_db_c, ruta_config=ruta_config_c)
        v.resize(900, 600)
        v.show()
        esperar(lambda w=v: w._carga_completada and w.gestor.hilo is None)
        v.escaneo_automatico.setChecked(escaneo_auto)
        return v

    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[raiz_c.name]
    ), mock.patch.object(
        visor_videos.VisorVideos, "iniciar_escaneo"
    ) as espia:
        v1 = construir(True)
        arbol1 = v1.findChild(ArbolNavegacion)
        disco1 = arbol1.topLevelItem(0).child(0)
        arbol1.setCurrentItem(disco1)
        QApplication.processEvents()
        registrar("arbol_auto_on_dispara", espia.call_count == 1)
        v1.close()
        v1.gestor.cerrar()

        v2 = construir(False)
        arbol2 = v2.findChild(ArbolNavegacion)
        disco2 = arbol2.topLevelItem(0).child(0)
        arbol2.setCurrentItem(disco2)
        QApplication.processEvents()
        registrar("arbol_auto_off_no_dispara", espia.call_count == 1)
        registrar(
            "arbol_auto_off_si_establece",
            v2.carpeta_seleccionada == raiz_c.name,
        )
        v2.close()
        v2.gestor.cerrar()

        v3 = construir(False)
        original = QFileDialog.getExistingDirectory
        QFileDialog.getExistingDirectory = lambda *a, **k: raiz_c.name
        v3.seleccionar_carpeta()
        QFileDialog.getExistingDirectory = original
        QApplication.processEvents()
        registrar("dialogo_auto_off_no_dispara", espia.call_count == 1)
        v3.close()
        v3.gestor.cerrar()

        v4 = construir(False)
        v4.carpeta_seleccionada = raiz_c.name
        v4._actualizar_botones_carpeta()
        v4.boton_escanear.click()
        QApplication.processEvents()
        registrar("boton_auto_off_si_dispara", espia.call_count == 2)
        v4.close()
        v4.gestor.cerrar()

        v5 = construir(True)
        v5.carpeta_seleccionada = raiz_c.name
        v5._actualizar_botones_carpeta()
        v5.boton_escanear.click()
        QApplication.processEvents()
        registrar("boton_auto_on_si_dispara", espia.call_count == 3)
        v5.close()
        v5.gestor.cerrar()

    # --- Parte D: cuatro combinaciones (resultados reales) ---
    flat_esperado = ["top.mp4"]
    recursivo_esperado = sorted(
        ["top.mp4", os.path.join("sub1", "v1.mp4"), os.path.join("sub2", "v2.mkv")]
    )
    raiz_d = _crear_raiz()

    def escenario_d(escaneo_auto, subcarpetas, origen):
        temp_db, ruta_db = _crear_bd()
        temp_config = tempfile.TemporaryDirectory()
        ruta_config = os.path.join(temp_config.name, "configuracion.json")
        try:
            v = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
            v.resize(900, 600)
            v.show()
            esperar(lambda w=v: w._carga_completada and w.gestor.hilo is None)
            v.escaneo_automatico.setChecked(escaneo_auto)
            v.incluir_subcarpetas.setChecked(subcarpetas)
            if origen == "seleccion":
                arbol = v.findChild(ArbolNavegacion)
                disco = arbol.topLevelItem(0).child(0)
                arbol.setCurrentItem(disco)
            elif origen == "boton":
                v.carpeta_seleccionada = raiz_d.name
                v._actualizar_botones_carpeta()
                v.boton_escanear.click()
            esperar(
                lambda w=v: w.videos_detectados is not None
                and not w._escaneo_pendiente
            )
            resultado = (
                list(v.videos_detectados) if v.videos_detectados is not None else None
            )
            v.close()
            v.gestor.cerrar()
            return resultado
        finally:
            temp_db.cleanup()
            temp_config.cleanup()

    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[raiz_d.name]
    ):
        r_auto_on_sub_on = escenario_d(True, True, "seleccion")
        r_auto_on_sub_off = escenario_d(True, False, "seleccion")
        r_auto_off_sub_on = escenario_d(False, True, "seleccion")
        r_auto_off_sub_off = escenario_d(False, False, "seleccion")
        r_boton_sub_on = escenario_d(False, True, "boton")
        r_boton_sub_off = escenario_d(False, False, "boton")

    registrar("combo_auto_on_sub_on", r_auto_on_sub_on == recursivo_esperado)
    registrar("combo_auto_on_sub_off", r_auto_on_sub_off == flat_esperado)
    registrar("combo_auto_off_sin_escaneo", r_auto_off_sub_on is None and r_auto_off_sub_off is None)
    registrar("combo_auto_off_boton_sub_on", r_boton_sub_on == recursivo_esperado)
    registrar("combo_auto_off_boton_sub_off", r_boton_sub_off == flat_esperado)

    temp_a.cleanup()
    temp_b.cleanup()
    temp_db_b.cleanup()
    temp_c.cleanup()
    temp_db_c.cleanup()
    raiz_c.cleanup()
    raiz_d.cleanup()

    total_ok = sum(1 for _, ok in resultados if ok)
    print(f"TOTAL={total_ok}/{len(resultados)}")
    print(f"RESULTADO_FINAL={'OK' if total_ok == len(resultados) else 'FAIL'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
