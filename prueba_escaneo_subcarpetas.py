import os
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication

import escanear_videos
from escanear_videos import (
    _nombre_seguro,
    configurar_escaneo_recursivo,
    escanear_videos,
    ruta_miniatura,
    ruta_preview,
)
from visor_videos import VisorVideos

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


def verifica(condicion, descripcion):
    if condicion:
        ok(descripcion)
    else:
        falla(descripcion)


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1

    # --- configurar_escaneo_recursivo existe ---
    verifica(
        callable(configurar_escaneo_recursivo),
        "configurar_escaneo_recursivo es invocable",
    )

    # --- escaneo sin subcarpetas (flat) funciona ---
    temp_flat = tempfile.TemporaryDirectory()
    try:
        for nombre in ["a.mp4", "b.mkv", "c.avi", "d.txt"]:
            with open(os.path.join(temp_flat.name, nombre), "w") as f:
                f.write("x")
        configurar_escaneo_recursivo(False)
        resultado = escanear_videos(temp_flat.name)
        verifica(
            resultado == ["a.mp4", "b.mkv", "c.avi"],
            "escaneo flat: solo archivos de video en carpeta raiz",
        )
    finally:
        temp_flat.cleanup()

    # --- escaneo con subcarpetas (recursivo) encuentra archivos anidados ---
    temp_rec = tempfile.TemporaryDirectory()
    try:
        os.makedirs(os.path.join(temp_rec.name, "sub1"))
        os.makedirs(os.path.join(temp_rec.name, "sub2", "nested"))
        for nombre, sub in [
            ("raiz.mp4", ""),
            ("sub1.mp4", "sub1"),
            ("nested.mp4", os.path.join("sub2", "nested")),
        ]:
            with open(os.path.join(temp_rec.name, sub, nombre), "w") as f:
                f.write("x")
        with open(os.path.join(temp_rec.name, "no_video.txt"), "w") as f:
            f.write("x")

        configurar_escaneo_recursivo(True)
        resultado = escanear_videos(temp_rec.name)
        esperados = sorted(
            [
                os.path.join("sub2", "nested", "nested.mp4"),
                os.path.join("sub1", "sub1.mp4"),
                "raiz.mp4",
            ]
        )
        verifica(
            resultado == esperados,
            "escaneo recursivo: archivos en subcarpetas con rutas relativas",
        )

        # --- restaurar estado no recursivo ---
        configurar_escaneo_recursivo(False)
        resultado_flat = escanear_videos(temp_rec.name)
        verifica(
            resultado_flat == ["raiz.mp4"],
            "configurar_escaneo_recursivo(False) restaura escaneo flat",
        )
    finally:
        temp_rec.cleanup()

    # --- _nombre_seguro reemplaza separadores ---
    verifica(
        _nombre_seguro("carpeta/video.mp4") == "carpeta_video.mp4",
        "_nombre_seguro: slash reemplazado",
    )
    verifica(
        _nombre_seguro("carpeta\\video.mp4") == "carpeta_video.mp4",
        "_nombre_seguro: backslash reemplazado",
    )
    verifica(
        _nombre_seguro("video.mp4") == "video.mp4",
        "_nombre_seguro: nombre plano intacto",
    )

    # --- ruta_miniatura usa nombre seguro ---
    ruta = ruta_miniatura("sub/video.mp4", indice=1)
    verifica(
        "sub_video_01" in ruta,
        "ruta_miniatura: usa nombre seguro en prefijo",
    )

    # --- ruta_preview usa nombre seguro ---
    ruta_p = ruta_preview("sub/video.mp4", indice=2)
    verifica(
        "sub_video_preview_02" in ruta_p,
        "ruta_preview: usa nombre seguro en prefijo",
    )

    # --- checkbox existe en la UI ---
    temp_db = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_db.name, "catalogo.db")
    from tareas_videos import conectar_bd
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()

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

    verifica(
        hasattr(ventana, "incluir_subcarpetas"),
        "VisorVideos tiene atributo incluir_subcarpetas",
    )
    verifica(
        ventana.incluir_subcarpetas.isVisible(),
        "checkbox incluir_subcarpetas es visible",
    )
    verifica(
        not ventana.incluir_subcarpetas.isChecked(),
        "checkbox comienza desmarcado",
    )

    ventana.close()
    ventana.gestor.cerrar()
    ventana.gestor_previews.cerrar()
    temp_db.cleanup()
    _CONFIG.cleanup()

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
