from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import plotly.express as px
import plotly.graph_objects as go

import pandas as pd
import numpy as np
import streamlit as st



from silo_hackathon import (
    HEURISTIC_KEYS,
    PALET_SIZE,
    STRATEGY_PRESETS,
    Silo,
    build_scenario_variants,
    gen_cajas,
    gen_historico_sintetico,
    normalizar_popularidad,
    parse_fill_targets,
)

BASE_DIR = Path(__file__).resolve().parent

# --- AÑADE ESTOS HELPERS ARRIBA DEL TODO (debajo de imports) ---

def interpolate_path(p0, p1, steps=8):
    return [
        (
            p0[0] + (p1[0]-p0[0]) * t/steps,
            p0[1] + (p1[1]-p0[1]) * t/steps,
            p0[2] + (p1[2]-p0[2]) * t/steps,
        )
        for t in range(steps+1)
    ]


def shuttle_path(start, end):
    # Movimiento realista: primero eje X, luego ajuste Y/Z
    mid = (end[0], start[1], start[2])
    return (
        interpolate_path(start, mid, 6) +
        interpolate_path(mid, end, 6)
    )


def _discover_scenarios() -> List[Path]:
    return sorted(BASE_DIR.glob("silo-semi-empty*.csv"))


def _inject_styles():
    st.markdown(
        """
        <style>
        .section-card {
            border: 1px solid #d6dde6;
            border-radius: 12px;
            padding: 12px 14px;
            margin-bottom: 10px;
            background: #f8fafc;
        }
        .section-title {
            font-weight: 700;
            font-size: 1.02rem;
            margin-bottom: 6px;
        }
        .section-note {
            color: #334155;
            font-size: 0.9rem;
            margin-bottom: 0px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _run_simulation(
    mode: str,
    n_cajas: int,
    n_destinos: int,
    seed: int,
    initial_csv: Path | None,
    arrival_rate_h: float,
    dispatch_every: int,
    strategy: str,
    history_size: int,
    history_destinos: int,
    history_skew: float,
    custom_weights: Optional[Dict[str, float]] = None,
) -> Tuple[Dict, Dict | None, List[dict], List[dict]]:
    destination_priority: Dict[str, float] = {}
    if history_size > 0:
        hist = gen_historico_sintetico(
            n_envios=history_size,
            n_dest=history_destinos,
            skew=history_skew,
            seed=seed,
        )
        destination_priority = normalizar_popularidad(hist)

    silo = Silo(
        strategy=strategy,
        destination_priority=destination_priority,
        custom_weights=custom_weights,
    )
    csv_summary = None

    if initial_csv is not None and initial_csv.exists():
        csv_summary = silo.load_initial_csv(str(initial_csv), strict=False)

    codigos = gen_cajas(n_cajas, n_destinos, seed)

    if mode == "online":
        result = silo.simulate_online(
            codigos,
            arrival_rate_h=arrival_rate_h,
            dispatch_every=dispatch_every,
            verbose=False,
        )
    else:
        result = silo.simulate(codigos, verbose=False)

    return result, csv_summary, silo.eventos, silo.completados


def _load_weights_from_file(path: Path) -> Tuple[Optional[Dict[str, float]], str]:
    if not path.exists():
        return None, f"No existe el archivo: {path}"

    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        return None, f"Error leyendo pesos: {exc}"

    if not isinstance(raw, dict):
        return None, "El archivo JSON debe ser un objeto"

    data = raw.get("weights", raw)
    if not isinstance(data, dict):
        return None, "El campo 'weights' debe ser un objeto"

    weights: Dict[str, float] = {}
    for k in HEURISTIC_KEYS:
        if k not in data:
            return None, f"Falta peso requerido: {k}"
        weights[k] = float(data[k])
        if weights[k] < 0:
            return None, f"Peso negativo no permitido: {k}"

    return weights, "ok"


def _render_metrics(title: str, result: Dict):
    st.subheader(title)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("t_sim (h)", result["t_simulacion_h"])
    c2.metric("throughput palets/h", result["throughput_palets_hora"])
    c3.metric("palets completos", result["palets_completados"])
    c4.metric("completitud %", result["tasa_completitud_%"])

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("cajas iniciales", result["cajas_iniciales"])
    c6.metric("cajas entrantes", result["cajas_entrantes"])
    c7.metric("reubicaciones", result["reubicaciones"])
    c8.metric("rechazadas por full", result["cajas_rechazadas_full"])

def _render_event_animation(events: List[dict], section_title: str, key_prefix: str):
    st.subheader(section_title)
    if not events:
        st.info("No hay eventos para animar.")
        return

    df = pd.DataFrame(events)
    
    # 1. PARSEO DE COORDENADAS (Basado en el estándar 11-dígitos del PDF)
    if 'pos' in df.columns:
        df['pos'] = df['pos'].astype(str).replace('nan', '01_01_000_01_01')
        pos_split = df['pos'].str.split('_', expand=True)
        df['x'] = pd.to_numeric(pos_split[2], errors='coerce').fillna(0).astype(int)
        df['y'] = pd.to_numeric(pos_split[3], errors='coerce').fillna(0).astype(int)
        df['z'] = pd.to_numeric(pos_split[4], errors='coerce').fillna(0).astype(int)

    df = df.sort_values('t') if 't' in df.columns else df
    
    # Reducción drástica para evitar el "pantallazo blanco" (Memoria del navegador)
    df_anim = df.head(100).copy()

    # 2. SEGUIMIENTO DE STOCK (Visualización de todas las cajas)
    frames = []
    current_stock = set() # Usamos un set para rapidez
    
    for i, row in df_anim.iterrows():
        # Antes de cada movimiento, gestionamos el stock
        if row['tipo'] == 'OUT':
            current_stock.discard((row['x'], row['y'], row['z']))
        
        # Coordenadas del Shuttle
        s_x, s_y, s_z = row['x'], row['y'], row['z']
        
        # Convertimos stock actual a listas para Plotly
        if current_stock:
            stock_x, stock_y, stock_z = zip(*current_stock)
        else:
            stock_x, stock_y, stock_z = [], [], []

        frames.append(go.Frame(
            data=[
                # Traza 0: Stock estático (Azul - cajas ya guardadas)
                go.Scatter3d(x=list(stock_x), y=list(stock_y), z=list(stock_z), 
                             mode='markers', marker=dict(size=5, color='#219ebc', opacity=0.5),
                             name='Stock Almacenado'),
                # Traza 1: Shuttle (Rojo - activo)
                go.Scatter3d(x=[s_x], y=[s_y], z=[s_z], 
                             mode='markers', marker=dict(size=10, color='#e63946', symbol='diamond'),
                             name='Shuttle'),
                # Traza 2: Caja en movimiento (Naranja)
                go.Scatter3d(x=[s_x], y=[s_y], z=[s_z], 
                             mode='markers', marker=dict(size=7, color='#ffb703', symbol='square'),
                             name='Caja Activa')
            ],
            name=f"f{i}"
        ))

        if row['tipo'] == 'IN':
            current_stock.add((row['x'], row['y'], row['z']))

    # 3. CREACIÓN DE LA FIGURA BASE
    fig = go.Figure()
    
    # Añadimos las trazas iniciales para definir la leyenda
    fig.add_trace(go.Scatter3d(x=[], y=[], z=[], mode='markers', name='Stock Almacenado'))
    fig.add_trace(go.Scatter3d(x=[], y=[], z=[], mode='markers', name='Shuttle'))
    fig.add_trace(go.Scatter3d(x=[], y=[], z=[], mode='markers', name='Caja Activa'))

    # 4. ESCENARIO (Racks grises fijos)
    # Dibujamos líneas para representar la estructura del silo del PDF (X=60, Y=8, Z=2)
    for z in [1, 2]:
        for y in range(1, 9):
            fig.add_trace(go.Scatter3d(
                x=[0, 60], y=[y, y], z=[z, z],
                mode='lines', line=dict(color='rgba(200,200,200,0.2)', width=1),
                showlegend=False
            ))

    fig.frames = frames

    # 5. LAYOUT "FULLSCREEN-READY"
    fig.update_layout(
        height=850, # Altura fija para evitar el bug de pantalla en blanco al redimensionar
        scene=dict(
            aspectmode='manual',
            aspectratio=dict(x=3, y=1, z=0.4), # Proporciones realistas del pasillo
            xaxis=dict(title="Longitud (X)", range=[-2, 62], gridcolor='white'),
            yaxis=dict(title="Nivel (Y)", range=[0, 9], gridcolor='white'),
            zaxis=dict(title="Profundidad (Z)", range=[0, 3], gridcolor='white'),
            bgcolor='#f8f9fa'
        ),
        updatemenus=[{
            "buttons": [
                {
                    "label": "▶ SIMULAR LOGÍSTICA",
                    "method": "animate",
                    "args": [None, {"frame": {"duration": 150, "redraw": True}, "fromcurrent": False}]
                },
                {"label": "⏸ PAUSA", "method": "animate", "args": [[None], {"mode": "immediate"}]}
            ],
            "type": "buttons", "direction": "left", "x": 0.1, "y": 0.05
        }],
        margin=dict(l=0, r=0, b=0, t=30)
    )

    st.plotly_chart(fig, use_container_width=True, config={'responsive': True})

def _render_config_summary(summary: Dict[str, str]):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Configuración activa</div>', unsafe_allow_html=True)
    row1 = st.columns(4)
    row1[0].metric("Modo", summary["mode"])
    row1[1].metric("Estrategia", summary["strategy"])
    row1[2].metric("Escenario", summary["scenario"])
    row1[3].metric("Comparativa", summary["compare"])

    row2 = st.columns(4)
    row2[0].metric("Cajas", summary["n_cajas"])
    row2[1].metric("Destinos", summary["n_destinos"])
    row2[2].metric("Arrival/h", summary["arrival_rate_h"])
    row2[3].metric("Dispatch", summary["dispatch_every"])
    st.markdown('</div>', unsafe_allow_html=True)


def main():
    st.set_page_config(page_title="Silo Hackathon Optimizer", layout="wide")
    _inject_styles()

    st.title("Silo Logístico: Simulación y Optimización")
    st.write(
        "Demo de motor con estado inicial configurable, "
        "comparativa batch/online y animación de eventos."
    )

    scenarios = _discover_scenarios()
    scenario_names = [p.name for p in scenarios]

    with st.sidebar:
        st.header("Configuración")
        st.caption("Parámetros agrupados por bloques para facilitar lectura y ajuste.")

        with st.expander("1) Escenario y ejecución", expanded=True):
            if scenario_names:
                scenario_name = st.selectbox(
                    "Escenario inicial CSV",
                    scenario_names,
                    index=0,
                    help="Estado inicial del silo antes de procesar cajas entrantes.",
                )
                initial_csv = BASE_DIR / scenario_name
            else:
                scenario_name = "(sin CSV detectado)"
                initial_csv = None
                st.warning("No se detectaron escenarios CSV en la carpeta del proyecto.")

            mode = st.selectbox(
                "Modo principal",
                ["online", "batch"],
                index=0,
                help="online: llegadas en el tiempo, batch: entrada y salida por fases.",
            )
            compare = st.checkbox("Comparar también contra el otro modo", value=True)

            profile = st.selectbox(
                "Perfil de carga",
                ["Personalizado", "Demo rápida", "Balanceado", "Stress"],
                index=0,
                help="Solo precarga valores sugeridos; puedes modificarlos después.",
            )
            defaults = {
                "Personalizado": (1200, 40, 1000.0, PALET_SIZE),
                "Demo rápida": (600, 30, 1000.0, PALET_SIZE),
                "Balanceado": (1200, 40, 1000.0, PALET_SIZE),
                "Stress": (4000, 90, 1500.0, max(8, PALET_SIZE // 2)),
            }
            d_cajas, d_dest, d_arrival, d_dispatch = defaults[profile]

            n_cajas = st.slider("Cajas entrantes", min_value=120, max_value=5000, value=d_cajas, step=60)
            n_destinos = st.slider("Destinos sintéticos", min_value=8, max_value=120, value=d_dest, step=1)
            seed = st.number_input("Seed", min_value=1, max_value=999999, value=42, step=1)

            arrival_rate_h = st.number_input(
                "Arrival rate (cajas/h)",
                min_value=100.0,
                max_value=20000.0,
                value=d_arrival,
                step=100.0,
            )
            dispatch_every = st.number_input(
                f"Dispatch cada N entradas (recomendado {PALET_SIZE})",
                min_value=1,
                max_value=200,
                value=d_dispatch,
                step=1,
            )

        with st.expander("2) Heurísticas y pesos", expanded=True):
            strategy = st.selectbox(
                "Perfil heurístico",
                ["balanced", "throughput", "pick_speed"],
                index=1,
                help="balanced: robusto, throughput: máximo flujo, pick_speed: extracción más rápida.",
            )

            custom_mode = st.selectbox(
                "Origen de pesos",
                ["preset", "manual", "best_weights.json"],
                index=0,
                help="preset: perfil fijo; manual: sliders; best_weights.json: carga optimizada.",
            )

            custom_weights: Optional[Dict[str, float]] = None
            if custom_mode == "manual":
                base = STRATEGY_PRESETS[strategy]
                st.caption("Ajuste manual de pesos")
                custom_weights = {}
                for key in HEURISTIC_KEYS:
                    hi = 10.0 if key == "w_close_pallet" else 3.0
                    custom_weights[key] = st.slider(
                        key,
                        min_value=0.0,
                        max_value=hi,
                        value=float(base[key]),
                        step=0.05,
                    )
            elif custom_mode == "best_weights.json":
                best_path_str = st.text_input(
                    "Ruta JSON pesos",
                    value=str(BASE_DIR / "best_weights.json"),
                )
                best_path = Path(best_path_str)
                custom_weights, msg = _load_weights_from_file(best_path)
                if custom_weights is None:
                    st.warning(msg)
                else:
                    st.caption("Pesos cargados")
                    st.json(custom_weights)

        with st.expander("3) Histórico sintético", expanded=False):
            st.caption("Controla el sesgo de popularidad de destinos para el scoring heurístico.")
            history_size = st.number_input(
                "Tamaño histórico",
                min_value=0,
                max_value=2_000_000,
                value=250_000,
                step=50_000,
            )
            history_destinos = st.number_input(
                "Destinos en histórico",
                min_value=20,
                max_value=400,
                value=120,
                step=10,
            )
            history_skew = st.number_input(
                "Skew histórico",
                min_value=0.1,
                max_value=3.0,
                value=1.15,
                step=0.05,
            )

        with st.expander("4) Generar más escenarios", expanded=False):
            target_raw = st.text_input("Targets llenado", value="0.40,0.70,0.90")
            scenario_seed = st.number_input("Seed escenarios", min_value=1, max_value=999999, value=42, step=1)
            gen_click = st.button("Generar escenarios")

        st.divider()
        run_click = st.button("Ejecutar simulación", type="primary", use_container_width=True)

    if gen_click:
        if initial_csv is None or not initial_csv.exists():
            st.error("Selecciona un CSV inicial válido para generar escenarios.")
        else:
            try:
                targets = parse_fill_targets(target_raw)
                created = build_scenario_variants(
                    base_csv=str(initial_csv),
                    targets=targets,
                    seed=int(scenario_seed),
                )
                if created:
                    st.success("Escenarios generados correctamente.")
                    for fp in created:
                        st.write(fp)
                else:
                    st.info("No se generaron escenarios nuevos (targets <= ocupación actual).")
            except Exception as exc:
                st.error(f"Error generando escenarios: {exc}")

    if not run_click:
        st.info("Ajusta parámetros y pulsa 'Ejecutar simulación'.")
        return

    if mode == "online" and dispatch_every > n_cajas:
        st.warning(
            "Dispatch es mayor que cajas entrantes; puede haber poca intercalación de salida durante llegada."
        )

    config_summary = {
        "mode": mode,
        "strategy": "custom" if custom_weights else strategy,
        "scenario": scenario_name,
        "compare": "Sí" if compare else "No",
        "n_cajas": str(n_cajas),
        "n_destinos": str(n_destinos),
        "arrival_rate_h": f"{arrival_rate_h:.0f}",
        "dispatch_every": str(dispatch_every),
    }
    _render_config_summary(config_summary)

    with st.spinner("Ejecutando simulación..."):
        primary_result, csv_summary, primary_events, primary_palets = _run_simulation(
            mode=mode,
            n_cajas=int(n_cajas),
            n_destinos=int(n_destinos),
            seed=int(seed),
            initial_csv=initial_csv,
            arrival_rate_h=float(arrival_rate_h),
            dispatch_every=int(dispatch_every),
            strategy=strategy,
            history_size=int(history_size),
            history_destinos=int(history_destinos),
            history_skew=float(history_skew),
            custom_weights=custom_weights,
        )

    st.markdown("---")

    tab_dash, tab_events, tab_palets, tab_debug = st.tabs(
        ["Dashboard", "Eventos", "Palets", "Detalle técnico"]
    )

    with tab_dash:
        st.write(f"Escenario inicial seleccionado: {scenario_name}")
        if csv_summary:
            st.caption("Resumen carga de estado inicial")
            st.json(csv_summary)

        _render_metrics(f"Resultados modo {mode}", primary_result)
        if custom_weights:
            st.caption("Pesos heurísticos activos")
            st.json(custom_weights)

    secondary_result = None
    secondary_events: List[dict] = []
    if compare:
        secondary_mode = "batch" if mode == "online" else "online"
        with st.spinner(f"Ejecutando comparativa modo {secondary_mode}..."):
            secondary_result, _, secondary_events, _ = _run_simulation(
                mode=secondary_mode,
                n_cajas=int(n_cajas),
                n_destinos=int(n_destinos),
                seed=int(seed),
                initial_csv=initial_csv,
                arrival_rate_h=float(arrival_rate_h),
                dispatch_every=int(dispatch_every),
                strategy=strategy,
                history_size=int(history_size),
                history_destinos=int(history_destinos),
                history_skew=float(history_skew),
                custom_weights=custom_weights,
            )

        with tab_dash:
            st.markdown("---")
            _render_metrics(f"Resultados modo {secondary_mode}", secondary_result)

            delta_cols = st.columns(3)
            delta_cols[0].metric(
                "Δ throughput (primario-secundario)",
                round(primary_result["throughput_palets_hora"] - secondary_result["throughput_palets_hora"], 3),
            )
            delta_cols[1].metric(
                "Δ palets completos",
                primary_result["palets_completados"] - secondary_result["palets_completados"],
            )
            delta_cols[2].metric(
                "Δ t_sim (s)",
                round(primary_result["t_simulacion_s"] - secondary_result["t_simulacion_s"], 3),
            )

    with tab_events:
        if compare and secondary_result is not None:
            left, right = st.columns(2)
            with left:
                _render_event_animation(primary_events, f"Animación eventos ({mode})", "primary")
            with right:
                _render_event_animation(secondary_events, f"Animación eventos ({secondary_mode})", "secondary")
        else:
            _render_event_animation(primary_events, f"Animación eventos ({mode})", "single")

    with tab_palets:
        st.subheader("Palets completados")
        st.write(f"Total palets reportados: {len(primary_palets)}")
        if primary_palets:
            pal_df = pd.DataFrame(primary_palets)
            st.dataframe(pal_df, use_container_width=True)
            st.caption("Distribución de tiempos de cierre de palets")
            if "t_fin" in pal_df.columns:
                st.bar_chart(pal_df["t_fin"])
        else:
            st.info("No se completaron palets en esta corrida.")

    with tab_debug:
        st.subheader("Parámetros de ejecución")
        st.json(config_summary)
        st.subheader("Resultado primario (raw)")
        st.json(primary_result)
        if secondary_result is not None:
            st.subheader("Resultado secundario (raw)")
            st.json(secondary_result)


if __name__ == "__main__":
    main()
