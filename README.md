## 🖥️ Interfaz Gráfica y Digital Twin (Streamlit + Plotly)

Para demostrar la eficacia de nuestros algoritmos, hemos construido un **Dashboard Analítico e Interactivo** desarrollado en Python (`Streamlit` + `Pandas` + `Plotly`). Este entorno no solo consume el JSON exportado, sino que actúa como un Gemelo Digital del silo de Inditex.

![Dashboard Preview]([AÑADIR CAPTURA DEL DASHBOARD PRINCIPAL AQUÍ])

### Funcionalidades del Front-End:
- **🎬 Animación 3D de Eventos (Plotly):** Reconstrucción visual del almacén. Permite visualizar en un espacio tridimensional (X, Y, Z) la coreografía de los 32 shuttles moviendo cajas en tiempo real, interpolando las trayectorias para entender el flujo físico.
- **⚖️ A/B Testing y Comparativa en Vivo:** El dashboard permite cargar dos escenarios simultáneamente (ej. *Modo Estándar* vs *Modo ABC Predictivo*) y calcular el delta de mejora exacta en *Throughput* y Tiempos de Simulación.
- **📊 Distribución de Tiempos de Paletizado:** Gráficos interactivos que muestran los picos de trabajo y el histórico de cierre de palets a lo largo de la simulación.
- **⚙️ Panel de Debugging:** Visor de parámetros, métricas crudas y configuración del JSON inyectado.

![Animación 3D]([AÑADIR GIF DE LA ANIMACIÓN 3D AQUÍ])

---

## 🔬 Suite de Benchmarking y Hyperopt (Auto-Tuning)

No nos conformamos con adivinar los pesos de nuestro algoritmo de coste `findBestSlot`. Hemos desarrollado una suite de herramientas avanzadas para optimizar matemáticamente la simulación:

- **`benchmark_runner.py`**: Ejecuta simulaciones masivas (Batch testing) variando la semilla aleatoria (seeds), las tasas de llegada y los porcentajes de llenado del almacén para garantizar que el algoritmo no sufre de *overfitting*.
- **`hyperopt_runner.py`**: Motor de optimización de hiperparámetros. Utiliza algoritmos de búsqueda para encontrar el balance perfecto entre las penalizaciones de distancia (`w_x`), profundidad (`w_depth`) y la heurística predictiva ABC (`w_pop`). 
- **Generador de Históricos Sintéticos**: Crea datasets de demanda basados en distribuciones asimétricas (Ley de Pareto) para simular escenarios de *Peak Season* (ej. Black Friday o Rebajas).

---

## 🛠️ Instalación y Uso

### 1. Compilación del Motor (Core C++)
Sin dependencias externas. Compilación estándar usando GCC/G++:
```bash
g++ main.cpp dualCycleShuttle.cpp paletManager.cpp silo.cpp -o simulador