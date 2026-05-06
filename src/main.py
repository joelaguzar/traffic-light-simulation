#!/usr/bin/env python3
"""
Entry point for the Traffic Light Simulation.
This script runs the simulation across multiple traffic scenarios,
collects performance data, and generates visual charts for analysis.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from simulation import TrafficSimulation
from data_collector import save_vehicle_data, save_summary, print_summary_table
import charts as chart_module

SCENARIO_NAMES = ["low_traffic", "normal", "rush_hour"]

BASE_DIR   = os.path.dirname(os.path.dirname(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")

def run_all_scenarios():
    all_results = []

    print("=" * 60)
    print("  Traffic Light Simulation - Performance Analysis")
    print("  Batangas State University | AY 2025–2026")
    print("=" * 60)

    for scenario in SCENARIO_NAMES:
        print(f"\n▶ Starting simulation: {scenario.upper().replace('_', ' ')}")
        
        sim = TrafficSimulation(scenario)
        results = sim.run()
        all_results.append(results)

        save_vehicle_data(results, output_dir=DATA_DIR)

    print()
    save_summary(all_results, output_dir=DATA_DIR)

    print_summary_table(all_results)

    chart_module.generate_all_charts(all_results, output_dir=CHARTS_DIR)

    print("\n✓ Processing complete. Results are available in /data and /charts.")
    print("  Launch the visualizer with: python src/gui.py")
    return all_results

if __name__ == "__main__":
    run_all_scenarios()
