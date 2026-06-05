"""
Multi-Objective Container Loading Optimization with NSGA-II

V2 refactor of the MODA Assignment 2 notebook.

What this script does:
- Generates synthetic containers with weights and unloading priorities
- Generates a 3D vessel slot grid: bays x rows x tiers
- Solves a constrained multi-objective assignment problem using NSGA-II
- Optimizes:
    1. unloading priority violations
    2. center-of-gravity deviation
    3. slot utilization
- Enforces/penalizes:
    1. duplicate slot assignment
    2. unsupported stacked containers
    3. unsafe heavier-on-lighter stacking
- Exports:
    results/containers.csv
    results/positions.csv
    results/pareto_front.csv
    results/selected_layout.csv
    results/solution_summary.csv
    results/pareto_front_3d.png
    results/selected_layout_3d.png

Run:
    python container_loading_nsga2_v2.py

Fast smoke test:
    python container_loading_nsga2_v2.py --generations 20 --population 40
"""

from __future__ import annotations

import argparse
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import Problem
from pymoo.core.repair import Repair
from pymoo.optimize import minimize
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.sampling.rnd import IntegerRandomSampling
from pymoo.termination import get_termination
from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting


# -----------------------------------------------------------------------------
# Data classes

@dataclass(frozen=True)
class Container:
    """Container metadata used by the optimizer."""
    id: int
    weight: float
    priority: int


@dataclass(frozen=True)
class Position:
    """Vessel slot position."""
    slot_id: int
    bay: int
    row: int
    tier: int


@dataclass
class LayoutMetrics:
    """Evaluation metrics for one container layout."""
    unloading_violations: int
    cog_deviation: float
    used_slots: int
    duplicate_slot_violations: int
    unsupported_stack_violations: int
    unsafe_weight_stack_violations: int
    total_constraint_violations: int


# -----------------------------------------------------------------------------
# Synthetic data generation

def generate_containers(
    n_containers: int,
    min_weight: float,
    max_weight: float,
    min_priority: int,
    max_priority: int,
    seed: int,
) -> List[Container]:
    """Generate synthetic containers with random weights and unloading priorities."""
    rng = random.Random(seed)

    return [
        Container(
            id=i,
            weight=rng.uniform(min_weight, max_weight),
            priority=rng.randint(min_priority, max_priority),
        )
        for i in range(n_containers)
    ]


def generate_positions(n_bays: int, n_rows: int, n_tiers: int) -> List[Position]:
    """Generate vessel positions in bay-row-tier layout."""
    positions = []
    slot_id = 0

    for bay in range(n_bays):
        for row in range(n_rows):
            for tier in range(n_tiers):
                positions.append(
                    Position(
                        slot_id=slot_id,
                        bay=bay,
                        row=row,
                        tier=tier,
                    )
                )
                slot_id += 1

    return positions


# -----------------------------------------------------------------------------
# Layout evaluation

def calculate_unloading_violations(
    containers: List[Container],
    assigned_positions: List[Position],
) -> int:
    """
    Count unloading priority violations.

    A violation occurs when a lower-priority operational arrangement causes a
    higher-priority container to be blocked in the same bay-row stack.
    Priority convention:
    - Lower priority number means earlier unloading requirement.
    - If a later-unload container sits above an earlier-unload container,
      the earlier container is blocked.
    """
    violations = 0

    for i, c_above_candidate in enumerate(containers):
        pos_i = assigned_positions[i]

        for j, c_below_candidate in enumerate(containers):
            if i == j:
                continue

            pos_j = assigned_positions[j]

            same_stack = pos_i.bay == pos_j.bay and pos_i.row == pos_j.row
            above = pos_i.tier > pos_j.tier
            earlier_unload_below = c_below_candidate.priority < c_above_candidate.priority

            if same_stack and above and earlier_unload_below:
                violations += 1

    return violations


def calculate_cog_deviation(
    containers: List[Container],
    assigned_positions: List[Position],
    n_bays: int,
    n_rows: int,
) -> float:
    """
    Calculate deviation from ideal center of gravity.

    Uses bay and row dimensions only. Tier is omitted for a simple horizontal
    balance proxy.
    """
    total_weight = sum(container.weight for container in containers)

    if total_weight <= 0:
        return 1_000.0

    x_moment = 0.0
    y_moment = 0.0

    for container, position in zip(containers, assigned_positions):
        x_moment += position.bay * container.weight
        y_moment += position.row * container.weight

    actual_x = x_moment / total_weight
    actual_y = y_moment / total_weight

    target_x = (n_bays - 1) / 2
    target_y = (n_rows - 1) / 2

    return abs(actual_x - target_x) + abs(actual_y - target_y)


