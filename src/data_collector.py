import pandas as pd
import os

def save_vehicle_data(results, output_dir="data"):
    """
    Exports individual vehicle metrics (arrival, departure, wait times) to a CSV file.
    Returns the generated DataFrame.
    """
    os.makedirs(output_dir, exist_ok=True)
    scenario = results["scenario"]

    rows = []
    for v in results["vehicles"]:
        rows.append({
            "vehicle_id":     v.vehicle_id,
            "direction":      v.direction,
            "arrival_time":   round(v.arrival_time, 2),
            "departure_time": round(v.departure_time, 2),
            "wait_time":      round(v.wait_time, 2)
        })

    df = pd.DataFrame(rows)
    filepath = os.path.join(output_dir, f"{scenario}_results.csv")
    df.to_csv(filepath, index=False)
    print(f"  Vehicle data saved → {filepath}  ({len(df)} records)")
    return df

def save_pedestrian_data(results, output_dir="data"):
    """
    Exports individual pedestrian metrics (arrival, departure, wait times) to a CSV file.
    Returns the generated DataFrame.
    """
    os.makedirs(output_dir, exist_ok=True)
    scenario = results["scenario"]

    rows = []
    for p in results.get("pedestrians", []):
        rows.append({
            "pedestrian_id":  p.pedestrian_id,
            "crossing":       p.crossing,
            "arrival_time":   round(p.arrival_time, 2),
            "departure_time": round(p.departure_time, 2),
            "wait_time":      round(p.wait_time, 2)
        })

    df = pd.DataFrame(rows)
    filepath = os.path.join(output_dir, f"{scenario}_pedestrians.csv")
    df.to_csv(filepath, index=False)
    print(f"  Pedestrian data saved → {filepath}  ({len(df)} records)")
    return df

def save_summary(all_results, output_dir="data"):
    """
    Creates a master summary report comparing key performance indicators across all scenarios.
    """
    os.makedirs(output_dir, exist_ok=True)
    rows = []
    for r in all_results:
        max_q = r["max_queue_per_lane"]
        rows.append({
            "scenario":          r["label"],
            "total_arrived":     r["total_arrived"],
            "total_departed":    r["total_departed"],
            "throughput_ratio":  round(r["throughput_ratio"], 4),
            "avg_wait_time_sec": round(r["avg_wait_time"], 2),
            "max_wait_time_sec": round(r["max_wait_time"], 2),
            "min_wait_time_sec": round(r["min_wait_time"], 2),
            "std_wait_time_sec": round(r["std_wait_time"], 2),
            "pedestrian_arrived": r.get("pedestrian_total_arrived", 0),
            "pedestrian_departed": r.get("pedestrian_total_departed", 0),
            "pedestrian_avg_wait_sec": round(r.get("pedestrian_avg_wait_time", 0.0), 2),
            "max_queue_north":   max_q["North"],
            "max_queue_south":   max_q["South"],
            "max_queue_east":    max_q["East"],
            "max_queue_west":    max_q["West"],
        })

    df = pd.DataFrame(rows)
    filepath = os.path.join(output_dir, "summary.csv")
    df.to_csv(filepath, index=False)
    print(f"  Summary saved → {filepath}")
    return df

def print_summary_table(all_results):
    """Outputs a quick-view results table to the terminal."""
    print("\n" + "=" * 70)
    print(f"{'SCENARIO':<15} {'ARRIVED':>8} {'DEPARTED':>9} {'AVG WAIT':>10} {'MAX WAIT':>10} {'RATIO':>7}")
    print("=" * 70)
    for r in all_results:
        print(
            f"{r['label']:<15} "
            f"{r['total_arrived']:>8} "
            f"{r['total_departed']:>9} "
            f"{r['avg_wait_time']:>9.1f}s "
            f"{r['max_wait_time']:>9.1f}s "
            f"{r['throughput_ratio']:>7.3f}"
        )
    print("=" * 70)
