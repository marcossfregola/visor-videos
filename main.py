from operaciones import sumar

resultado = sumar(7, 5)
with open("datos.txt", "w") as f:
    f.write(str(resultado))