def calculate_duplicate_violations(slot_indices: Iterable[int]) -> int:
    """Count duplicate assignment violations."""
    slot_indices = list(slot_indices)
    return len(slot_indices) - len(set(slot_indices))


def calculate_stack_violations(
    containers: List[Container],
    assigned_positions: List[Position],
    max_heavier_delta: float,
) -> Tuple[int, int]:
    """
    Count unsupported stacks and unsafe weight-stack violations.

    Structural support is checked once per container:
    - A container in tier > 0 must have a container directly below it.

    Weight rule:
    - If a container is directly above another container and is heavier by more
      than max_heavier_delta, count one violation.
    """
    position_to_container_idx: Dict[Tuple[int, int, int], int] = {
        (pos.bay, pos.row, pos.tier): idx
        for idx, pos in enumerate(assigned_positions)
    }

    unsupported_stack_violations = 0
    unsafe_weight_stack_violations = 0

    for idx, position in enumerate(assigned_positions):
        if position.tier == 0:
            continue

        below_key = (position.bay, position.row, position.tier - 1)
        below_idx = position_to_container_idx.get(below_key)

        if below_idx is None:
            unsupported_stack_violations += 1
            continue

        current_weight = containers[idx].weight
        below_weight = containers[below_idx].weight

        if current_weight - below_weight > max_heavier_delta:
            unsafe_weight_stack_violations += 1

    return unsupported_stack_violations, unsafe_weight_stack_violations


def evaluate_layout(
    slot_indices: Iterable[int],
    containers: List[Container],
    positions: List[Position],
    n_bays: int,
    n_rows: int,
    max_heavier_delta: float,
) -> LayoutMetrics:
    """Evaluate one full container-to-slot assignment."""
    slot_indices = [int(idx) for idx in slot_indices]

    # Clip defensively in case repair is bypassed.
    slot_indices = [
        min(max(idx, 0), len(positions) - 1)
        for idx in slot_indices
    ]

    assigned_positions = [positions[idx] for idx in slot_indices]

    duplicate_violations = calculate_duplicate_violations(slot_indices)

    unloading_violations = calculate_unloading_violations(
        containers=containers,
        assigned_positions=assigned_positions,
    )

    cog_deviation = calculate_cog_deviation(
        containers=containers,
        assigned_positions=assigned_positions,
        n_bays=n_bays,
        n_rows=n_rows,
    )

    unsupported_violations, unsafe_weight_violations = calculate_stack_violations(
        containers=containers,
        assigned_positions=assigned_positions,
        max_heavier_delta=max_heavier_delta,
    )

    used_slots = len(set(slot_indices))

    total_constraint_violations = (
        duplicate_violations
        + unsupported_violations
        + unsafe_weight_violations
    )

    return LayoutMetrics(
        unloading_violations=unloading_violations,
        cog_deviation=cog_deviation,
        used_slots=used_slots,
        duplicate_slot_violations=duplicate_violations,
        unsupported_stack_violations=unsupported_violations,
        unsafe_weight_stack_violations=unsafe_weight_violations,
        total_constraint_violations=total_constraint_violations,
    )


# -----------------------------------------------------------------------------
# Pymoo problem and integer repair

class IntegerRoundingRepair(Repair):
    """
    Repair operator that rounds decision variables to valid integer slot indices.

    This fixes the rough notebook issue where continuous crossover/mutation could
    produce floating-point assignments that were later truncated implicitly.
    """
    def _do(self, problem, X, **kwargs):
        X = np.rint(X).astype(int)
        X = np.clip(X, problem.xl, problem.xu)
        return X


