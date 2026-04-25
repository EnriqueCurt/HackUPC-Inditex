"""
╔══════════════════════════════════════════════════════════╗
║       SILO LOGÍSTICO — Algoritmos Optimizados            ║
║       Hackathon — Motor de Simulación                    ║
╚══════════════════════════════════════════════════════════╝

Estrategias implementadas:
  ENTRADA  → Destination-aware slotting + balanceo de carga por lanzadera
  SALIDA   → C-SCAN por shuttle + prioridad dinámica entre palés activos
  SHUTTLES → Una por (pasillo, nivel Y), algoritmo de barrido elevator

Soporte extra para hackathon:
    - Carga de estado inicial desde CSV de silo semi-lleno
    - Simulación online de entrada a una tasa configurable (p.ej. 1000 cajas/h)
    - Generación de escenarios adicionales con mayor porcentaje de llenado
"""

from __future__ import annotations

import csv
import json
import os
import random
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ─────────────────────────── CONSTANTES ──────────────────────────────────────

N_PASILLOS  = 4
N_LADOS     = 2
X_MAX       = 60
Y_MAX       = 8
Z_MAX       = 2
T_OP        = 10      # segundos por operación pick/place (fijo)
PALET_SIZE  = 12      # cajas por palé
MAX_ACTIVOS = 8       # palés activos simultáneos (2 robots × 4 palés)


Pos = Tuple[int, int, int, int, int]  # (pasillo, lado, x, y, z)

HEURISTIC_KEYS = (
    "w_shuttle",
    "w_x",
    "w_depth",
    "w_lane_fill",
    "w_pop",
    "w_close_pallet",
)

STRATEGY_PRESETS: Dict[str, Dict[str, float]] = {
    "balanced": {
        "w_shuttle": 1.00,
        "w_x": 0.90,
        "w_depth": 0.35,
        "w_lane_fill": 0.30,
        "w_pop": 0.35,
        "w_close_pallet": 2.5,
    },
    "throughput": {
        "w_shuttle": 1.20,
        "w_x": 0.80,
        "w_depth": 0.30,
        "w_lane_fill": 0.20,
        "w_pop": 0.40,
        "w_close_pallet": 3.2,
    },
    "pick_speed": {
        "w_shuttle": 0.70,
        "w_x": 1.30,
        "w_depth": 0.55,
        "w_lane_fill": 0.35,
        "w_pop": 0.55,
        "w_close_pallet": 4.0,
    },
}


def parse_posicion(raw: str) -> Pos:
    """
    Parsea formato PPSSXXXYYZZ (11 dígitos) a tupla (p,s,x,y,z).
    """
    txt = (raw or "").strip()
    if len(txt) != 11 or not txt.isdigit():
        raise ValueError(f"Posición inválida: {raw!r}")

    p = int(txt[0:2])
    s = int(txt[2:4])
    x = int(txt[4:7])
    y = int(txt[7:9])
    z = int(txt[9:11])

    if not (1 <= p <= N_PASILLOS):
        raise ValueError(f"Pasillo fuera de rango en {raw!r}: {p}")
    if not (1 <= s <= N_LADOS):
        raise ValueError(f"Lado fuera de rango en {raw!r}: {s}")
    if not (1 <= x <= X_MAX):
        raise ValueError(f"X fuera de rango en {raw!r}: {x}")
    if not (1 <= y <= Y_MAX):
        raise ValueError(f"Y fuera de rango en {raw!r}: {y}")
    if not (1 <= z <= Z_MAX):
        raise ValueError(f"Z fuera de rango en {raw!r}: {z}")

    return p, s, x, y, z


def pos_to_str(pos: Pos) -> str:
    p, s, x, y, z = pos
    return f"{p:02d}_{s:02d}_{x:03d}_{y:02d}_{z:02d}"


def read_layout_rows(csv_path: str) -> List[Tuple[int, str, str]]:
    """
    Lee filas del CSV con cabeceras `posicion,etiqueta`.
    Retorna: (line_no, posicion_raw, etiqueta_raw)
    """
    rows: List[Tuple[int, str, str]] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV sin cabeceras: {csv_path}")

        field_map = {name.strip().lower(): name for name in reader.fieldnames}
        if "posicion" not in field_map or "etiqueta" not in field_map:
            raise ValueError(
                f"CSV {csv_path!r} debe tener cabeceras 'posicion,etiqueta'"
            )

        k_pos = field_map["posicion"]
        k_tag = field_map["etiqueta"]

        for line_no, row in enumerate(reader, start=2):
            pos_raw = (row.get(k_pos) or "").strip()
            tag_raw = (row.get(k_tag) or "").strip()
            rows.append((line_no, pos_raw, tag_raw))
    return rows


