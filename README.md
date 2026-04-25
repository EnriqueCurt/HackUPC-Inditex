## 🖥️ Interfaz Gráfica y Digital Twin (Streamlit + Plotly)

Para demostrar la eficacia de nuestros algoritmos, hemos construido un **Dashboard Analítico e Interactivo** desarrollado en Python (`Streamlit` + `Pandas` + `Plotly`). Este entorno no solo consume el JSON exportado, sino que actúa como un Gemelo Digital del silo de Inditex.

<img width="1918" height="867" alt="image" src="https://github.com/user-attachments/assets/5d89fa2f-c035-445c-b85f-d0b2221ce736" />


### Funcionalidades del Front-End:
- **🎬 Animación 3D de Eventos (Plotly):** Reconstrucción visual del almacén. Permite visualizar en un espacio tridimensional (X, Y, Z) la coreografía de uno de los 32 shuttles moviendo cajas en tiempo real, interpolando las trayectorias para entender el flujo físico.
- **⚙️ Panel de Debugging:** Visor de parámetros, métricas crudas y configuración del JSON inyectado.

<img width="1914" height="866" alt="20260425-2051-44 3556047" src="https://github.com/user-attachments/assets/4cb992d2-3c83-4807-a430-41260c8a5917" />

### Arquitectura del motor (C++ Core)
## Gestion del almacen (silo.hpp / silo.cpp)

Define las estructuras de datos base como Position (Aisle, Side, X, Y, Z) y Box (ID, Destino, Reservas)

## Control de Lanzaderas (dualCycleShuttle.cpp)

Implementa el comportamiento lógico y físico de la clase Shuttle optimizando los movimientos para realizar las operaciones de entrada y salida de cajas en el mismo viaje con el objetivo de maximizar el rendimiento.

## Orquestación de Salida y Métricas (paletManager.hpp / paletManager.cpp)

Define las clases ActivePallet y PalletManager que actúan como el cerebro logístico que identifica cuándo hay suficiente stock (12 cajas) para iniciar la formación de un palé.

También genera el informe final de rendimiento por consola y se encarga de la exportación a output.json.

## Punto de entrada y simulación (main.cpp)

Orquestrador principal del sistema.

Funcionalidades:

- CLI Parser: Procesa los argumentos de la terminal (Cajas, Seed, Arrival Rate, Skew, etc.) permitiendo el control total desde Streamlit.

- Loop de Tiempo Real: Gestiona el reloj global de la simulación y la llegada de cajas según la Distribución Discreta de Zipf.

- Inicialización: Carga los escenarios iniciales desde archivos CSV y configura el estado de los 32 shuttles antes de iniciar la ejecución.

## 🔬 Suite de Benchmarking y Hyperopt (Auto-Tuning)

No nos conformamos con adivinar los pesos de nuestro algoritmo de coste `findBestSlot`. Hemos desarrollado una suite de herramientas avanzadas para optimizar matemáticamente la simulación:

- **Generador de Históricos Sintéticos**: Crea datasets de demanda basados en distribuciones asimétricas (Ley de Pareto) para simular escenarios de *Peak Season* (ej. Black Friday o Rebajas).

---

## 🛠️ Instalación y Uso

### 1. Compilación del Motor (Core C++)
Sin dependencias externas. Compilación estándar usando GCC/G++:
```bash
g++ main.cpp dualCycleShuttle.cpp paletManager.cpp silo.cpp -o simulador