class ContainerPlacementProblem(Problem):
    """Constrained multi-objective container placement problem."""

    def __init__(
        self,
        containers: List[Container],
        positions: List[Position],
        n_bays: int,
        n_rows: int,
        max_heavier_delta: float,
    ):
        self.containers = containers
        self.positions = positions
        self.n_bays = n_bays
        self.n_rows = n_rows
        self.max_heavier_delta = max_heavier_delta

        super().__init__(
            n_var=len(containers),
            n_obj=3,
            n_constr=3,
            xl=0,
            xu=len(positions) - 1,
            type_var=np.int32,
        )

    def _evaluate(self, X, out, *args, **kwargs):
        F = []
        G = []

        for solution in X:
            metrics = evaluate_layout(
                slot_indices=solution,
                containers=self.containers,
                positions=self.positions,
                n_bays=self.n_bays,
                n_rows=self.n_rows,
                max_heavier_delta=self.max_heavier_delta,
            )

            F.append(
                [
                    metrics.unloading_violations,
                    metrics.cog_deviation,
                    -metrics.used_slots,
                ]
            )

            # Pymoo treats G <= 0 as feasible.
            # Since these are violation counts, zero is feasible and positive is infeasible.
            G.append(
                [
                    metrics.duplicate_slot_violations,
                    metrics.unsupported_stack_violations,
                    metrics.unsafe_weight_stack_violations,
                ]
            )

        out["F"] = np.array(F, dtype=float)
        out["G"] = np.array(G, dtype=float)


# -----------------------------------------------------------------------------
# Optimization and solution selection

def run_nsga2(
    problem: ContainerPlacementProblem,
    population_size: int,
    generations: int,
    seed: int,
):
    """Run NSGA-II with integer-safe repair."""
    repair = IntegerRoundingRepair()

    algorithm = NSGA2(
        pop_size=population_size,
        sampling=IntegerRandomSampling(),
        crossover=SBX(prob=0.9, eta=15, vtype=float, repair=repair),
        mutation=PM(eta=20, vtype=float, repair=repair),
        repair=repair,
        eliminate_duplicates=True,
    )

    termination = get_termination("n_gen", generations)

    return minimize(
        problem=problem,
        algorithm=algorithm,
        termination=termination,
        seed=seed,
        save_history=True,
        verbose=True,
    )


def extract_pareto_front(res) -> Tuple[np.ndarray, np.ndarray]:
    """Extract non-dominated solutions from pymoo results."""
    F = np.asarray(res.F)
    X = np.asarray(res.X)

    nds = NonDominatedSorting()
    pareto_indices = nds.do(F, only_non_dominated_front=True)

    return F[pareto_indices], X[pareto_indices]


def make_solution_summary(
    F: np.ndarray,
    X: np.ndarray,
    containers: List[Container],
    positions: List[Position],
    n_bays: int,
    n_rows: int,
    max_heavier_delta: float,
) -> pd.DataFrame:
    """Create a metrics summary for every Pareto solution."""
    rows = []

    for solution_id, (objectives, solution) in enumerate(zip(F, X)):
        metrics = evaluate_layout(
            slot_indices=solution,
            containers=containers,
            positions=positions,
            n_bays=n_bays,
            n_rows=n_rows,
            max_heavier_delta=max_heavier_delta,
        )

        rows.append(
            {
                "solution_id": solution_id,
                "unloading_violations": metrics.unloading_violations,
                "cog_deviation": metrics.cog_deviation,
                "used_slots": metrics.used_slots,
                "duplicate_slot_violations": metrics.duplicate_slot_violations,
                "unsupported_stack_violations": metrics.unsupported_stack_violations,
                "unsafe_weight_stack_violations": metrics.unsafe_weight_stack_violations,
                "total_constraint_violations": metrics.total_constraint_violations,
                "objective_1_unloading_violations": objectives[0],
                "objective_2_cog_deviation": objectives[1],
                "objective_3_negative_used_slots": objectives[2],
            }
        )

    return pd.DataFrame(rows)


