# CS 324 — Traffic Light Simulation

**CS 324: Modeling and Simulation | AY 2025–2026**

---

## Overview

A **high-fidelity discrete-event simulation** of a 4-way, multi-lane traffic intersection using Python + SimPy.  

### Key Features
- **Parallel Throughput**: Models a 2-lane road per direction where multiple vehicles discharge simultaneously.
- **Realistic Driver Behavior**: Includes randomized reaction delays (0.1–0.6s) and headway jitter to mimic real-world traffic flow.
- **Dynamic Visuals**: Animated Tkinter GUI with assorted vehicle types (cars, vans, trucks), random color palettes, and smooth state transitions.
- **Data-Driven**: Automatic generation of wait-time distributions, queue analysis, and throughput metrics.

### Scenarios
| Scenario | Arrival Rate (per lane) | Green Duration |
|---|---|---|
| Low Traffic | 5 veh/min | 30 s |
| Normal | 10 veh/min | 30 s |
| Rush Hour | 20 veh/min | 45 s |
| Optimized | 20 veh/min | 60 s |

---

## Setup

```bash
# 1. Clone / unzip the project
cd traffic_light_sim

# 2. Install dependencies
pip install -r requirements.txt
```

---

## Run

### Simulation only (all scenarios, generate CSV + charts)
```bash
python src/main.py
```

### GUI visualization
```bash
python src/gui.py                  # default: normal scenario
python src/gui.py rush_hour        # specific scenario
python src/gui.py low_traffic
```

### Unit tests
```bash
python -m pytest tests/ -v
# or
python tests/test_simulation.py
```

---

## Project Structure

```
traffic_light_sim/
├── src/
│   ├── main.py              # Entry point — runs all scenarios
│   ├── simulation.py        # SimPy core engine
│   ├── traffic_light.py     # Traffic light FSM
│   ├── vehicle.py           # Vehicle model
│   ├── config.py            # All parameters & scenarios
│   ├── data_collector.py    # CSV output
│   ├── charts.py            # Matplotlib chart generation
│   └── gui.py               # Tkinter animated visualization
├── data/                    # CSV outputs (generated on run)
├── charts/                  # PNG chart outputs (generated on run)
├── docs/                    # Report and diagrams
├── tests/
│   └── test_simulation.py   # Unit tests
├── requirements.txt
└── README.md
```

---

## Outputs

After running `python src/main.py`:

**CSV files (`/data/`):**
- `low_traffic_results.csv` — per-vehicle data
- `normal_results.csv`
- `rush_hour_results.csv`
- `summary.csv` — cross-scenario comparison

**Charts (`/charts/`):**
- `avg_wait_time.png` — average wait time comparison
- `arrived_vs_departed.png` — throughput comparison
- `queue_<scenario>.png` — max queue per lane (3 charts)
- `queue_over_time_<scenario>.png` — queue history over time
- `wait_time_distribution.png` — histogram of wait times
- `throughput_ratio.png` — efficiency metric

---

## Technology Stack

| Tool | Purpose |
|---|---|
| Python 3.10+ | Language |
| SimPy | Discrete-event simulation engine |
| NumPy | Poisson/exponential random arrivals |
| Pandas | Data collection and CSV export |
| Matplotlib | Chart generation |
| Tkinter | Animated GUI visualization |

---

*CS 324: Modeling and Simulation — Final Project*
