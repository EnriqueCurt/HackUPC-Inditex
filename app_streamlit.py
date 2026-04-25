from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import plotly.express as px
import plotly.graph_objects as go

import pandas as pd
import numpy as np
import streamlit as st
import subprocess
import json
import time
import pandas as pd
import os
import platform
from pathlib import Path

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

def compilar_motor_cpp():
    """Compila los archivos C++ en un ejecutable."""
    ejecutable = CURRENT_DIR / ("simulador.exe" if platform.system() == "Windows" else "simulador")
    comando = [
    "g++", "main.cpp", "dualCycleShuttle.cpp",
    "paletManager.cpp", "silo.cpp", "-O2", "-o", str(ejecutable)
    ]
    
    with st.spinner("Compilando motor C++..."):
        try:
            subprocess.run(comando, check=True, capture_output=True, text=True, cwd=str(CURRENT_DIR))
            st.success("Codigo C++ compilado con exito.")
            return True
        except subprocess.CalledProcessError as e:
            st.error(f"Error al compilar C++:\n{e.stderr}")
            return False

# Obtener la ruta de la carpeta donde está este script de python
CURRENT_DIR = Path(__file__).parent.absolute()

def ejecutar_motor_cpp(parametros):
    # Ruta absoluta al ejecutable y al json
    ejecutable = str(CURRENT_DIR / "simulador.exe") if platform.system() == "Windows" else str(CURRENT_DIR / "simulador")
    json_path = CURRENT_DIR / "output.json"
    
    # Limpiamos el json antiguo si existe para no leer datos viejos
    if json_path.exists():
        os.remove(json_path)

    comando = [ejecutable]
    for k, v in parametros.items():
        if v != "": comando.extend([f"--{k}", str(v)])
            
    try:
        # Ejecutamos especificando el directorio de trabajo (cwd)
        subprocess.run(comando, check=True, cwd=str(CURRENT_DIR))
        
        if not json_path.exists():
            st.error(f"No se encontró el archivo en: {json_path}")
            return None, None, None

        with open(json_path, "r") as f:
            data = json.load(f)
            
        return data["metrics"], data["events"], data["pallets"]
    except Exception as e:
        st.error(f"❌ Error leyendo output.json: {e}")
        return None, None, None

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


def _render_metrics(title: str, res: Dict):
    st.subheader(f"📊 {title}")
    
    # Primera fila: Los "Big Numbers"
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏆 Score Total", f"{int(res.get('score', 0)):,}")
    c2.metric("📦 Palets", f"{res.get('palets_completados', 0)} uds")
    c3.metric("⏱️ Tiempo Sim", f"{res.get('t_simulacion_s', 0)} s")
    c4.metric("📉 Cajas en Silo", f"{res.get('cajas_restantes_silo', 0)}")

    st.markdown("---")
    
    # Segunda fila: Rendimiento y Estabilidad
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**Productividad**")
        st.metric("Throughput", f"{res.get('throughput_palets_hora', 0):.2f} pal/h")
        st.progress(min(res.get('tasa_completitud_%', 0) / 100, 1.0), text="Completitud")

    with col2:
        st.write("**Tiempo por Palet**")
        st.metric("Media", f"{res.get('tiempo_medio_s_palet', 0):.2f} s", delta_color="inverse")
        st.metric("Mediana", f"{res.get('mediana_tiempo_s_palet', 0):.2f} s")

    with col3:
        st.write("**Estado del Sistema**")
        
        # Mostramos el porcentaje de completitud en grande
        tasa = res.get('tasa_completitud_%', 0)
        st.metric(label="Completitud", value=f"{tasa:.1f} %")

        # Mostramos las cajas que se han quedado en el silo
        cajas_restantes = res.get('cajas_restantes_silo', 0)
        st.metric(label="Cajas en Silo (Final)", value=f"{cajas_restantes} uds")

        # Mensaje de estado rápido
        if tasa >= 100:
            st.success("✅ Todo completado")
        else:
            st.warning(f"⚠️ {100 - tasa:.1f}% por procesar")

