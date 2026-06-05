Multi-Objective Container Loading Optimization with NSGA-II
A Python-based multi-objective ooptimisationproject for container placement using NSGA-II. The project models a vessel loading problem where containers must be assigned to slots while balancing unloading priority, vessel stability, and slot utilization under stacking constraints.

Repository Summary
Field	Details
Project type	Multi-objective optimization
Domain	Logistics, vessel loading, operations research
Algorithm	NSGA-II
Library	`pymoo`
Language	Python
Data	Synthetic containers with random weights and unloading priorities
Main outputs	Pareto front, selected layout, solution summary, 3D plots
Core skills	Constraint modeling, Pareto optimization, logistics simulation, decision analytics

Problem
Container loading is not just a packing problem.
A good loading plan must balance several competing goals:
Keep unloading order practical
Maintain stable weight distribution
Use vessel slots efficiently
Avoid unsupported stacks
Avoid unsafe heavy-over-light stacking patterns
Keep the final layout interpretable for operations teams
These goals conflict. A layout that uses more slots may create worse stack feasibility. A layout that improves unloading order may shift the center of gravity. A layout with better balance may force awkward container placement.
That makes the problem a good fit for multi-objective optimization.

First-Principles View
The real question is not:
```text
Can we place containers into available slots?
```
The real question is:
```text
Can we generate feasible loading layouts that balance unloading order, vessel stability, and capacity usage?
```
A single weighted score would hide the trade-offs. NSGA-II is useful because it produces a Pareto front, where each solution represents a different operational compromise.

Solution
The project formulates container loading as a constrained multi-objective assignment problem.
Each candidate solution assigns containers to vessel slots.
```text
x[i] = slot assigned to container i
```
The optimizer evaluates each layout using three objectives:
Minimize unloading priority violations
Minimize center-of-gravity deviation
Maximize used slots
Because `pymoo` minimizes objectives by default, slot utilization is encoded as:
```python
-used_slots
```
This keeps the optimization compatible with minimization while still rewarding higher utilization.

Vessel Layout
The vessel is modelled as a 3D grid.
```text
Bays × Rows × Tiers
```
Default configuration:
```text
8 bays × 4 rows × 3 tiers = 96 available positions
```
Each position is represented as:
```text
(bay, row, tier)
```
Each container has:
Container ID
Weight
Unloading priority

Objectives
Objective	Direction	Meaning
Unloading violations	Minimize	Reduce cases where earlier-unload containers are blocked by later-unload containers
Center-of-gravity deviation	Minimize	Keep horizontal weight distribution near the vessel center
Used slots	Maximize	Increase container placement utilization

Constraints
Constraint	Purpose
Duplicate slot assignment	Prevent multiple containers from occupying the same vessel slot
Unsupported stack	Prevent containers from floating above empty positions
Unsafe weight stack	Penalize containers placed above another container when the upper container is too much heavier
In `pymoo`, constraints are feasible when `G <= 0`. Since this project uses violation counts, a constraint value of `0` means feasible and a positive value means violation.

Algorithm
The project uses NSGA-II, a genetic algorithm designed for multi-objective optimization.
NSGA-II is suitable because:
The assignment space is large
The objectives conflict
The constraints are non-trivial
There is no single best layout
Decision makers need trade-off options

Project Structure
```text
container-loading-nsga2-v2/
│
├── container_loading_nsga2_v2.py
├── README.md
├── requirements.txt
├── .gitignore
└── results/
    ├── containers.csv
    ├── positions.csv
    ├── pareto_front.csv
    ├── selected_layout.csv
    ├── solution_summary.csv
    ├── pareto_front_3d.png
    └── selected_layout_3d.png
```
The `results/` folder is generated after running the script.