def select_representative_solutions(summary_df: pd.DataFrame) -> Dict[str, int]:
    """
    Select interpretable representative solutions from the Pareto front.

    Returns solution IDs for:
    - most_used
    - lowest_unloading_violations
    - lowest_cog_deviation
    - most_feasible
    - balanced
    """
    selected = {}

    selected["most_used"] = int(
        summary_df.sort_values(
            ["used_slots", "total_constraint_violations", "unloading_violations", "cog_deviation"],
            ascending=[False, True, True, True],
        ).iloc[0]["solution_id"]
    )

    selected["lowest_unloading_violations"] = int(
        summary_df.sort_values(
            ["unloading_violations", "total_constraint_violations", "cog_deviation"],
            ascending=[True, True, True],
        ).iloc[0]["solution_id"]
    )

    selected["lowest_cog_deviation"] = int(
        summary_df.sort_values(
            ["cog_deviation", "total_constraint_violations", "unloading_violations"],
            ascending=[True, True, True],
        ).iloc[0]["solution_id"]
    )

    selected["most_feasible"] = int(
        summary_df.sort_values(
            ["total_constraint_violations", "unloading_violations", "cog_deviation"],
            ascending=[True, True, True],
        ).iloc[0]["solution_id"]
    )

    # Balanced solution: normalize main decision metrics and minimize total score.
    balanced_df = summary_df.copy()

    score_columns = [
        "unloading_violations",
        "cog_deviation",
        "total_constraint_violations",
    ]

    for column in score_columns:
        min_value = balanced_df[column].min()
        max_value = balanced_df[column].max()

        if max_value == min_value:
            balanced_df[f"{column}_norm"] = 0.0
        else:
            balanced_df[f"{column}_norm"] = (
                (balanced_df[column] - min_value) / (max_value - min_value)
            )

    # Slot use is a benefit, so invert it into a penalty.
    used_min = balanced_df["used_slots"].min()
    used_max = balanced_df["used_slots"].max()

    if used_max == used_min:
        balanced_df["used_slots_penalty_norm"] = 0.0
    else:
        balanced_df["used_slots_penalty_norm"] = (
            (used_max - balanced_df["used_slots"]) / (used_max - used_min)
        )

    balanced_df["balanced_score"] = (
        balanced_df["unloading_violations_norm"]
        + balanced_df["cog_deviation_norm"]
        + balanced_df["total_constraint_violations_norm"]
        + balanced_df["used_slots_penalty_norm"]
    )

    selected["balanced"] = int(
        balanced_df.sort_values("balanced_score", ascending=True).iloc[0]["solution_id"]
    )

    return selected


# -----------------------------------------------------------------------------
# Export helpers

def containers_to_dataframe(containers: List[Container]) -> pd.DataFrame:
    return pd.DataFrame([asdict(container) for container in containers])


def positions_to_dataframe(positions: List[Position]) -> pd.DataFrame:
    return pd.DataFrame([asdict(position) for position in positions])


def layout_to_dataframe(
    solution: Iterable[int],
    containers: List[Container],
    positions: List[Position],
) -> pd.DataFrame:
    """Convert one solution vector into a readable container layout table."""
    rows = []

    for container, slot_index in zip(containers, solution):
        slot_index = int(slot_index)
        position = positions[slot_index]

        rows.append(
            {
                "container_id": container.id,
                "weight": container.weight,
                "priority": container.priority,
                "slot_id": position.slot_id,
                "bay": position.bay,
                "row": position.row,
                "tier": position.tier,
            }
        )

    return pd.DataFrame(rows)


