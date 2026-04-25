from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
from pathlib import Path
from typing import Dict, List, Tuple

from silo_hackathon import (
    HEURISTIC_KEYS,
    STRATEGY_PRESETS,
    Silo,
    gen_cajas,
    gen_historico_sintetico,
    normalizar_popularidad,
)

WeightDict = Dict[str, float]
MetricRow = Dict[str, float | int | str]


RANGES: Dict[str, Tuple[float, float]] = {
    "w_shuttle": (0.10, 3.00),
    "w_x": (0.10, 3.00),
    "w_depth": (0.00, 2.00),
    "w_lane_fill": (0.00, 2.00),
    "w_pop": (0.00, 2.50),
    "w_close_pallet": (0.00, 10.0),
}


def objective(
    avg_t_sim_s: float,
    avg_throughput: float,
    avg_completitud: float,
    avg_reubic: float,
    avg_full: float,
    alpha_throughput: float,
    alpha_completitud: float,
    alpha_reubic: float,
    alpha_full: float,
) -> float:
    """
    Score a minimizar.
    Menor score = mejor equilibrio objetivo.
    """
    return (
        avg_t_sim_s
        - alpha_throughput * avg_throughput
        - alpha_completitud * avg_completitud
        + alpha_reubic * avg_reubic
        + alpha_full * avg_full
    )


def _clip_weight(name: str, value: float) -> float:
    lo, hi = RANGES[name]
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def random_weights(rng: random.Random) -> WeightDict:
    return {
        k: rng.uniform(*RANGES[k])
        for k in HEURISTIC_KEYS
    }


def mutate_weights(base: WeightDict, rng: random.Random, sigma: float = 0.25) -> WeightDict:
    out: WeightDict = {}
    for k in HEURISTIC_KEYS:
        delta = rng.gauss(0.0, sigma)
        out[k] = _clip_weight(k, base[k] * (1.0 + delta))
    return out


def evaluate_candidate(
    weights: WeightDict,
    scenarios: List[Path],
    modes: List[str],
    seeds: List[int],
    n_cajas: int,
    n_destinos: int,
    arrival_rate_h: float,
    dispatch_every: int,
    history_size: int,
    history_destinos: int,
    history_skew: float,
    alpha_throughput: float,
    alpha_completitud: float,
    alpha_reubic: float,
    alpha_full: float,
) -> MetricRow:
    t_sims: List[float] = []
    throughputs: List[float] = []
    completitudes: List[float] = []
    reubics: List[float] = []
    fulls: List[float] = []

    # Cache por seed para no regenerar en cada escenario/modo.
    codigos_by_seed: Dict[int, List[str]] = {
        seed: gen_cajas(n_cajas, n_destinos, seed)
        for seed in seeds
    }

    prio_by_seed: Dict[int, Dict[str, float]] = {}
    for seed in seeds:
        if history_size > 0:
            hist = gen_historico_sintetico(
                n_envios=history_size,
                n_dest=history_destinos,
                skew=history_skew,
                seed=seed,
            )
            prio_by_seed[seed] = normalizar_popularidad(hist)
        else:
            prio_by_seed[seed] = {}

    for scenario in scenarios:
        for mode in modes:
            for seed in seeds:
                silo = Silo(
                    strategy="balanced",
                    destination_priority=prio_by_seed[seed],
                    custom_weights=weights,
                )
                silo.load_initial_csv(str(scenario), strict=False)

                codigos = codigos_by_seed[seed]
                if mode == "online":
                    res = silo.simulate_online(
                        codigos,
                        arrival_rate_h=arrival_rate_h,
                        dispatch_every=dispatch_every,
                        verbose=False,
                    )
                else:
                    res = silo.simulate(codigos, verbose=False)

                t_sims.append(float(res["t_simulacion_s"]))
                throughputs.append(float(res["throughput_palets_hora"]))
                completitudes.append(float(res["tasa_completitud_%"]))
                reubics.append(float(res["reubicaciones"]))
                fulls.append(float(res["cajas_rechazadas_full"]))

    avg_t = statistics.mean(t_sims)
    avg_thr = statistics.mean(throughputs)
    avg_comp = statistics.mean(completitudes)
    avg_reub = statistics.mean(reubics)
    avg_full = statistics.mean(fulls)

    score = objective(
        avg_t_sim_s=avg_t,
        avg_throughput=avg_thr,
        avg_completitud=avg_comp,
        avg_reubic=avg_reub,
        avg_full=avg_full,
        alpha_throughput=alpha_throughput,
        alpha_completitud=alpha_completitud,
        alpha_reubic=alpha_reubic,
        alpha_full=alpha_full,
    )

    out: MetricRow = {
        "score": round(score, 6),
        "avg_t_sim_s": round(avg_t, 6),
        "avg_throughput": round(avg_thr, 6),
        "avg_completitud": round(avg_comp, 6),
        "avg_reubicaciones": round(avg_reub, 6),
        "avg_rechazadas_full": round(avg_full, 6),
        "runs": len(t_sims),
    }
    for k in HEURISTIC_KEYS:
        out[k] = round(weights[k], 8)
    return out