def _render_event_animation(events: List[dict], section_title: str, key_prefix: str):
    st.markdown("<style>.main .block-container{max-width:100%; padding:1rem;}</style>", unsafe_allow_html=True)
    
    if not events:
        st.info("No hay eventos para mostrar en el Gemelo Digital.")
        return

    # Convertimos a DataFrame
    df = pd.DataFrame(events)

    # --- FIX CRÍTICO: Normalizar nombres de columnas ---
    # Esto convierte 'X', 'Y', 'Z', 'T' en 'x', 'y', 'z', 't' automáticamente
    df.columns = [str(c).lower() for c in df.columns]

    # Comprobación de seguridad
    if 'x' not in df.columns:
        st.error(f"❌ Error: El JSON no tiene la columna 'x'. Columnas encontradas: {list(df.columns)}")
        st.write("Muestra de datos recibidos:", events[:2]) # Ayuda a debugear
        return

    # Ordenar por tiempo
    df = df.sort_values('t').reset_index(drop=True)
    
    # Asegurar que sean números
    df['x'] = pd.to_numeric(df['x'], errors='coerce').fillna(0)
    df['y'] = pd.to_numeric(df['y'], errors='coerce').fillna(0)
    df['z'] = pd.to_numeric(df['z'], errors='coerce').fillna(0)

    frames = []
    current_stock = set() 
    # Usamos 200 eventos para fluidez
    df_anim = df.head(200).copy() 

    for i, row in df_anim.iterrows():
        rx, ry, rz = int(row['x']), int(row['y']), int(row['z'])
        tipo = str(row['tipo']).upper()
        
        if tipo == 'OUT':
            current_stock.discard((rx, ry, rz))
        
        # Preparar coordenadas del stock actual
        if current_stock:
            inv_x, inv_y, inv_z = zip(*current_stock)
        else:
            inv_x, inv_y, inv_z = [], [], []

        frames.append(go.Frame(
            data=[
                # Capa 1: Stock (Azul)
                go.Scatter3d(x=list(inv_x), y=list(inv_y), z=list(inv_z), 
                             mode='markers', name='Stock',
                             marker=dict(size=6, color='#219ebc', opacity=0.3, symbol='square')),
                # Capa 2: Shuttle (Rojo)
                go.Scatter3d(x=[rx], y=[ry], z=[rz], 
                             mode='markers', name='Shuttle',
                             marker=dict(size=14, color='#e63946', symbol='diamond')),
                # Capa 3: Caja activa (Amarillo)
                go.Scatter3d(x=[rx], y=[ry], z=[rz], 
                             mode='markers', name='Caja',
                             marker=dict(size=8, color='#ffb703', symbol='square'))
            ],
            name=f"f{i}"
        ))

        if tipo == 'IN':
            current_stock.add((rx, ry, rz))

    fig = go.Figure()
    # Trazas base para que la leyenda siempre aparezca
    fig.add_trace(go.Scatter3d(x=[], y=[], z=[], mode='markers', name='Stock', marker=dict(color='#219ebc')))
    fig.add_trace(go.Scatter3d(x=[], y=[], z=[], mode='markers', name='Shuttle', marker=dict(color='#e63946')))
    fig.add_trace(go.Scatter3d(x=[], y=[], z=[], mode='markers', name='Caja', marker=dict(color='#ffb703')))

    fig.frames = frames

    fig.update_layout(
        height=850,
        scene=dict(
            aspectmode='manual',
            aspectratio=dict(x=3, y=1, z=0.5),
            xaxis=dict(title="X", range=[-2, 62], backgroundcolor="rgb(230, 230,230)"),
            yaxis=dict(title="Y", range=[0, 9], backgroundcolor="rgb(230, 230,230)"),
            zaxis=dict(title="Z", range=[0.5, 2.5], backgroundcolor="rgb(230, 230,230)"),
        ),
        updatemenus=[{
            "buttons": [
                {"label": "▶ REPRODUCIR", "method": "animate", "args": [None, {"frame": {"duration": 50, "redraw": True}, "fromcurrent": True}]},
                {"label": "⏸ PAUSA", "method": "animate", "args": [[None], {"mode": "immediate"}]}
            ],
            "type": "buttons", "showactive": False, "x": 0.05, "y": 0.05
        }],
        margin=dict(l=0, r=0, b=0, t=30),
        title=f"<b>{section_title}</b>"
    )

    st.plotly_chart(fig, use_container_width=True)

