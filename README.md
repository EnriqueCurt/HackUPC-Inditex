# HackUPC-Inditex
# 📦 SmartSilo Optimizer: Algoritmos de Agilidad Logística

## 🚀 El Reto
Desarrollo de un motor de inteligencia logística para la gestión automatizada de silos de alta densidad. El objetivo es optimizar la coreografía de **lanzaderas (shuttles)** para minimizar los tiempos de respuesta en la entrada y salida de mercancía, maximizando el *throughput* de paletizado.

## 🧠 Solución Implementada
Este repositorio contiene una solución basada en **Python 3.12** que aborda:
- **Heurística de Almacenamiento:** Algoritmo de posicionamiento inteligente priorizando profundidad (Z=2) y clustering por destino.
- **Optimización de Salida:** Gestión de colas de prioridad mediante `heapq` para minimizar el movimiento de las lanzaderas (X) y evitar bloqueos en Z=1.
- **Simulador de Tiempos:** Cálculo preciso basado en la fórmula `t = 10 + d`, gestionando la concurrencia de 8 niveles de altura por pasillo.
- **Interfaz Visual:** Dashboard interactivo en **Streamlit** para monitorizar el estado del silo y métricas de eficiencia en tiempo real.

## 🛠️ Tecnologías
- **Lenguaje:** Python 3.12
- **Lógicas:** Greedy Algorithms, Heurísticas de búsqueda.
- **Visualización:** Plotly / Streamlit.
