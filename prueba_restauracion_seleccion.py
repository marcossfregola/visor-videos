import os
import sys
import tempfile
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from visor_videos import ESTILO_SELECCIONADA, VisorVideos

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

    nombres = [nombre for nombre, _ in ventana.tarjetas]

    # --- seleccion simple se restaura tras reemplazar ---
    ventana._al_seleccionar_tarjeta(nombres[0], False)
    verifica(
        len(ventana._nombres_seleccionados) == 1,
        "seleccion simple previa: 1 elemento",
    )
    verifica(
        nombres[0] in ventana._nombres_seleccionados,
        "seleccion simple previa: nombre correcto",
    )

    misma_fila = [ventana.tarjetas[0][1]._nombre]
    filas_para_reemplazar = [
        ("v001.mp4", None, None, None, None, None, None),
        ("v002.mp4", None, None, None, None, None, None),
    ]
    ventana._reemplazar_tarjetas(filas_para_reemplazar)

    verifica(
        len(ventana._nombres_seleccionados) == 1,
        "seleccion simple restaurada: 1 elemento tras reemplazar",
    )
    verifica(
        "v001.mp4" in ventana._nombres_seleccionados,
        "seleccion simple restaurada: nombre correcto en conjunto",
    )
    verifica(
        ventana.tarjetas[0][1]._seleccionada,
        "seleccion simple restaurada: tarjeta marcada visualmente",
    )
    verifica(
        ESTILO_SELECCIONADA in ventana.tarjetas[0][1].styleSheet(),
        "seleccion simple restaurada: stylesheet aplicado",
    )

    # --- seleccion multiple se restaura tras reemplazar ---
    ventana._limpiar_seleccion()
    ventana._al_seleccionar_tarjeta("v001.mp4", False)
    ventana._al_seleccionar_tarjeta("v002.mp4", True)
    verifica(
        len(ventana._nombres_seleccionados) == 2,
        "seleccion multiple previa: 2 elementos",
    )

    ventana._reemplazar_tarjetas(filas_para_reemplazar)

    verifica(
        len(ventana._nombres_seleccionados) == 2,
        "seleccion multiple restaurada: 2 elementos tras reemplazar",
    )
    verifica(
        "v001.mp4" in ventana._nombres_seleccionados
        and "v002.mp4" in ventana._nombres_seleccionados,
        "seleccion multiple restaurada: ambos nombres en conjunto",
    )
    verifica(
        ventana.tarjetas[0][1]._seleccionada
        and ventana.tarjetas[1][1]._seleccionada,
        "seleccion multiple restaurada: ambas tarjetas marcadas visualmente",
    )

    # --- sin seleccion previa queda sin seleccion ---
    ventana._limpiar_seleccion()
    ventana._reemplazar_tarjetas(filas_para_reemplazar)
    verifica(
        len(ventana._nombres_seleccionados) == 0,
        "sin seleccion previa: conjunto vacio tras reemplazar",
    )
    verifica(
        not ventana.tarjetas[0][1]._seleccionada
        and not ventana.tarjetas[1][1]._seleccionada,
        "sin seleccion previa: ninguna tarjeta marcada",
    )

    # --- nombre seleccionado que ya no existe simplemente se ignora ---
    ventana._al_seleccionar_tarjeta("v002.mp4", False)
    verifica(
        len(ventana._nombres_seleccionados) == 1,
        "seleccion con nombre a desaparecer: 1 elemento previo",
    )

    reemplazo_parcial = [
        ("v001.mp4", None, None, None, None, None, None),
        ("v003.mp4", None, None, None, None, None, None),
    ]
    ventana._reemplazar_tarjetas(reemplazo_parcial)

    verifica(
        len(ventana._nombres_seleccionados) == 0,
        "nombre seleccionado ausente: conjunto vacio sin fallo",
    )
    verifica(
        not ventana.tarjetas[0][1]._seleccionada
        and not ventana.tarjetas[1][1]._seleccionada,
        "nombre seleccionado ausente: ninguna tarjeta marcada",
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