def parse_fill_targets(raw: str) -> List[float]:
    """Parsea una lista de targets de llenado como '0.4,0.7,0.9'."""
    targets: List[float] = []
    for tok in (raw or "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        v = float(tok)
        if not (0.0 < v <= 1.0):
            raise ValueError(f"Target de llenado inválido: {tok}")
        targets.append(v)

    if not targets:
        raise ValueError("Debe indicar al menos un target de llenado")

    return sorted(set(targets))


def gen_historico_sintetico(
    n_envios: int = 1_000_000,
    n_dest: int = 120,
    skew: float = 1.15,
    seed: int = 42,
) -> Dict[str, int]:
    """
    Genera un histórico sintético de popularidad de destinos.
    Retorna: destino -> frecuencia
    """
    if n_envios <= 0:
        raise ValueError("n_envios debe ser > 0")
    if n_dest <= 1:
        raise ValueError("n_dest debe ser > 1")
    if skew <= 0:
        raise ValueError("skew debe ser > 0")

    rng = random.Random(seed)
    destinos = [f"{rng.randint(10_000_000, 99_999_999):08d}" for _ in range(n_dest)]
    pesos = [1.0 / ((idx + 1) ** skew) for idx in range(n_dest)]

    counts = {d: 0 for d in destinos}
    sampled = rng.choices(destinos, weights=pesos, k=n_envios)
    for d in sampled:
        counts[d] += 1
    return counts


def normalizar_popularidad(dest_counts: Dict[str, int]) -> Dict[str, float]:
    """Normaliza frecuencias a rango [0,1]."""
    if not dest_counts:
        return {}

    max_v = max(dest_counts.values())
    min_v = min(dest_counts.values())
    if max_v == min_v:
        return {k: 0.5 for k in dest_counts}

    return {
        k: (v - min_v) / (max_v - min_v)
        for k, v in dest_counts.items()
    }


def build_scenario_variants(
    base_csv: str,
    targets: List[float],
    seed: int = 42,
) -> List[str]:
    """
    Genera escenarios adicionales a partir de un CSV de estado inicial,
    incrementando el porcentaje de ocupación de forma reproducible.
    """
    rows = read_layout_rows(base_csv)
    parsed_rows: List[Tuple[int, str, Pos, str]] = []

    for line_no, pos_raw, tag_raw in rows:
        if not pos_raw:
            raise ValueError(f"Fila {line_no}: posición vacía no permitida")
        pos = parse_posicion(pos_raw)
        parsed_rows.append((line_no, pos_raw, pos, tag_raw))

    total_slots = len(parsed_rows)
    existing: Dict[Pos, str] = {
        pos: tag for _, _, pos, tag in parsed_rows if tag
    }
    current_occupied = len(existing)

    existing_tags = [tag for tag in existing.values()]
    rng = random.Random(seed)

    destinos = [tag[7:15] for tag in existing_tags]
    origenes = [tag[:7] for tag in existing_tags]
    if not destinos:
        destinos = [f"{rng.randint(10_000_000, 99_999_999):08d}" for _ in range(64)]
    if not origenes:
        origenes = [f"{rng.randint(3_000_000, 3_999_999):07d}" for _ in range(64)]

    max_seq = 0
    for tag in existing_tags:
        try:
            max_seq = max(max_seq, int(tag[15:]))
        except ValueError:
            continue

    base_dir = os.path.dirname(base_csv) or "."
    base_name = os.path.splitext(os.path.basename(base_csv))[0]
    all_positions = [pos for _, _, pos, _ in parsed_rows]
    pos_to_raw = {pos: raw for _, raw, pos, _ in parsed_rows}

    generated_files: List[str] = []

    for target in targets:
        desired = max(current_occupied, min(total_slots, int(round(target * total_slots))))
        if desired == current_occupied:
            continue

        occ = set(existing.keys())
        labels = dict(existing)
        seq = max_seq

        while len(occ) < desired:
            legal: List[Pos] = []
            for pos in all_positions:
                if pos in occ:
                    continue
                p, s, x, y, z = pos
                if z == 1 or (p, s, x, y, 1) in occ:
                    legal.append(pos)

            if not legal:
                break

            # Sesgo suave a posiciones cercanas a cabecera (x bajo)
            legal.sort(key=lambda pp: (pp[2], pp[0], pp[3], pp[1], pp[4]))
            top_n = max(1, len(legal) // 3)
            chosen = rng.choice(legal[:top_n])

            seq += 1
            code = (
                f"{rng.choice(origenes)}"
                f"{rng.choice(destinos)}"
                f"{(seq % 100_000):05d}"
            )
            labels[chosen] = code
            occ.add(chosen)

        fill_pct = int(round(100.0 * len(occ) / total_slots))
        out_name = f"{base_name}-fill-{fill_pct:02d}.csv"
        out_path = os.path.join(base_dir, out_name)

        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["posicion", "etiqueta"])
            for _, _, pos, _ in parsed_rows:
                writer.writerow([pos_to_raw[pos], labels.get(pos, "")])

        generated_files.append(out_path)

    return generated_files


# ─────────────────────────── DATACLASSES ─────────────────────────────────────

@dataclass
class Caja:
    codigo:  str
    origen:  str
    destino: str
    bulto:   str
    pos:     Optional[Pos] = None

    @staticmethod
    def parse(codigo: str) -> "Caja":
        if len(codigo) != 20:
            raise ValueError(f"Código inválido (debe tener 20 dígitos): {codigo!r}")
        return Caja(
            codigo=codigo,
            origen=codigo[:7],
            destino=codigo[7:15],
            bulto=codigo[15:],
        )

    def fmt_pos(self) -> str:
        if not self.pos:
            return "─────────────"
        return pos_to_str(self.pos)


@dataclass
class Lanzadera:
    """
    Una lanzadera por (pasillo, nivel Y).
    Modela posición actual y disponibilidad temporal.
    """
    pasillo: int
    y:       int
    x:       int   = 0      # posición actual en X (cabecera = 0)
    libre:   float = 0.0    # tiempo en el que queda disponible

    def leg(self, dest_x: int) -> float:
        """Coste de un tramo: T_OP + distancia."""
        return T_OP + abs(dest_x - self.x)

    def mover(self, dest_x: int, desde: float = 0.0) -> float:
        """Ejecuta el movimiento. Retorna tiempo de finalización."""
        t = max(self.libre, desde) + self.leg(dest_x)
        self.x = dest_x
        self.libre = t
        return t


# ─────────────────────────── SILO ────────────────────────────────────────────

class Silo:
    """
    Motor principal de simulación del silo automatizado.

    Atributos públicos de interés:
        grid          → posición -> Caja  (estado actual del almacén)
        completados   → lista de palés completados con métricas
        eventos       → log completo de operaciones (útil para la UI)
        stats         → contadores de rendimiento
    """

    def __init__(
        self,
        strategy: str = "balanced",
        destination_priority: Optional[Dict[str, float]] = None,
        custom_weights: Optional[Dict[str, float]] = None,
    ):
        # ── Estado del almacén ────────────────────────────────────────────────
        self.grid: Dict[Pos, Caja] = {}

        # ── Lanzaderas: (pasillo, y) → Lanzadera ─────────────────────────────
        self.shuttles: Dict[Tuple[int, int], Lanzadera] = {
            (p, y): Lanzadera(p, y)
            for p in range(1, N_PASILLOS + 1)
            for y in range(1, Y_MAX + 1)
        }

        # ── Índices ───────────────────────────────────────────────────────────
        # destino → lista de posiciones actualmente en grid
        self.by_dest: Dict[str, List[Pos]] = defaultdict(list)
        # palés activos (en proceso de recuperación)
        self.activos: Dict[str, List[Pos]] = {}

        # ── Resultados ────────────────────────────────────────────────────────
        self.completados: List[dict] = []
        self.eventos:     List[dict] = []
        self.stats = {
            "iniciales_cargadas": 0,
            "almacenadas":   0,
            "recuperadas":   0,
            "reubicaciones": 0,
            "rechazadas_full": 0,
            "rechazadas_csv": 0,
        }
        self.last_result: Optional[dict] = None

        self.strategy = strategy
        self.destination_priority: Dict[str, float] = dict(destination_priority or {})

        # Pesos de heurística para slotting y picking.
        self.heur = self._build_strategy(strategy)
        if custom_weights:
            self.set_heuristic_weights(custom_weights)
            self.strategy = "custom"

        # ── Punteros de relleno secuencial por (pasillo, lado, y) ─────────────
        # Valor: (x_actual, z_actual) — llenamos x=1→60, z=1 antes z=2
        self._ptr: Dict[Tuple[int, int, int], Tuple[int, int]] = {
            (p, s, y): (1, 1)
            for p in range(1, N_PASILLOS + 1)
            for s in range(1, N_LADOS + 1)
            for y in range(1, Y_MAX + 1)
        }

    def _rebuild_ptr(self):
        """Reconstruye punteros de búsqueda de huecos según estado actual de `grid`."""
        for p in range(1, N_PASILLOS + 1):
            for s in range(1, N_LADOS + 1):
                for y in range(1, Y_MAX + 1):
                    ptr = (X_MAX + 1, 1)
                    for x in range(1, X_MAX + 1):
                        z1 = (p, s, x, y, 1)
                        z2 = (p, s, x, y, 2)
                        if z1 not in self.grid:
                            ptr = (x, 1)
                            break
                        if z2 not in self.grid:
                            ptr = (x, 2)
                            break
                    self._ptr[(p, s, y)] = ptr

    def _build_strategy(self, strategy: str) -> Dict[str, float]:
        """
        Devuelve pesos heurísticos por estrategia.
        """
        if strategy not in STRATEGY_PRESETS:
            raise ValueError(f"Estrategia desconocida: {strategy}")
        return dict(STRATEGY_PRESETS[strategy])

    def set_heuristic_weights(self, custom_weights: Dict[str, float]):
        """
        Aplica pesos heurísticos custom. Permite override parcial.
        """
        unknown = [k for k in custom_weights.keys() if k not in HEURISTIC_KEYS]
        if unknown:
            raise ValueError(f"Pesos desconocidos: {unknown}")

        for k, v in custom_weights.items():
            fv = float(v)
            if fv < 0:
                raise ValueError(f"Peso {k} debe ser >= 0")
            self.heur[k] = fv

    def get_heuristic_weights(self) -> Dict[str, float]:
        return dict(self.heur)

    def set_destination_priority(self, priority: Dict[str, float]):
        """Actualiza mapa de prioridad de destinos (0..1)."""
        self.destination_priority = dict(priority or {})

    def _lane_fill_ratio(self, p: int, s: int, y: int) -> float:
        """
        Estima ocupación de una lane (p,s,y) usando el puntero de siguiente hueco.
        """
        x, z = self._ptr[(p, s, y)]
        if x > X_MAX:
            return 1.0
        occupied_slots = (x - 1) * 2 + (z - 1)
        return occupied_slots / float(X_MAX * Z_MAX)

    def _slot_score(self, destino: str, pos: Pos) -> float:
        p, s, x, y, z = pos
        sh = self.shuttles[(p, y)]

        pop = self.destination_priority.get(destino, 0.5)
        lane_fill = self._lane_fill_ratio(p, s, y)

        # Destinos populares priorizan posiciones más accesibles (x bajo, z=1)
        x_norm = x / float(X_MAX)
        depth_pen = 1.0 if z == 2 else 0.0

        return (
            self.heur["w_shuttle"] * sh.libre
            + self.heur["w_x"] * x_norm * (0.5 + pop)
            + self.heur["w_depth"] * depth_pen * (0.7 + pop)
            + self.heur["w_lane_fill"] * lane_fill
            + self.heur["w_pop"] * pop * x_norm
        )

    def load_initial_csv(self, path: str, strict: bool = True) -> dict:
        """
        Carga un estado inicial del silo desde CSV con formato:
          posicion,etiqueta

        - `strict=True`: falla si detecta inconsistencias.
        - `strict=False`: ignora filas inválidas y reporta rechazos.
        """
        rows = read_layout_rows(path)
        empty_tag_rows = 0
        parse_errors: List[str] = []
        pending: List[Tuple[int, Pos, Caja]] = []

        for line_no, pos_raw, tag_raw in rows:
            if not pos_raw:
                parse_errors.append(f"L{line_no}: posición vacía")
                continue

            try:
                pos = parse_posicion(pos_raw)
            except ValueError as exc:
                parse_errors.append(f"L{line_no}: {exc}")
                continue

            if not tag_raw:
                empty_tag_rows += 1
                continue

            try:
                caja = Caja.parse(tag_raw)
            except ValueError as exc:
                parse_errors.append(f"L{line_no}: {exc}")
                continue

            pending.append((line_no, pos, caja))

        occupancy = set(self.grid.keys())
        valid: List[Tuple[int, Pos, Caja]] = []

        for line_no, pos, caja in pending:
            if pos in occupancy:
                parse_errors.append(f"L{line_no}: posición duplicada {pos_to_str(pos)}")
                continue
            occupancy.add(pos)
            valid.append((line_no, pos, caja))

        valid_final: List[Tuple[int, Pos, Caja]] = []
        for line_no, pos, caja in valid:
            p, s, x, y, z = pos
            if z == 2 and (p, s, x, y, 1) not in occupancy:
                parse_errors.append(
                    f"L{line_no}: z=2 sin z=1 ocupada en {pos_to_str(pos)}"
                )
                continue
            valid_final.append((line_no, pos, caja))

        if strict and parse_errors:
            raise ValueError(
                f"CSV inicial inválido ({len(parse_errors)} errores). "
                f"Primer error: {parse_errors[0]}"
            )

        for _, pos, caja in valid_final:
            self.grid[pos] = caja
            caja.pos = pos
            self.by_dest[caja.destino].append(pos)

        for dest in self.by_dest:
            self.by_dest[dest].sort()

        self.stats["iniciales_cargadas"] += len(valid_final)
        if not strict:
            self.stats["rechazadas_csv"] += len(parse_errors)

        self._rebuild_ptr()

        return {
            "csv": path,
            "filas": len(rows),
            "filas_vacias": empty_tag_rows,
            "cajas_cargadas": len(valid_final),
            "rechazadas": len(parse_errors) if not strict else 0,
            "modo_estricto": strict,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # ENTRADA — Asignación de posición
    # ══════════════════════════════════════════════════════════════════════════

    def _find_slot(self, p: int, s: int, y: int) -> Optional[Pos]:
        """
        Escanea hacia adelante desde el puntero para encontrar el
        siguiente slot libre respetando la restricción Z=1 < Z=2.
        """
        x, z = self._ptr[(p, s, y)]
        while x <= X_MAX:
            # Restricción: z=2 solo si z=1 está ocupado
            if z == 2 and (p, s, x, y, 1) not in self.grid:
                z = 1   # retroceder a z=1 en el mismo x
                continue
            pos = (p, s, x, y, z)
            if pos not in self.grid:
                return pos
            # Posición ocupada → avanzar
            if z == 1:
                z = 2
            else:
                z = 1
                x += 1
        return None  # slot (pasillo, lado, y) lleno

    def _advance_ptr(self, p: int, s: int, y: int, x: int, z: int):
        """Avanza el puntero tras asignar la posición (p,s,x,y,z)."""
        if z == 1:
            self._ptr[(p, s, y)] = (x, 2)
        elif x + 1 <= X_MAX:
            self._ptr[(p, s, y)] = (x + 1, 1)

    def _best_slot(self, destino: str) -> Optional[Pos]:
        """
        Algoritmo de asignación inteligente:

        1. Pasillo preferido = hash(destino) % N_PASILLOS
           → Boxes del mismo destino van al mismo pasillo (localidad)
        2. Nivel Y = el que tenga la lanzadera más libre (balanceo)
        3. Lado = el primer lado con slot disponible
        4. Fallback circular por los demás pasillos
        """
        p0 = int(destino) % N_PASILLOS + 1
        pasillos = [(p0 - 1 + off) % N_PASILLOS + 1 for off in range(N_PASILLOS)]

        candidates: List[Pos] = []
        for p in pasillos:
            for y in range(1, Y_MAX + 1):
                for s in range(1, N_LADOS + 1):
                    slot = self._find_slot(p, s, y)
                    if slot:
                        candidates.append(slot)

        if not candidates:
            return None

        return min(candidates, key=lambda pos: self._slot_score(destino, pos))

    # ──────────────────────────────────────────────────────────────────────────

    def store(self, caja: Caja, t0: float = 0.0) -> float:
        """
        Almacena una caja.

        Ciclo de lanzadera (2 tramos):
          Leg 1: X_actual → X=0  (ir a cabecera a recoger caja entrante)
          Leg 2: X=0      → X    (depositar en posición asignada)

        Retorna: tiempo de finalización (segundos de simulación).
        """
        slot = self._best_slot(caja.destino)
        if slot is None:
            self.stats["rechazadas_full"] += 1
            self._log("FULL", max(0.0, t0), caja, None)
            return -1.0

        p, s, x, y, z = slot
        sh = self.shuttles[(p, y)]

        t1 = sh.mover(0, t0)   # Leg 1: ir a cabecera
        t2 = sh.mover(x, t1)   # Leg 2: depositar

        self.grid[slot] = caja
        caja.pos = slot
        self.by_dest[caja.destino].append(slot)
        self.stats["almacenadas"] += 1
        self._advance_ptr(p, s, y, x, z)

        self._log("IN", t2, caja, slot)
        return t2

    # ══════════════════════════════════════════════════════════════════════════
    # SALIDA — Recuperación de palés
    # ══════════════════════════════════════════════════════════════════════════

    def _select_pallets(self):
        """
        Rellena los slots de palés activos (hasta MAX_ACTIVOS).

        Criterio de prioridad:
          1. Destinos con ≥ PALET_SIZE cajas (palés completos)
          2. Luego por cantidad descendente (maximizar output)
        """
        ya_activos = set(self.activos)
        candidatos = [
            (d, ps)
            for d, ps in self.by_dest.items()
            if d not in ya_activos and ps
        ]
        # Priorizar palés completos; luego más cajas
        candidatos.sort(key=lambda kv: (-min(len(kv[1]), PALET_SIZE), kv[0]))

        for dest, poss in candidatos:
            if len(self.activos) >= MAX_ACTIVOS:
                break
            self.activos[dest] = list(poss[:PALET_SIZE])

    def _retrieve_cost(self, pos: Pos, dest: Optional[str] = None) -> float:
        """
        Coste estimado para recuperar la caja en `pos`.
        Incluye penalización si z=2 está bloqueado por z=1.
        """
        p, s, x, y, z = pos
        sh = self.shuttles[(p, y)]
        cost = sh.libre + sh.leg(x) + T_OP + x   # leg-to-box + return-to-0
        if z == 2 and (p, s, x, y, 1) in self.grid:
            cost += 2 * (T_OP + x)               # penalización reubicación

        # Bonus por cerrar antes un palé activo (reduce coste efectivo)
        if dest and dest in self.activos:
            pendientes = sum(1 for pp in self.activos[dest] if pp in self.grid)
            avance = max(0, PALET_SIZE - pendientes)
            cost -= self.heur["w_close_pallet"] * avance

        return cost

    def _relocate(self, pos: Pos) -> bool:
        """
        Reubica la caja bloqueante en `pos` a otro slot libre del mismo
        nivel Y y pasillo (para desbloquear z=2).

        Retorna True si tuvo éxito.
        """
        p, s, x, y, z = pos
        caja = self.grid.get(pos)
        if caja is None:
            return False

        sh = self.shuttles[(p, y)]

        # Buscar primer hueco libre en el mismo nivel, distinto X
        for dx in range(1, X_MAX + 1):
            if dx == x:
                continue
            for zz in (1, 2):
                if zz == 2 and (p, s, dx, y, 1) not in self.grid:
                    continue  # z=2 sin z=1 → ilegal
                cand = (p, s, dx, y, zz)
                if cand in self.grid:
                    continue

                # Ejecutar reubicación: pick en x, place en dx
                t1 = sh.mover(x, sh.libre)
                sh.mover(dx, t1)

                # Actualizar grid
                del self.grid[pos]
                self.grid[cand] = caja
                caja.pos = cand

                # Actualizar índice de destino
                d = caja.destino
                if pos in self.by_dest[d]:
                    self.by_dest[d].remove(pos)
                    self.by_dest[d].append(cand)

                # Actualizar posiciones en palés activos
                for poss in self.activos.values():
                    if pos in poss:
                        poss[poss.index(pos)] = cand

                self.stats["reubicaciones"] += 1
                self._log("RELOC", sh.libre, caja, cand)
                return True

        return False  # no hay hueco

    def _retrieve(self, pos: Pos) -> float:
        """
        Recupera la caja en `pos` hacia la cabecera.

        Ciclo de lanzadera (2 tramos):
          Leg 1: X_actual → X_pos  (pick up)
          Leg 2: X_pos    → X=0    (entregar a cabecera)

        Si z=2 bloqueado por z=1 → reubica z=1 primero.
        Retorna tiempo de finalización.
        """
        p, s, x, y, z = pos
        if pos not in self.grid:
            return self.shuttles[(p, y)].libre

        # Desbloquear z=2 si z=1 está ocupado
        if z == 2:
            z1_pos = (p, s, x, y, 1)
            if z1_pos in self.grid:
                self._relocate(z1_pos)

        sh = self.shuttles[(p, y)]
        caja = self.grid[pos]

        t1 = sh.mover(x, sh.libre)   # Leg 1: ir a recoger
        t2 = sh.mover(0, t1)          # Leg 2: volver a cabecera

        # Retirar del almacén
        del self.grid[pos]
        d = caja.destino
        if pos in self.by_dest[d]:
            self.by_dest[d].remove(pos)
        self.stats["recuperadas"] += 1

        self._log("OUT", t2, caja, pos)
        return t2

    def _execute_wave(self) -> int:
        """
        Ejecuta una ola de recuperaciones sobre todos los palés activos.

        Algoritmo C-SCAN por lanzadera:
          - Agrupa posiciones a recuperar por (pasillo, y) → cada lanzadera
            procesa su grupo independientemente (paralelismo entre Y-levels)
          - Dentro de cada grupo: ordena por X en la dirección de avance
            de la lanzadera (elevator algorithm) → minimiza reversas
          - Las lanzaderas de distintos Y operan en paralelo

        Retorna: número de posiciones procesadas.
        """
        # plan: shuttle_key → [(pos, destino)]
        plan: Dict[Tuple[int, int], List[Tuple[Pos, str]]] = defaultdict(list)
        for dest, poss in self.activos.items():
            for pos in poss:
                if pos in self.grid:
                    plan[(pos[0], pos[3])].append((pos, dest))

        if not plan:
            return 0

        count = 0
        for (p, y), items in plan.items():
            # Prioridad dinámica: escoger siempre la siguiente extracción
            # con menor coste estimado entre todas las cajas pendientes
            # del shuttle.
            while items:
                best_idx = min(
                    range(len(items)),
                    key=lambda idx: self._retrieve_cost(items[idx][0], items[idx][1]),
                )
                pos, _dest = items.pop(best_idx)
                if pos not in self.grid:
                    continue  # ya recuperado (p.ej. reubicado)
                self._retrieve(pos)
                count += 1

        return count

    def _close_pallets(self) -> List[str]:
        """
        Cierra los palés cuyas cajas han sido totalmente recuperadas.
        Retorna lista de destinos cerrados.
        """
        cerrados = []
        for dest in list(self.activos.keys()):
            poss = self.activos[dest]
            pendientes = [p for p in poss if p in self.grid]
            recuperadas = len(poss) - len(pendientes)

            if recuperadas == len(poss):  # palé completamente vaciado
                # t_fin = cuando la última lanzadera que sirvió este palé queda libre
                t_fin = max(
                    (self.shuttles[(p[0], p[3])].libre for p in poss),
                    default=0.0,
                )
                completo = recuperadas == PALET_SIZE
                r = dict(
                    destino=dest,
                    cajas=recuperadas,
                    completo=completo,
                    t_fin=round(t_fin, 1),
                )
                if completo:
                    self.completados.append(r)
                    self._log("PALET", t_fin, None, None, extra=r)

                del self.activos[dest]
                cerrados.append(dest)

        return cerrados

    def run_dispatch_cycle(self) -> int:
        """Ejecuta un ciclo de salida (selección + ola + cierre de palés)."""
        self._select_pallets()
        if not self.activos:
            return 0
        n = self._execute_wave()
        self._close_pallets()
        return n

    def run_exit(self):
        """Fase de salida completa. Itera hasta vaciar el índice de destinos."""
        while True:
            n = self.run_dispatch_cycle()
            if n == 0:
                break  # nada procesable → salir

    # ══════════════════════════════════════════════════════════════════════════
    # SIMULACIÓN COMPLETA
    # ══════════════════════════════════════════════════════════════════════════

    def _build_result(self, total_incoming: int, t_total: float, t_wall_0: float) -> dict:
        n_pal = len(self.completados)
        cajas_modeladas = self.stats["iniciales_cargadas"] + total_incoming
        n_posibles = cajas_modeladas // PALET_SIZE
        throughput = n_pal / (t_total / 3600) if t_total else 0.0
        t_prom = (
            sum(r["t_fin"] for r in self.completados) / n_pal
            if n_pal else 0.0
        )

        resultado = {
            "strategy":                self.strategy,
            "cajas_iniciales":          self.stats["iniciales_cargadas"],
            "cajas_entrantes":          total_incoming,
            "cajas_almacenadas":        self.stats["almacenadas"],
            "cajas_recuperadas":        self.stats["recuperadas"],
            "cajas_rechazadas_full":    self.stats["rechazadas_full"],
            "reubicaciones":            self.stats["reubicaciones"],
            "palets_completados":       n_pal,
            "palets_posibles":          n_posibles,
            "tasa_completitud_%":       round(n_pal / n_posibles * 100, 1) if n_posibles else 0,
            "t_simulacion_s":           round(t_total, 1),
            "t_simulacion_h":           round(t_total / 3600, 3),
            "throughput_palets_hora":   round(throughput, 2),
            "t_promedio_palet_s":       round(t_prom, 1),
            "t_computo_s":              round(time.perf_counter() - t_wall_0, 4),
        }
        self.last_result = resultado
        return resultado

    def simulate(self, codigos: List[str], verbose: bool = True) -> dict:
        """
        Ejecuta la simulación completa:
          1. Fase ENTRADA: almacena todas las cajas
          2. Fase SALIDA:  recupera palés hasta vaciar el almacén

        Retorna: diccionario con todas las métricas de rendimiento.
        """
        t_wall_0 = time.perf_counter()

        if verbose:
            print(f"\n{'═' * 60}")
            print(f"  SILO LOGÍSTICO — Simulación")
            print(f"  {len(codigos)} cajas  ·  "
                  f"{len(set(c[7:15] for c in codigos))} destinos únicos")
            print(f"{'═' * 60}")

        # ── FASE 1: ENTRADA ───────────────────────────────────────────────────
        for cod in codigos:
            self.store(Caja.parse(cod))

        t_entrada = max(sh.libre for sh in self.shuttles.values())
        if verbose:
            print(f"  ▶ ENTRADA completada  — t_sim = {t_entrada:.0f}s")

        # ── FASE 2: SALIDA ────────────────────────────────────────────────────
        self.run_exit()

        t_total = max(sh.libre for sh in self.shuttles.values())
        if verbose:
            print(f"  ▶ SALIDA  completada  — t_sim = {t_total:.0f}s")

        resultado = self._build_result(len(codigos), t_total, t_wall_0)

        if verbose:
            print(f"{'─' * 60}")
            for k, v in resultado.items():
                print(f"  {k:<35} {v}")
            print(f"{'═' * 60}\n")

        return resultado

    def simulate_online(
        self,
        codigos: List[str],
        arrival_rate_h: float = 1000.0,
        dispatch_every: int = PALET_SIZE,
        verbose: bool = True,
    ) -> dict:
        """
        Simulación online:
          - Las cajas llegan a ritmo `arrival_rate_h`
          - Se ejecutan ciclos de salida intercalados cada `dispatch_every` entradas
          - Al final se drena toda la cola de salida pendiente
        """
        if arrival_rate_h <= 0:
            raise ValueError("arrival_rate_h debe ser > 0")
        if dispatch_every <= 0:
            raise ValueError("dispatch_every debe ser > 0")

        t_wall_0 = time.perf_counter()
        dt = 3600.0 / arrival_rate_h

        if verbose:
            print(f"\n{'═' * 60}")
            print("  SILO LOGÍSTICO — Simulación ONLINE")
            print(f"  {len(codigos)} cajas entrantes  ·  llegada {arrival_rate_h:.1f} cajas/h")
            print(f"{'═' * 60}")

        for idx, cod in enumerate(codigos, start=1):
            t_arribo = (idx - 1) * dt
            fin = self.store(Caja.parse(cod), t0=t_arribo)

            if idx % dispatch_every == 0 or fin < 0:
                self.run_dispatch_cycle()

        while True:
            n = self.run_dispatch_cycle()
            if n == 0:
                break

        t_total = max((sh.libre for sh in self.shuttles.values()), default=0.0)
        resultado = self._build_result(len(codigos), t_total, t_wall_0)

        if verbose:
            print(f"  ▶ ONLINE completada — t_sim = {t_total:.0f}s")
            print(f"{'─' * 60}")
            for k, v in resultado.items():
                print(f"  {k:<35} {v}")
            print(f"{'═' * 60}\n")

        return resultado

    def to_json(self, path: str = "resultado.json"):
        """Exporta log completo para consumo de la UI."""
        out = {
            "config": {
                "N_PASILLOS": N_PASILLOS, "N_LADOS": N_LADOS,
                "X_MAX": X_MAX, "Y_MAX": Y_MAX, "Z_MAX": Z_MAX,
                "PALET_SIZE": PALET_SIZE, "MAX_ACTIVOS": MAX_ACTIVOS,
                "strategy": self.strategy,
                "heuristic_weights": self.get_heuristic_weights(),
            },
            "stats":     self.stats,
            "resultado": self.last_result,
            "palets":    self.completados,
            "eventos":   self.eventos,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"  → Exportado: {path}")

    # ──────────────────────────────────────────────────────────────────────────

    def _log(self, tipo: str, t: float, caja: Optional[Caja],
             pos: Optional[Pos], extra: dict = None):
        ev = {"tipo": tipo, "t": round(t, 1)}
        if caja:
            ev["codigo"]  = caja.codigo
            ev["destino"] = caja.destino
        if pos:
            ev["pos"] = pos_to_str(pos)
        if extra:
            ev.update(extra)
        self.eventos.append(ev)


# ─────────────────────────── GENERADOR DE DATOS ──────────────────────────────

def gen_cajas(n: int, n_dest: int = 40, seed: int = 42) -> List[str]:
    """Genera n códigos de caja sintéticos con n_dest destinos distintos."""
    rng = random.Random(seed)
    destinos = [f"{rng.randint(10_000_000, 99_999_999):08d}" for _ in range(n_dest)]
    return [
        f"{rng.randint(3_000_000, 3_999_999):07d}{rng.choice(destinos)}{i+1:05d}"
        for i in range(n)
    ]


# ─────────────────────────── PUNTO DE ENTRADA ────────────────────────────────

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Simulador Silo Logístico")
    ap.add_argument("--cajas",           type=int,   default=500,   help="Núm. de cajas entrantes")
    ap.add_argument("--destinos",        type=int,   default=40,    help="Destinos únicos sintéticos")
    ap.add_argument("--seed",            type=int,   default=42,    help="Semilla aleatoria")
    ap.add_argument("--strategy",        choices=["balanced", "throughput", "pick_speed"],
                    default="balanced", help="Perfil heurístico")
    ap.add_argument("--mode",            choices=["batch", "online"], default="online",
                    help="Modo de simulación")
    ap.add_argument("--arrival-rate",    type=float, default=1000.0,
                    help="Tasa de llegada de cajas/h en modo online")
    ap.add_argument("--dispatch-every",  type=int,   default=PALET_SIZE,
                    help="Frecuencia de despacho online (cada N entradas)")
    ap.add_argument("--initial-csv",     type=str,   default="",
                    help="CSV de estado inicial del silo (opcional)")
    ap.add_argument("--strict-csv",      action="store_true",
                    help="Validación estricta del CSV inicial")
    ap.add_argument("--make-scenarios",  action="store_true",
                    help="Generar escenarios de mayor llenado y salir")
    ap.add_argument("--scenario-base",   type=str,   default="silo-semi-empty.csv",
                    help="CSV base para generar escenarios")
    ap.add_argument("--scenario-targets", type=str,  default="0.40,0.70,0.90",
                    help="Targets de llenado CSV (0..1), separados por coma")
    ap.add_argument("--scenario-seed",   type=int,   default=42,
                    help="Semilla para generación de escenarios")
    ap.add_argument("--history-size",    type=int,   default=0,
                    help="Si >0, genera histórico sintético de destinos para priorización")
    ap.add_argument("--history-destinos", type=int,  default=120,
                    help="Nº destinos para histórico sintético")
    ap.add_argument("--history-skew",    type=float, default=1.15,
                    help="Sesgo de popularidad destino (Zipf-like)")
    ap.add_argument("--weights-json",    type=str,   default="",
                    help="Ruta a JSON con pesos heurísticos custom")
    ap.add_argument("--export",          action="store_true", help="Exportar JSON para la UI")
    ap.add_argument("--export-path",     type=str,   default="resultado.json",
                    help="Ruta de exportación JSON")
    ap.add_argument("--quiet",           action="store_true", help="Sin output verbose")
    args = ap.parse_args()

    if args.make_scenarios:
        targets = parse_fill_targets(args.scenario_targets)
        files = build_scenario_variants(
            base_csv=args.scenario_base,
            targets=targets,
            seed=args.scenario_seed,
        )
        if not files:
            print("No se generaron escenarios (targets <= ocupación actual).")
        else:
            print("Escenarios generados:")
            for fp in files:
                print(f"  - {fp}")
        raise SystemExit(0)

    codigos = gen_cajas(args.cajas, args.destinos, args.seed)

    destination_priority: Dict[str, float] = {}
    if args.history_size > 0:
        hist = gen_historico_sintetico(
            n_envios=args.history_size,
            n_dest=args.history_destinos,
            skew=args.history_skew,
            seed=args.seed,
        )
        destination_priority = normalizar_popularidad(hist)

    silo = Silo(strategy=args.strategy, destination_priority=destination_priority)

    if args.weights_json:
        with open(args.weights_json, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise ValueError("El JSON de pesos debe ser un objeto clave/valor")
        weights = raw.get("weights", raw)
        if not isinstance(weights, dict):
            raise ValueError("Clave 'weights' inválida en JSON")
        silo.set_heuristic_weights(weights)
        silo.strategy = "custom"

    if args.initial_csv:
        resumen = silo.load_initial_csv(args.initial_csv, strict=args.strict_csv)
        if not args.quiet:
            print("Estado inicial cargado:")
            for k, v in resumen.items():
                print(f"  {k:<20} {v}")

    if args.mode == "online":
        silo.simulate_online(
            codigos,
            arrival_rate_h=args.arrival_rate,
            dispatch_every=args.dispatch_every,
            verbose=not args.quiet,
        )
    else:
        silo.simulate(codigos, verbose=not args.quiet)

    if args.export:
        silo.to_json(args.export_path)
