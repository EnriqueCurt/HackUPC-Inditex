# HackUPC-Inditex
# 📦 SmartSilo Optimizer: Algoritmos de Agilidad Logística

## 🚀 El Reto
Desarrollo de un motor de inteligencia logística para la gestión automatizada de silos de alta densidad. El objetivo es optimizar la coreografía de **lanzaderas (shuttles)** para minimizar los tiempos de respuesta en la entrada y salida de mercancía, maximizando el *throughput* de paletizado.

# Solucion propuesta:
# 📦 [Enrique Curt Moscoso y Daniel Parejo Jaramago] - Inditex Logistics Challenge

[![C++](https://img.shields.io/badge/C++-17-blue.svg?style=flat&logo=c%2B%2B)](https://isocpp.org/)
[![HackUPC 2026](https://img.shields.io/badge/HackUPC-2026-ff69b4.svg?style=flat)](https://hackupc.com/)
[![Status](https://img.shields.io/badge/Status-Completed-success.svg)]()

> Solución de alto rendimiento para el reto **"Hack The Flow"** de Inditex en la HackUPC 2026. 

Este proyecto implementa un motor de simulación de Eventos Discretos en C++ para orquestar la entrada y salida de cajas en un silo automatizado AS/RS (Automated Storage and Retrieval System). Nuestro objetivo: minimizar el tiempo de ciclo, evitar cuellos de botella y maximizar el *Throughput* mediante la ejecución en paralelo y la zonificación predictiva.

---

## 🚀 Características Principales (The "Killer Features")

Nuestra arquitectura no se limita a mover cajas de un punto A a un punto B; toma decisiones logísticas inteligentes en tiempo real:

- **🔥 Paralelismo Físico Real (32 Shuttles):** Hemos modelado la física exacta del almacén. El silo no es un embudo de 8 niveles; consta de **4 pasillos independientes con 8 niveles cada uno**. Nuestro motor asigna tareas de forma asíncrona, permitiendo que hasta 32 shuttles extraigan cajas simultáneamente sin bloquearse entre sí.
- **⏱️ Motor basado en Ticks (Global Clock):** En lugar de ejecución secuencial, el sistema utiliza un reloj global que simula el tiempo real. Los shuttles calculan sus tiempos de viaje (`t = d + 10s`) y "despiertan" solo cuando han completado su tarea actual.
- **🧠 Consolidación Dinámica de Palets:** Un `PalletManager` actúa como supervisor. Vigila el stock en tiempo real y, en el momento exacto en que hay 12 cajas de un mismo destino libres, bloquea el stock y lanza las órdenes de extracción priorizadas.
- **🎯 Velocity-Based Storage (Zonificación ABC):** *Nuestra mayor ventaja competitiva.* El sistema ingiere un histórico de pedidos (`historico_pedidos.csv`) y aplica una heurística predictiva. Los productos "Top Ventas" (Clase A) son penalizados por el algoritmo si intentan guardarse en la profundidad del pasillo, forzando a que los destinos de alta rotación se queden a escasos segundos de la cabecera de salida.
- **🔌 Interfaz Desacoplada (Exportación JSON):** El core en C++ genera métricas y un *log* exhaustivo de eventos (IN/OUT, coordenadas, tiempos) en un archivo `output.json`, permitiendo que cualquier Front-End lo consuma y renderice sin dependencias pesadas.

---

## 📊 Métricas de Éxito (Throughput)

Bajo condiciones de estrés extremo (cargas semi-llenas desde CSV y entrada online simultánea), nuestro algoritmo logra:

* **Full Pallets Percentage:** `100%` (Regla estricta de consolidación).
* **Throughput Máximo Sostenido:** Logramos montar palets completos de alta rotación en tiempos de ciclo inferiores a **60 segundos** (gracias a la recolección paralela de múltiples shuttles).

---

## 🛠️ Instalación y Uso

### Compilación (Core C++)
No requiere dependencias externas. Compilación estándar usando GCC/G++:

```bash
g++ main.cpp dualCycleShuttle.cpp paletManager.cpp silo.cpp -o simulador