Installation
Clone the repository:
```bash
git clone https://github.com/your-username/container-loading-nsga2-v2.git
cd container-loading-nsga2-v2
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
Requirements
```text
numpy
pandas
matplotlib
pymoo==0.6.0
```
Run the Project
Default run:
```bash
python container_loading_nsga2_v2.py
```
Fast smoke test:
```bash
python container_loading_nsga2_v2.py --generations 20 --population 40
```
Custom vessel size:
```bash
python container_loading_nsga2_v2.py --bays 10 --rows 4 --tiers 3 --containers 120
```
Custom optimization budget:
```bash
python container_loading_nsga2_v2.py --population 150 --generations 200
```
Command-Line Options
Argument	Default	Meaning
`--bays`	8	Number of vessel bays
`--rows`	4	Number of rows per bay
`--tiers`	3	Number of stacking tiers
`--containers`	96	Number of containers to place
`--min-weight`	5.0	Minimum synthetic container weight
`--max-weight`	20.0	Maximum synthetic container weight
`--min-priority`	1	Earliest unloading priority
`--max-priority`	4	Latest unloading priority
`--max-heavier-delta`	3.0	Maximum allowed heavier-over-lighter stack delta
`--population`	100	NSGA-II population size
`--generations`	100	Number of generations
`--seed`	42	Random seed
`--output-dir`	`results`	Output directory

Output Files
`containers.csv`
Synthetic container dataset.
Column	Meaning
`id`	Container ID
`weight`	Synthetic container weight
`priority`	Unloading priority

`positions.csv`
Generated vessel slot grid.
Column	Meaning
`slot_id`	Slot index
`bay`	Bay coordinate
`row`	Row coordinate
`tier`	Vertical tier coordinate

`pareto_front.csv`
Objective values for non-dominated solutions.
Column	Meaning
`solution_id`	Pareto solution index
`unloading_violations`	Number of unloading conflicts
`cog_deviation`	Center-of-gravity deviation
`negative_used_slots`	Negative utilization objective
`used_slots`	Number of unique slots used

`solution_summary.csv`
Detailed summary of Pareto solutions.
Includes:
Unloading violations
Center-of-gravity deviation
Used slots
Duplicate slot violations
Unsupported stack violations
Unsafe weight-stack violations
Total constraint violations

`selected_layout.csv`
Readable container-to-slot assignment for the selected balanced solution.

`pareto_front_3d.png`
3D plot of the Pareto front.
Axes:
```text
Unloading Violations | Center-of-Gravity Deviation | Used Slots
```

`selected_layout_3d.png`
3D visualization of the selected container layout.
Axes:
```text
Bay | Row | Tier
```
Colour indicates unloading priority. Marker size indicates container weight.

Representative Solution Selection

Solution Type	Selection Logic
Most used	Highest slot utilization, then fewer violations
Lowest unloading violations	Best unloading-order score
Lowest CoG deviation	Best weight-balance score
Most feasible	Lowest total constraint violations
Balanced	Best normalized compromise across objectives and constraint violations
The balanced solution is exported as `selected_layout.csv`.

Founder-Style Product Diagnosis
User
A logistics planner, operations research student, shipping analyst, or portfolio reviewer.
Pain Point
Container loading decisions involve trade-offs that are hard to compare manually.
Smallest Useful Version
A synthetic optimizer that generates vessel layouts and exposes trade-offs between unloading order, stability, and utilization.
Script
A reproducible Python script with clean outputs, Pareto-front analysis, selected layout export, and visual decision support.

Scientific and Optimization Skills Demonstrated
This project demonstrates:
Multi-objective optimization
Constraint modeling
Evolutionary algorithms
Pareto-front analysis
Integer decision repair
Synthetic data generation
Logistics optimization
3D visualization
Decision-support reporting
The scientific value is in the trade-off modeling. This is not meant to be a full industrial loading solver. It is a controlled optimisation prototype.

Security and Data Notes
This project is low-risk.
Area	Status
Secrets	None
API keys	None
User data	None
External user input	None
File uploads	None
Dataset	Synthetic
Privacy risk	Low
Main dependency risk	`pymoo` version compatibility

Limitations
Synthetic data only
Simplified vessel geometry
Simplified stability proxy
No crane sequencing
No port schedule constraints
No hazardous-material rules
No refrigerated-container slot rules
No real-world vessel trim model
NSGA-II may need tuning for larger instances

Future Improvements
Add real or anonymized container manifests
Add crane-move minimization
Add hazardous-material separation rules
Add reefer container slot constraints
Add port sequence modeling
Add vessel trim and stability constraints
Add Plotly interactive 3D layout viewer
Add Streamlit Pareto-front explorer
Add sensitivity analysis for population size and generations
Add repeated runs with seed-level robustness checks


