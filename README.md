## 🖥️ Interfaz Gráfica y Digital Twin (Streamlit + Plotly)

Para demostrar la eficacia de nuestros algoritmos, hemos construido un **Dashboard Analítico e Interactivo** desarrollado en Python (`Streamlit` + `Pandas` + `Plotly`). Este entorno no solo consume el JSON exportado, sino que actúa como un Gemelo Digital del silo de Inditex.

<img width="1918" height="867" alt="image" src="https://github.com/user-attachments/assets/5d89fa2f-c035-445c-b85f-d0b2221ce736" />


### Funcionalidades del Front-End:
- **🎬 Animación 3D de Eventos (Plotly):** Reconstrucción visual del almacén. Permite visualizar en un espacio tridimensional (X, Y, Z) la coreografía de uno de los 32 shuttles moviendo cajas en tiempo real, interpolando las trayectorias para entender el flujo físico.
- **⚙️ Panel de Debugging:** Visor de parámetros, métricas crudas y configuración del JSON inyectado.

<img width="1914" height="866" alt="20260425-2051-44 3556047" src="https://github.com/user-attachments/assets/4cb992d2-3c83-4807-a430-41260c8a5917" />

### Arquitectura del motor (C++ Core)

## 🔬 Suite de Benchmarking y Hyperopt (Auto-Tuning)

No nos conformamos con adivinar los pesos de nuestro algoritmo de coste `findBestSlot`. Hemos desarrollado una suite de herramientas avanzadas para optimizar matemáticamente la simulación:

- **Generador de Históricos Sintéticos**: Crea datasets de demanda basados en distribuciones asimétricas (Ley de Pareto) para simular escenarios de *Peak Season* (ej. Black Friday o Rebajas).

---

## 🛠️ Instalación y Uso

### 1. Compilación del Motor (Core C++)
Sin dependencias externas. Compilación estándar usando GCC/G++:
```bash
g++ main.cpp dualCycleShuttle.cpp paletManager.cpp silo.cpp -o simulador
