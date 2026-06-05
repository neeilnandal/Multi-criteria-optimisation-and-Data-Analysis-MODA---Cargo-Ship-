# Multi-Objective Container Loading Optimization with NSGA-II

A Python-based **multi-objective optimization project** for solving a container placement problem using **NSGA-II**. The project models a vessel loading scenario where containers must be assigned to available slots while balancing unloading priority, vessel stability, and capacity utilization under stacking constraints.

The goal is not to find one perfect answer. The goal is to generate a set of **Pareto-efficient container layouts** that expose the trade-offs between operational efficiency, structural feasibility, and center-of-gravity balance.

## Repository Summary

| Field        | Details                                                                            |
| ------------ | ---------------------------------------------------------------------------------- |
| Project type | Multi-objective optimization                                                       |
| Domain       | Container loading, logistics, operations research                                  |
| Algorithm    | NSGA-II                                                                            |
| Library      | `pymoo`                                                                            |
| Language     | Python                                                                             |
| Data         | Synthetic container weights and unloading priorities                               |
| Main output  | Pareto front and 3D container layout visualization                                 |
| Key skills   | Constraint modeling, Pareto optimization, logistics simulation, decision analytics |

## Problem

Container loading is not a simple packing problem.

A good layout must balance multiple competing goals:

* Containers should be loaded in a way that respects unloading priority.
* Weight should be distributed to avoid poor center-of-gravity balance.
* Slots should be used efficiently.
* Containers should not float without support.
* Heavy containers should not be stacked unsafely above weaker positions.

These goals conflict. A layout that maximizes capacity may create stability issues. A layout that improves unloading order may worsen weight balance. A layout that improves structure may reduce placement flexibility.

That makes the problem a strong fit for **multi-objective optimization**.

## First-Principles View

The real problem is not:

```text
Can we place containers into slots?
```

The real problem is:

```text
Can we generate feasible container layouts that balance operational unloading order, vessel stability, and slot utilization?
```

A single-objective optimizer would hide the trade-offs. NSGA-II is useful because it produces a Pareto front: a set of solutions where no layout is clearly better across every objective.

## Solution

This project formulates container loading as a constrained multi-objective optimization problem.

The optimizer searches for container-to-slot assignments across a vessel grid and evaluates each candidate layout using three objectives:

1. Minimize unloading priority violations
2. Minimize center-of-gravity deviation
3. Maximize number of used container slots

Because `pymoo` minimizes objectives by default, capacity usage is modeled as a negative objective:

```python
-used_count
```

This allows the optimizer to treat higher utilization as better while still using a minimization framework.

## Vessel Layout

The vessel is modeled as a 3D grid.

```text
Bays × Rows × Tiers
```

Example configuration:

```text
8 bays × 4 rows × 3 tiers = 96 available positions
```

Each position is represented as:

```text
(bay, row, tier)
```

Each container has:

* Unique container ID
* Weight
* Unloading priority

## Objectives

| Objective                   | Direction | Meaning                                                                        |
| --------------------------- | --------- | ------------------------------------------------------------------------------ |
| Unloading violations        | Minimize  | Reduce conflicts where a lower-priority container blocks a higher-priority one |
| Center-of-gravity deviation | Minimize  | Improve weight balance across the vessel                                       |
| Used containers             | Maximize  | Increase slot utilization                                                      |

## Constraints

The model includes operational and structural constraints.

| Constraint         | Purpose                                                        |
| ------------------ | -------------------------------------------------------------- |
| Unique assignment  | Prevent two containers from occupying the same slot            |
| Structural support | Prevent containers from floating above empty slots             |
| Weight stacking    | Penalize unsafe stacking patterns involving heavier containers |

These constraints make the problem closer to a real logistics decision problem rather than a simple toy optimizer.

## Algorithm: NSGA-II

The project uses **NSGA-II**, a genetic algorithm designed for multi-objective optimization.

NSGA-II is suitable because:

* The search space is large
* The objectives conflict
* The constraints are non-trivial
* There is no single best answer
* Decision makers benefit from a Pareto trade-off set