def main():
    ap = argparse.ArgumentParser(description="Hiperoptimización de pesos heurísticos del silo")
    ap.add_argument("--scenarios", type=str, default="silo-semi-empty*.csv")
    ap.add_argument("--modes", type=str, default="online,batch",
                    help="Modos separados por coma")
    ap.add_argument("--seeds", type=str, default="7,42,99",
                    help="Seeds separadas por coma")

    ap.add_argument("--cajas", type=int, default=1200)
    ap.add_argument("--destinos", type=int, default=40)
    ap.add_argument("--arrival-rate", type=float, default=1000.0)
    ap.add_argument("--dispatch-every", type=int, default=12)

    ap.add_argument("--history-size", type=int, default=250000)
    ap.add_argument("--history-destinos", type=int, default=120)
    ap.add_argument("--history-skew", type=float, default=1.15)

    ap.add_argument("--alpha-throughput", type=float, default=20.0)
    ap.add_argument("--alpha-completitud", type=float, default=8.0)
    ap.add_argument("--alpha-reubic", type=float, default=0.4)
    ap.add_argument("--alpha-full", type=float, default=10.0)

    ap.add_argument("--iterations", type=int, default=60)
    ap.add_argument("--seed", type=int, default=42, help="Seed del optimizador")
    ap.add_argument("--exploit-prob", type=float, default=0.55,
                    help="Probabilidad de mutar alrededor del mejor")

    ap.add_argument("--out-trials", type=str, default="hyperopt_trials.csv")
    ap.add_argument("--out-best", type=str, default="best_weights.json")

    args = ap.parse_args()

    if args.iterations <= 0:
        raise SystemExit("--iterations debe ser > 0")

    cwd = Path.cwd()
    scenarios = sorted(cwd.glob(args.scenarios))
    if not scenarios:
        raise SystemExit(f"No se encontraron escenarios con patrón: {args.scenarios}")

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]

    rng = random.Random(args.seed)
    trials: List[MetricRow] = []

    # Punto de partida: presets.
    candidates: List[WeightDict] = [dict(v) for v in STRATEGY_PRESETS.values()]

    best_row: MetricRow | None = None
    best_weights: WeightDict | None = None

    for i in range(args.iterations):
        if i < len(candidates):
            w = dict(candidates[i])
        else:
            if best_weights is not None and rng.random() < args.exploit_prob:
                w = mutate_weights(best_weights, rng)
            else:
                w = random_weights(rng)

        row = evaluate_candidate(
            weights=w,
            scenarios=scenarios,
            modes=modes,
            seeds=seeds,
            n_cajas=args.cajas,
            n_destinos=args.destinos,
            arrival_rate_h=args.arrival_rate,
            dispatch_every=args.dispatch_every,
            history_size=args.history_size,
            history_destinos=args.history_destinos,
            history_skew=args.history_skew,
            alpha_throughput=args.alpha_throughput,
            alpha_completitud=args.alpha_completitud,
            alpha_reubic=args.alpha_reubic,
            alpha_full=args.alpha_full,
        )
        row["trial"] = i + 1
        trials.append(row)

        if best_row is None or float(row["score"]) < float(best_row["score"]):
            best_row = row
            best_weights = {k: float(row[k]) for k in HEURISTIC_KEYS}
            print(
                f"[trial {i+1}] nuevo mejor score={row['score']} "
                f"t={row['avg_t_sim_s']} thr={row['avg_throughput']}"
            )

    if not trials or best_row is None or best_weights is None:
        raise SystemExit("No se pudo optimizar")

    out_trials = Path(args.out_trials)
    fieldnames = list(trials[0].keys())
    with out_trials.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trials)

    best_payload = {
        "meta": {
            "iterations": args.iterations,
            "optimizer_seed": args.seed,
            "modes": modes,
            "seeds": seeds,
            "scenarios": [p.name for p in scenarios],
            "objective": {
                "alpha_throughput": args.alpha_throughput,
                "alpha_completitud": args.alpha_completitud,
                "alpha_reubic": args.alpha_reubic,
                "alpha_full": args.alpha_full,
            },
            "metrics": {
                "score": best_row["score"],
                "avg_t_sim_s": best_row["avg_t_sim_s"],
                "avg_throughput": best_row["avg_throughput"],
                "avg_completitud": best_row["avg_completitud"],
                "avg_reubicaciones": best_row["avg_reubicaciones"],
                "avg_rechazadas_full": best_row["avg_rechazadas_full"],
            },
        },
        "weights": best_weights,
    }

    out_best = Path(args.out_best)
    with out_best.open("w", encoding="utf-8") as f:
        json.dump(best_payload, f, ensure_ascii=False, indent=2)

    print("Hiperoptimización completada")
    print(f"  trials: {out_trials}")
    print(f"  best:   {out_best}")
    print(f"  best score: {best_row['score']}")


if __name__ == "__main__":
    main()
