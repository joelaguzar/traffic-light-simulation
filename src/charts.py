import matplotlib.pyplot as plt
import numpy as np
import os

COLORS = {
    "low_traffic": "#2ecc71",
    "normal":      "#3498db",
    "rush_hour":   "#e74c3c",
    "optimized":   "#9b59b6",
}

LANE_COLORS = ["#5dade2", "#f1948a", "#82e0aa", "#f9e79f"]

def _save(fig, path):
    """Helper to standardize figure saving across all chart types."""
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart generated → {path}")

def chart_avg_wait_time(all_results, output_dir="charts"):
    """Compares average delays across the different tested scenarios."""
    os.makedirs(output_dir, exist_ok=True)
    labels   = [r["label"] for r in all_results]
    values   = [r["avg_wait_time"] for r in all_results]
    colors   = [COLORS.get(r["scenario"], "#95a5a6") for r in all_results]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, values, color=colors, edgecolor="white", linewidth=0.8)
    ax.bar_label(bars, fmt="%.1f s", padding=4, fontsize=11, fontweight="bold")
    ax.set_title("Average Vehicle Wait Time by Scenario", fontsize=14, fontweight="bold")
    ax.set_xlabel("Scenario", fontsize=12)
    ax.set_ylabel("Average Wait Time (seconds)", fontsize=12)
    ax.set_ylim(0, max(values) * 1.25)
    ax.grid(axis="y", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _save(fig, os.path.join(output_dir, "avg_wait_time.png"))

def chart_arrived_vs_departed(all_results, output_dir="charts"):
    """Visualizes volume vs. capacity by comparing total arrivals and departures."""
    os.makedirs(output_dir, exist_ok=True)
    labels   = [r["label"] for r in all_results]
    arrived  = [r["total_arrived"] for r in all_results]
    departed = [r["total_departed"] for r in all_results]
    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    b1 = ax.bar(x - width / 2, arrived,  width, label="Arrived",  color="#5dade2", edgecolor="white")
    b2 = ax.bar(x + width / 2, departed, width, label="Departed", color="#f1948a", edgecolor="white")
    ax.bar_label(b1, padding=3, fontsize=9)
    ax.bar_label(b2, padding=3, fontsize=9)
    ax.set_title("Vehicles Arrived vs Departed by Scenario", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Number of Vehicles", fontsize=12)
    ax.legend(fontsize=11)
    ax.grid(axis="y", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _save(fig, os.path.join(output_dir, "arrived_vs_departed.png"))

def chart_max_queue_per_lane(all_results, output_dir="charts"):
    """Identifies the biggest 'bottleneck' lane for each scenario."""
    os.makedirs(output_dir, exist_ok=True)
    for r in all_results:
        lanes  = list(r["max_queue_per_lane"].keys())
        max_qs = list(r["max_queue_per_lane"].values())
        fig, ax = plt.subplots(figsize=(7, 4))
        bars = ax.bar(lanes, max_qs, color=LANE_COLORS, edgecolor="white", linewidth=0.8)
        ax.bar_label(bars, padding=3, fontsize=11)
        ax.set_title(f"Max Queue Length per Lane — {r['label']}", fontsize=13, fontweight="bold")
        ax.set_xlabel("Lane Direction", fontsize=11)
        ax.set_ylabel("Max Vehicles in Queue", fontsize=11)
        ax.set_ylim(0, max(max_qs) * 1.3 if max(max_qs) > 0 else 5)
        ax.grid(axis="y", alpha=0.4)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        _save(fig, os.path.join(output_dir, f"queue_{r['scenario']}.png"))

def chart_queue_over_time(all_results, output_dir="charts"):
    """Plots queue fluctuations throughout the simulation period."""
    os.makedirs(output_dir, exist_ok=True)
    directions = ["North", "South", "East", "West"]
    dir_colors = {"North": "#5dade2", "South": "#f1948a",
                  "East": "#82e0aa",  "West": "#f7dc6f"}

    for r in all_results:
        time_pts = r["queue_time_points"]
        if not time_pts:
            continue
        fig, ax = plt.subplots(figsize=(10, 4))
        for d in directions:
            hist = r["queue_history"].get(d, [])
            if hist:
                ax.plot(time_pts[:len(hist)], hist, label=d,
                        color=dir_colors[d], linewidth=1.8)
        ax.set_title(f"Queue Length Over Time — {r['label']}", fontsize=13, fontweight="bold")
        ax.set_xlabel("Simulation Time (seconds)", fontsize=11)
        ax.set_ylabel("Vehicles in Queue", fontsize=11)
        ax.legend(fontsize=10, loc="upper right")
        ax.grid(alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        _save(fig, os.path.join(output_dir, f"queue_over_time_{r['scenario']}.png"))

def chart_wait_time_distribution(all_results, output_dir="charts"):
    """Overlays wait time histograms to see the 'spread' of delays."""
    os.makedirs(output_dir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    for r in all_results:
        waits = [v.wait_time for v in r["vehicles"] if v.wait_time is not None]
        if waits:
            color = COLORS.get(r["scenario"], "#95a5a6")
            ax.hist(waits, bins=40, alpha=0.55, label=r["label"], color=color, edgecolor="none")
    ax.set_title("Wait Time Distribution by Scenario", fontsize=14, fontweight="bold")
    ax.set_xlabel("Wait Time (seconds)", fontsize=12)
    ax.set_ylabel("Number of Vehicles", fontsize=12)
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _save(fig, os.path.join(output_dir, "wait_time_distribution.png"))

def chart_throughput_ratio(all_results, output_dir="charts"):
    """Shows the percentage of arrived vehicles that successfully cleared the intersection."""
    os.makedirs(output_dir, exist_ok=True)
    labels = [r["label"] for r in all_results]
    ratios = [r["throughput_ratio"] * 100 for r in all_results]
    colors = [COLORS.get(r["scenario"], "#95a5a6") for r in all_results]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(labels, ratios, color=colors, edgecolor="white")
    ax.bar_label(bars, fmt="%.1f%%", padding=4, fontsize=11, fontweight="bold")
    ax.set_title("Vehicle Throughput Ratio by Scenario\n(Departed / Arrived)", fontsize=13, fontweight="bold")
    ax.set_ylabel("Throughput (%)", fontsize=12)
    ax.set_ylim(0, 115)
    ax.axhline(100, color="black", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.grid(axis="y", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _save(fig, os.path.join(output_dir, "throughput_ratio.png"))

def generate_all_charts(all_results, output_dir="charts"):
    """Main function to trigger the generation of the entire visualization suite."""
    print("\nGenerating final report charts...")
    chart_avg_wait_time(all_results, output_dir)
    chart_arrived_vs_departed(all_results, output_dir)
    chart_max_queue_per_lane(all_results, output_dir)
    chart_queue_over_time(all_results, output_dir)
    chart_wait_time_distribution(all_results, output_dir)
    chart_throughput_ratio(all_results, output_dir)
    print(f"Visualization suite ready in /{output_dir}/")