The optimizer evolves a population of candidate layouts over multiple generations, selecting layouts that perform well across competing objectives.

## App / Notebook Workflow

```text
Generate synthetic containers
        |
Generate vessel slot positions
        |
Define objective functions
        |
Define feasibility constraints
        |
Run NSGA-II optimization
        |
Extract Pareto-efficient solutions
        |
Visualize objective-space trade-offs
        |
Visualize selected container layout in 3D
```

## Recommended Project Structure

```text
container-loading-optimization/
│
├── container_loading_nsga2.py
├── MODA_ASSIGNMENT2.ipynb
├── README.md
├── requirements.txt
├── .gitignore
└── results/
    ├── pareto_front.csv
    ├── selected_layout.csv
    ├── pareto_front_3d.png
    └── container_layout_3d.png
```

## Installation

Clone the repository:

```bash
git clone https://github.com/your-username/container-loading-optimization.git
cd container-loading-optimization
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate the environment.

On macOS or Linux:

```bash
source venv/bin/activate
```

On Windows:

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Requirements

Recommended `requirements.txt`:

```text
numpy
pandas
matplotlib
pymoo==0.6.0
```

Optional, if keeping the notebook:

```text
jupyter
```

## Run the Project

If using the notebook:

```bash
jupyter notebook MODA_ASSIGNMENT2.ipynb
```

If refactored into a script:

```bash
python container_loading_nsga2.py
```

Expected outputs:

```text
results/pareto_front.csv
results/selected_layout.csv
results/pareto_front_3d.png
results/container_layout_3d.png
```

## Decision Variables

Each candidate solution represents an assignment of containers to vessel slots.

Conceptually:

```text
x[i] = slot assigned to container i
```

For example:

```text
Container 0 -> Position 12
Container 1 -> Position 45
Container 2 -> Position 7
```

The optimizer searches over these assignments to find layouts that perform well across all objectives.

## Pareto Front

The Pareto front represents the trade-off set found by NSGA-II.

Each point is one container layout.

A solution is Pareto-efficient if no other solution improves one objective without worsening at least one other objective.

Example interpretation:

| Layout Type                     | Strength               | Weakness                             |
| ------------------------------- | ---------------------- | ------------------------------------ |
| Low unloading violations        | Easier port operations | May reduce weight balance            |
| Low center-of-gravity deviation | Better stability       | May worsen unloading order           |
| High slot utilization           | Uses capacity well     | May create more feasibility pressure |
| Balanced layout                 | Practical compromise   | Not best on any single objective     |

## Visualizations

### 1. Pareto Front Plot

The Pareto plot shows the relationship between:

* Unloading violations
* Center-of-gravity deviation
* Used container count

This helps identify trade-offs between operational efficiency and vessel stability.

### 2. 3D Container Layout

The layout visualization shows the selected solution in vessel-space.

Axes:

```text
Bay | Row | Tier
```

This makes the final decision interpretable. Instead of only seeing objective values, the user can inspect where containers are actually placed.

## Result Interpretation

A typical output should not be read as:

```text
This is the single correct loading plan.
```

It should be read as:

```text
These are feasible trade-off options. The final choice depends on operational preference.
```

For example:

* If port turnaround is the main priority, choose a layout with fewer unloading violations.
* If vessel stability is the main priority, choose a layout with lower center-of-gravity deviation.
* If capacity is the main priority, choose a layout with maximum slot utilization.
* If no single priority dominates, choose a balanced Pareto solution.

## OODA Summary

### Observe

Container loading requires multiple objectives to be handled at the same time: unloading order, stability, utilization, and stack feasibility.

### Orient

The problem is combinatorial and constrained. A single-objective formulation would oversimplify the decision.

### Decide

Use NSGA-II to search for Pareto-efficient layouts instead of forcing one weighted objective.

### Act

Generate containers and positions, evaluate layouts against objectives and constraints, run NSGA-II, then visualize the Pareto front and selected layout.

## Founder-Style Product Diagnosis

### User

A logistics planner, port operations analyst, shipping optimization researcher, or operations research student.

### Pain Point

Manual container loading decisions involve competing trade-offs that are hard to compare systematically.

### Smallest Useful Version

A synthetic prototype that generates feasible layouts and shows the trade-offs between unloading priority, stability, and utilization.

### Current Version

The project demonstrates the optimization formulation and produces Pareto-front and layout visualizations.

### What Still Needs Work

The current notebook should be refactored into a cleaner script with integer-safe decision variables, clearer constraint handling, and result exports.

## Important Technical Notes

### Integer Decision Variables

Container positions are discrete. The optimizer should treat slot assignments as integer decisions.

If continuous genetic operators are used, add a repair step:

```python
from pymoo.core.repair import Repair
import numpy as np

