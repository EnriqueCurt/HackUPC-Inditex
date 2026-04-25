from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Dict, List, Optional

from silo_hackathon import (
    Silo,
    gen_cajas,
    gen_historico_sintetico,
    normalizar_popularidad,
)


def run_one(
    scenario_csv: Path,
    mode: str,
    strategy: str,
    seed: int,
    n_cajas: int,
    n_destinos: int,
    arrival_rate_h: float,
    dispatch_every: int,
    history_size: int,
    history_destinos: int,
    history_skew: float,
    custom_weights: Optional[Dict[str, float]] = None,
) -> Dict:
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
    silo.load_initial_csv(str(scenario_csv), strict=False)

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

    row = {
        "scenario": scenario_csv.name,
        "mode": mode,
        "strategy": "custom" if custom_weights else strategy,
        "seed": seed,
        **result,
    }
    return row


def objective(
    r: Dict,
    alpha_throughput: float,
    alpha_completitud: float,
    alpha_reubic: float,
    alpha_full: float,
) -> float:
    return (
        float(r["t_simulacion_s"])
        - alpha_throughput * float(r["throughput_palets_hora"])
        - alpha_completitud * float(r["tasa_completitud_%"])
        + alpha_reubic * float(r["reubicaciones"])
        + alpha_full * float(r["cajas_rechazadas_full"])
    )


def main():
    ap = argparse.ArgumentParser(description="Benchmark de estrategias del silo")
    ap.add_argument("--scenarios", type=str, default="silo-semi-empty*.csv",
                    help="Patrón glob para escenarios CSV")
    ap.add_argument("--modes", type=str, default="online,batch",
                    help="Modos separados por coma")
    ap.add_argument("--strategies", type=str, default="balanced,throughput,pick_speed",
                    help="Estrategias separadas por coma")
    ap.add_argument("--seeds", type=str, default="7,42,99",
                    help="Seeds separadas por coma")

    ap.add_argument("--cajas", type=int, default=1200)
    ap.add_argument("--destinos", type=int, default=40)
    ap.add_argument("--arrival-rate", type=float, default=1000.0)
    ap.add_argument("--dispatch-every", type=int, default=12)

    ap.add_argument("--history-size", type=int, default=250000)
    ap.add_argument("--history-destinos", type=int, default=120)
    ap.add_argument("--history-skew", type=float, default=1.15)

    ap.add_argument("--weights-json", type=str, default="",
                    help="JSON con pesos custom (plano o con clave weights)")

    ap.add_argument("--alpha-throughput", type=float, default=20.0)
    ap.add_argument("--alpha-completitud", type=float, default=8.0)
    ap.add_argument("--alpha-reubic", type=float, default=0.4)
    ap.add_argument("--alpha-full", type=float, default=10.0)

    ap.add_argument("--out", type=str, default="benchmark_results.csv")
    args = ap.parse_args()

    cwd = Path.cwd()
    scenarios = sorted(cwd.glob(args.scenarios))
    if not scenarios:
        raise SystemExit(f"No se encontraron escenarios con patrón: {args.scenarios}")

    modes = [x.strip() for x in args.modes.split(",") if x.strip()]
    strategies = [x.strip() for x in args.strategies.split(",") if x.strip()]
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]

    custom_weights: Optional[Dict[str, float]] = None
    if args.weights_json:
        with open(args.weights_json, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise ValueError("weights-json inválido")
        data = raw.get("weights", raw)
        if not isinstance(data, dict):
            raise ValueError("Formato de pesos inválido")
        custom_weights = {k: float(v) for k, v in data.items()}

    rows: List[Dict] = []
    eval_strategies = strategies if custom_weights is None else ["custom"]

    for scenario in scenarios:
        for mode in modes:
            for strategy in eval_strategies:
                for seed in seeds:
                    row = run_one(
                        scenario_csv=scenario,
                        mode=mode,
                        strategy=strategy if custom_weights is None else "balanced",
                        seed=seed,
                        n_cajas=args.cajas,
                        n_destinos=args.destinos,
                        arrival_rate_h=args.arrival_rate,
                        dispatch_every=args.dispatch_every,
                        history_size=args.history_size,
                        history_destinos=args.history_destinos,
                        history_skew=args.history_skew,
                        custom_weights=custom_weights,
                    )
                    row["score"] = round(
                        objective(
                            row,
                            alpha_throughput=args.alpha_throughput,
                            alpha_completitud=args.alpha_completitud,
                            alpha_reubic=args.alpha_reubic,
                            alpha_full=args.alpha_full,
                        ),
                        6,
                    )
                    rows.append(row)

    out = Path(args.out)
    if not rows:
        raise SystemExit("No hay resultados")

    fieldnames = list(rows[0].keys())
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Ranking agregado por (modo, estrategia)
    grouped: Dict[tuple, List[Dict]] = {}
    for r in rows:
        key = (r["mode"], r["strategy"])
        grouped.setdefault(key, []).append(r)

    summary = []
    for (mode, strategy), rs in grouped.items():
        summary.append(
            {
                "mode": mode,
                "strategy": strategy,
                "runs": len(rs),
                "avg_t_sim_s": round(statistics.mean(r["t_simulacion_s"] for r in rs), 3),
                "avg_throughput": round(statistics.mean(r["throughput_palets_hora"] for r in rs), 3),
                "avg_palets": round(statistics.mean(r["palets_completados"] for r in rs), 3),
                "avg_completitud": round(statistics.mean(r["tasa_completitud_%"] for r in rs), 3),
                "avg_score": round(statistics.mean(r["score"] for r in rs), 3),
            }
        )

    summary.sort(key=lambda x: (x["avg_score"], x["avg_t_sim_s"], -x["avg_throughput"]))

    print("Benchmark completado")
    print(f"  resultados: {out}")
    print("Top estrategias:")
    for idx, row in enumerate(summary[:6], start=1):
        print(
            f"  {idx}. mode={row['mode']} strategy={row['strategy']} "
            f"avg_score={row['avg_score']} avg_t={row['avg_t_sim_s']}s "
            f"avg_thr={row['avg_throughput']} avg_palets={row['avg_palets']}"
        )


if __name__ == "__main__":
    main()
