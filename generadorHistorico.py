import random

# Destinos reales extraídos de tu CSV de prueba
destinos = [
    "01006170", "01000110", "01005160", "01001120", "01002130", 
    "01003140", "01004150", "01007180", "01008190", "01009210", 
    "01010220", "01011230", "01012240", "01014260", "01015270", 
    "01013250", "01016280", "01018310", "01019320", "01017290"
]

# Pesos (Los primeros destinos tienen muchísima más demanda que los últimos)
pesos = [150, 120, 90, 80, 50, 40, 30, 20, 15, 10, 5, 5, 5, 2, 2, 1, 1, 1, 1, 1]

print("Generando 10,000 pedidos históricos...")
with open("historico_pedidos.csv", "w") as f:
    f.write("destino\n")
    for _ in range(10000):
        # Selecciona un destino aleatorio pero respetando los pesos
        dest = random.choices(destinos, weights=pesos, k=1)[0]
        f.write(f"{dest}\n")

print("¡historico_pedidos.csv generado con éxito!")