def _render_config_summary(summary: Dict[str, str]):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Configuración activa</div>', unsafe_allow_html=True)
    row1 = st.columns(4)
    row1[1].metric("Estrategia", summary["strategy"])
    row1[2].metric("Escenario", summary["scenario"])
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

    if "sim_result" not in st.session_state:
        st.session_state.sim_result = None
    if "sim_events" not in st.session_state:
        st.session_state.sim_events = None
    if "sim_palets" not in st.session_state:
        st.session_state.sim_palets = None
    if "sim_config" not in st.session_state:
        st.session_state.sim_config = None

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
            # --- Nueva opción Modo ABC ---
            st.markdown('<div class="section-title">Configuración Algoritmo</div>', unsafe_allow_html=True)
            modo_abc = st.checkbox("Activar Clasificación ABC", value=False, help="Organiza el almacén priorizando productos de alta rotación.")

            # Guardamos el valor en un string para pasárselo al C++
            abc_flag = "true" if modo_abc else "false"
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
        run_click = st.button("Ejecutar simulacion", type="primary", use_container_width=True)

        if run_click:
            ejecutable = CURRENT_DIR / ("simulador.exe" if platform.system() == "Windows" else "simulador")
            if not ejecutable.exists():
                if not compilar_motor_cpp():
                    st.error("No se pudo compilar el motor C++.")
                    st.stop()

            params = {
                "cajas": n_cajas,
                "destinos": n_destinos,
                "seed": seed,
                "strategy": strategy,
                "abc": abc_flag,
                "arrival-rate": arrival_rate_h,
                "dispatch-every": dispatch_every,
                "initial-csv": str(initial_csv) if initial_csv else ""
            }

            primary_result, primary_events, primary_palets = ejecutar_motor_cpp(params)

            if primary_result is None:
                st.error("Error al obtener datos del motor C++.")
                st.stop()

            st.session_state.sim_result = primary_result
            st.session_state.sim_events = primary_events
            st.session_state.sim_palets = primary_palets
            st.session_state.sim_config = {
                "strategy": "custom" if custom_weights else strategy,
                "scenario": scenario_name,
                "n_cajas": str(n_cajas),
                "n_destinos": str(n_destinos),
                "arrival_rate_h": f"{arrival_rate_h:.0f}",
                "dispatch_every": str(dispatch_every),
            }

    if st.session_state.sim_result is None:
        st.info("Configura parametros y pulsa 'Ejecutar simulacion'.")
        st.stop()

    if st.session_state.sim_config is not None:
        _render_config_summary(st.session_state.sim_config)

   # --- RENDERIZADO ÚNICO (MOTOR C++) ---
    st.markdown("---")
    
    # Solo una pestaña de Dashboard y una de Gemelo Digital
    tab_dash, tab_shuttle, tab_palets = st.tabs(
        ["📊 Dashboard de Rendimiento", "🤖 Gemelo Digital 3D", "📦 Detalle Palets"]
    )

    with tab_dash:
        # Esto llamará a la función de métricas pero solo con un resultado
        _render_metrics("Resultados Motor C++", st.session_state.sim_result)
        
        # Si quieres ver el score grande, podemos añadirlo aquí
        if "score" in st.session_state.sim_result:
            st.metric("🏆 SCORE TOTAL", st.session_state.sim_result["score"])

        # Comparativa visual rápida entre Media y Mediana
        st.info(f"💡 **Análisis de estabilidad:** La diferencia entre la media ({st.session_state.sim_result['tiempo_medio_s_palet']:.1f}s) "
                f"y la mediana ({st.session_state.sim_result['mediana_tiempo_s_palet']:.1f}s) indica la consistencia del algoritmo "
                f"frente a picos de trabajo.")
        

    with tab_shuttle:
        # Tu animación a pantalla completa
        _render_event_animation(st.session_state.sim_events, "Simulación Real-Time", "cpp_single")

    with tab_palets:
        if st.session_state.sim_palets:
            st.dataframe(pd.DataFrame(st.session_state.sim_palets), use_container_width=True)
        else:
            st.info("No hay datos de palets.")

if __name__ == "__main__":
    main()
