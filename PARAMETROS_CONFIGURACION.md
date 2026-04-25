# Parámetros de Configuración

Guía de todos los parámetros de configuración del simulador y la interfaz.

Referencias:

- Interfaz: [app_streamlit.py](app_streamlit.py)
- Motor/CLI: [silo_hackathon.py](silo_hackathon.py)
- Pesos optimizados: [best_weights_quick.json](best_weights_quick.json)

## 1. Parámetros en la Interfaz (barra lateral de Streamlit)

### 1. Escenario inicial CSV

Archivo de estado inicial del silo (ocupación ya existente).

Impacto:

- Cambia por completo la dificultad del problema (semi vacío, 40%, 70%, 90%, etc.).

### 2. Modo principal

Valores:

- `online`
- `batch`

Significado:

- `online`: las cajas llegan en el tiempo.
- `batch`: primero entra todo y luego se procesa salida.

### 3. Comparar también contra el otro modo

Si se activa, ejecuta también el modo contrario para mostrar comparativa de KPIs.

### 4. Perfil heurístico

Valores:

- `balanced`
- `throughput`
- `pick_speed`

Significado:

#### `balanced`

Perfil equilibrado entre velocidad de entrada, coste de salida y estabilidad.

Cómo se comporta:

- Reparte mejor la carga entre lanzaderas.
- Evita extremos (ni súper agresivo en throughput, ni súper conservador en picking).
- Suele dar resultados robustos cuando no sabes aún la distribución real.

Cuándo usarlo:

- Como baseline.
- Para comparar contra los otros perfiles.
- En escenarios mixtos donde quieres consistencia.

#### `throughput`

Perfil orientado a maximizar palets/hora y flujo global.

Cómo se comporta:

- Favorece decisiones que mantienen alto ritmo de procesamiento.
- Prioriza cierres de palets activos con más agresividad.
- Tiende a funcionar mejor cuando el objetivo principal es capacidad de salida.

Cuándo usarlo:

- Si tu KPI principal es throughput.
- En demos donde quieres enseñar productividad máxima.
- En cargas altas y continuas (tipo 1000 cajas/hora).

#### `pick_speed`

Perfil orientado a rapidez de extracción inmediata (picks más cortos/rápidos).

Cómo se comporta:

- Penaliza más posiciones caras en X y profundidad.
- Da más peso a accesibilidad de caja.
- Puede mejorar tiempos de pick, aunque no siempre maximiza throughput total.

Cuándo usarlo:

- Si te importa bajar tiempo de ciclo por extracción.
- Si hay mucha sensibilidad a bloqueos y reubicaciones locales.
- Para escenarios donde prima respuesta rápida más que volumen total.

Regla práctica:

- Empieza con `throughput` si tu objetivo es rendimiento global.
- Usa `balanced` como referencia estable.
- Prueba `pick_speed` cuando detectes cuellos en la fase de extracción.

### 5. Origen de pesos

Valores:

- `preset`
- `manual`
- `best_weights.json`

Significado:

- `preset`: usa el perfil elegido tal cual.
- `manual`: permite ajustar cada peso con sliders.
- `best_weights.json`: carga pesos optimizados desde archivo JSON.

### 6. Parámetros de pesos manuales

(Aparecen si `Origen de pesos = manual`)

- `w_shuttle`: prioriza lanzaderas menos ocupadas.
- `w_x`: penaliza posiciones más profundas en X (más lejos).
- `w_depth`: penaliza usar z=2 (riesgo de bloqueo).
- `w_lane_fill`: evita concentrar en lanes muy llenas.
- `w_pop`: empuja destinos populares a posiciones más accesibles.
- `w_close_pallet`: favorece picks que cierran antes un pallet activo.

### 7. Cajas entrantes

Cantidad de cajas nuevas a simular.

### 8. Destinos sintéticos

Número de destinos distintos para las cajas generadas.

### 9. Seed

Semilla aleatoria para reproducibilidad.

Regla:

- Misma seed + mismos parámetros = mismo experimento.

### 10. Arrival rate (cajas/h)

Ritmo de llegada en modo online.

Ejemplo:

- `1000` cajas/hora equivale a una caja cada `3.6s` de tiempo simulado.

### 11. Dispatch cada N entradas

Cada cuántas cajas entrantes se dispara un ciclo de salida en online.

Efecto:

- Más bajo: más reactivo.
- Más alto: más acumulación antes de despachar.

### 12. Tamaño histórico

Número de envíos sintéticos para estimar popularidad de destinos.

### 13. Destinos en histórico

Número de destinos usados en ese histórico sintético.

### 14. Skew histórico

Sesgo tipo Zipf.

Efecto:

- Más alto: pocos destinos muy dominantes.
- Más bajo: distribución más uniforme.

### 15. Targets llenado

Lista de porcentajes para generar escenarios nuevos desde un CSV base.

Ejemplo:

- `0.40,0.70,0.90`

### 16. Seed escenarios

Semilla para generar escenarios de forma reproducible.

## 2. Parámetros del archivo best_weights_quick.json

En [best_weights_quick.json](best_weights_quick.json) aparecen:

### 1. `meta.iterations`

Cuántas pruebas hizo el optimizador.

### 2. `meta.optimizer_seed`

Semilla del optimizador de pesos.

### 3. `meta.modes`

Modos usados durante la optimización (`online`, `batch` o ambos).

### 4. `meta.seeds`

Semillas de simulación usadas para robustez.

### 5. `meta.scenarios`

Escenarios CSV usados en la búsqueda de pesos.

### 6. `meta.objective`

Coeficientes de la función objetivo:

- `alpha_throughput`: premio al throughput.
- `alpha_completitud`: premio a completitud.
- `alpha_reubic`: castigo a reubicaciones.
- `alpha_full`: castigo a rechazos por silo lleno.

### 7. `meta.metrics`

Métricas medias del mejor candidato encontrado.

### 8. `weights`

Pesos finales óptimos:

- `w_shuttle`
- `w_x`
- `w_depth`
- `w_lane_fill`
- `w_pop`
- `w_close_pallet`

## 3. Parámetros CLI principales del motor

Definidos en [silo_hackathon.py](silo_hackathon.py).

### Núcleo de simulación

- `--cajas`, `--destinos`, `--seed`: tamaño/variedad de entrada y reproducibilidad.
- `--mode`: `online` o `batch`.
- `--strategy`: preset base (`balanced`, `throughput`, `pick_speed`).
- `--arrival-rate`, `--dispatch-every`: control temporal del flujo online.

### Estado inicial

- `--initial-csv`: carga estado inicial del silo.
- `--strict-csv`: validación estricta del CSV inicial.

### Popularidad de destinos (histórico sintético)

- `--history-size`
- `--history-destinos`
- `--history-skew`

### Pesos heurísticos

- `--weights-json`: inyecta pesos custom desde JSON.
  - Acepta JSON plano o formato con clave `weights`.

### Exportación

- `--export`
- `--export-path`

### Generación de escenarios

- `--make-scenarios`
- `--scenario-base`
- `--scenario-targets`
- `--scenario-seed`

## 4. Recomendaciones rápidas

### Perfil para demo de jurado

- `mode = online`
- `strategy = throughput`
- `Origen de pesos = best_weights.json`
- `arrival-rate = 1000`
- `dispatch-every = 12`
- `compare = on`

### Perfil para investigación/optimización

- Usar `hyperopt_runner.py` con más iteraciones y múltiples seeds.
- Validar con `benchmark_runner.py` en varios escenarios.
- Mantener seed fija en iteraciones de comparación para trazabilidad.