class IntegerRoundingRepair(Repair):
    def _do(self, problem, X, **kwargs):
        return np.rint(X).astype(int)
```

This avoids silently truncating floating-point assignments during evaluation.

### Objective Direction

Since `pymoo` minimizes objectives, maximizing used containers should be expressed as:

```python
-used_count
```

When selecting the layout with maximum utilization, use:

```python
best_idx = np.argmax(-res.F[:, 2])
```

or:

```python
best_idx = np.argmin(res.F[:, 2])
```

because the third objective is stored as a negative value.

### Constraint Counting

Structural and stacking violations should be counted once per relevant placement, not repeatedly inside unnecessary nested loops. This keeps feasibility scoring fair and easier to interpret.

## Security and Data Notes

This project is low-risk.

| Area                 | Status                        |
| -------------------- | ----------------------------- |
| Secrets              | None                          |
| API keys             | None                          |
| User data            | None                          |
| External user input  | None                          |
| File uploads         | None                          |
| Data privacy risk    | Low                           |
| Dataset              | Synthetic                     |
| Main dependency risk | `pymoo` version compatibility |

Recommended hygiene:

* Keep dependencies in `requirements.txt`
* Avoid committing heavy notebook outputs
* Save plots and CSV results in `results/`
* Pin `pymoo` version for reproducibility
* Use synthetic data unless real logistics data is properly anonymized

## Scientific and Optimization Skills Demonstrated

This project demonstrates:

* Multi-objective optimization
* Constraint modeling
* Pareto-front analysis
* Evolutionary algorithms
* Synthetic data generation
* Logistics decision modeling
* 3D decision-space visualization
* Trade-off interpretation
* Operations research thinking

The scientific value is not that the model perfectly replicates real container loading. It is that the project creates a controlled optimization environment where competing objectives can be studied clearly.

## Limitations

* Synthetic data only
* Simplified vessel geometry
* Simplified stacking logic
* No real port schedule or crane sequencing
* No hazardous-material constraints
* No reefer container constraints
* No dynamic unloading sequence simulation
* Integer decision handling should be strengthened
* Constraint evaluation can be made more efficient

## Future Improvements

* Refactor notebook into a clean Python script
* Add integer repair for decision variables
* Export Pareto solutions to CSV
* Export selected layout to CSV
* Add balanced-solution selection logic
* Add crane-move minimization objective
* Add real-world container classes
* Add hazardous-material separation rules
* Add refrigerated-container slot constraints
* Add vessel trim and stability constraints
* Add interactive 3D visualization with Plotly
* Add a Streamlit dashboard for exploring Pareto solutions

## Suggested `.gitignore`

```text
__pycache__/
*.pyc
.env
.venv/
venv/
.ipynb_checkpoints/
results/*.tmp
```

## SEO Keywords

Relevant keywords:

* multi-objective optimization
* NSGA-II
* pymoo optimization
* container loading optimization
* logistics optimization
* Pareto front
* operations research
* vessel loading problem
* combinatorial optimization
* constrained optimization
* Python optimization project

## Repository Topics

```text
multi-objective-optimization
nsga2
pymoo
operations-research
logistics
container-loading
pareto-front
constrained-optimization
python
evolutionary-algorithms
```
loading optimization project for balancing unloading order, vessel stability, and slot utilization under stacking constraints.
```