def save_outputs(
    output_dir: Path,
    containers: List[Container],
    positions: List[Position],
    pareto_front: np.ndarray,
    pareto_solutions: np.ndarray,
    summary_df: pd.DataFrame,
    selected_solution_id: int,
):
    """Save all CSV outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)

    containers_to_dataframe(containers).to_csv(output_dir / "containers.csv", index=False)
    positions_to_dataframe(positions).to_csv(output_dir / "positions.csv", index=False)

    pareto_df = pd.DataFrame(
        pareto_front,
        columns=[
            "unloading_violations",
            "cog_deviation",
            "negative_used_slots",
        ],
    )
    pareto_df["used_slots"] = -pareto_df["negative_used_slots"]
    pareto_df.insert(0, "solution_id", range(len(pareto_df)))
    pareto_df.to_csv(output_dir / "pareto_front.csv", index=False)

    summary_df.to_csv(output_dir / "solution_summary.csv", index=False)

    selected_solution = pareto_solutions[selected_solution_id]
    selected_layout_df = layout_to_dataframe(
        solution=selected_solution,
        containers=containers,
        positions=positions,
    )
    selected_layout_df.to_csv(output_dir / "selected_layout.csv", index=False)


# -----------------------------------------------------------------------------
# Plotting

def plot_pareto_front(
    pareto_front: np.ndarray,
    output_path: Path,
):
    """Save a 3D Pareto-front plot."""
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")

    unloading_violations = pareto_front[:, 0]
    cog_deviation = pareto_front[:, 1]
    used_slots = -pareto_front[:, 2]

    scatter = ax.scatter(
        unloading_violations,
        cog_deviation,
        used_slots,
        c=used_slots,
        cmap="viridis",
        s=60,
        alpha=0.85,
    )

    ax.set_title("Pareto Front: Container Loading Trade-offs")
    ax.set_xlabel("Unloading Violations")
    ax.set_ylabel("Center-of-Gravity Deviation")
    ax.set_zlabel("Used Slots")

    fig.colorbar(scatter, ax=ax, label="Used Slots")
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def plot_selected_layout(
    layout_df: pd.DataFrame,
    output_path: Path,
):
    """Save a 3D plot of one selected container layout."""
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")

    scatter = ax.scatter(
        layout_df["bay"],
        layout_df["row"],
        layout_df["tier"],
        c=layout_df["priority"],
        s=layout_df["weight"] * 10,
        cmap="coolwarm",
        alpha=0.85,
    )

    for _, row in layout_df.iterrows():
        ax.text(
            row["bay"],
            row["row"],
            row["tier"],
            str(int(row["container_id"])),
            fontsize=6,
            ha="center",
            va="center",
        )

    ax.set_title("Selected Container Layout")
    ax.set_xlabel("Bay")
    ax.set_ylabel("Row")
    ax.set_zlabel("Tier")

    fig.colorbar(scatter, ax=ax, label="Unloading Priority")
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


# -----------------------------------------------------------------------------
# Main runner

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Multi-objective container loading optimization using NSGA-II."
    )

    parser.add_argument("--bays", type=int, default=8)
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--tiers", type=int, default=3)

    parser.add_argument("--containers", type=int, default=96)
    parser.add_argument("--min-weight", type=float, default=5.0)
    parser.add_argument("--max-weight", type=float, default=20.0)
    parser.add_argument("--min-priority", type=int, default=1)
    parser.add_argument("--max-priority", type=int, default=4)
    parser.add_argument("--max-heavier-delta", type=float, default=3.0)

    parser.add_argument("--population", type=int, default=100)
    parser.add_argument("--generations", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument("--output-dir", type=Path, default=Path("results"))

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    positions = generate_positions(
        n_bays=args.bays,
        n_rows=args.rows,
        n_tiers=args.tiers,
    )

    if args.containers > len(positions):
        raise ValueError(
            f"Number of containers ({args.containers}) cannot exceed number of slots ({len(positions)})."
        )

    containers = generate_containers(
        n_containers=args.containers,
        min_weight=args.min_weight,
        max_weight=args.max_weight,
        min_priority=args.min_priority,
        max_priority=args.max_priority,
        seed=args.seed,
    )

    problem = ContainerPlacementProblem(
        containers=containers,
        positions=positions,
        n_bays=args.bays,
        n_rows=args.rows,
        max_heavier_delta=args.max_heavier_delta,
    )

    result = run_nsga2(
        problem=problem,
        population_size=args.population,
        generations=args.generations,
        seed=args.seed,
    )

    pareto_front, pareto_solutions = extract_pareto_front(result)

    summary_df = make_solution_summary(
        F=pareto_front,
        X=pareto_solutions,
        containers=containers,
        positions=positions,
        n_bays=args.bays,
        n_rows=args.rows,
        max_heavier_delta=args.max_heavier_delta,
    )

    selected = select_representative_solutions(summary_df)
    selected_solution_id = selected["balanced"]

    save_outputs(
        output_dir=args.output_dir,
        containers=containers,
        positions=positions,
        pareto_front=pareto_front,
        pareto_solutions=pareto_solutions,
        summary_df=summary_df,
        selected_solution_id=selected_solution_id,
    )

    selected_layout_df = layout_to_dataframe(
        solution=pareto_solutions[selected_solution_id],
        containers=containers,
        positions=positions,
    )

    plot_pareto_front(
        pareto_front=pareto_front,
        output_path=args.output_dir / "pareto_front_3d.png",
    )

    plot_selected_layout(
        layout_df=selected_layout_df,
        output_path=args.output_dir / "selected_layout_3d.png",
    )

    selected_summary = summary_df[summary_df["solution_id"] == selected_solution_id].iloc[0]

    print("\n" + "=" * 80)
    print("Optimization complete")
    print("=" * 80)
    print(f"Pareto solutions found: {len(pareto_front)}")
    print(f"Selected balanced solution ID: {selected_solution_id}")
    print("\nRepresentative solution IDs:")
    for name, solution_id in selected.items():
        print(f"  {name}: {solution_id}")

    print("\nSelected balanced solution metrics:")
    print(selected_summary.to_string())

    print(f"\nSaved outputs to: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
