#!/usr/bin/env python3
"""
A Tkinter-based visualizer for the traffic intersection simulation.
Provides a real-time animated view of the intersection, including 
vehicle movement, light changes, and live performance metrics.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import random

# Ensure we can import modules from the current directory
sys.path.insert(0, os.path.dirname(__file__))
from simulation import TrafficSimulation
from config import DIRECTIONS, SCENARIOS

COLORS = {
    "bg": "#0f172a",
    "panel": "#1e293b",
    "accent": "#38bdf8",
    "road": "#334155",
    "road_line": "#94a3b8",
    "grass": "#064e3b",
    "text": "#f8fafc",
    "text_dim": "#94a3b8",
    "GREEN": "#10b981",
    "RED": "#ef4444",
    "YELLOW": "#f59e0b",
    "WALK": "#22c55e",
    "DONT_WALK": "#ef4444",
    "OFF": "#1e293b",
    "SIDEWALK": "#475569",
    "CURB": "#cbd5e1",
    "MARKING": "#ffffff",
}

# Assign distinct colors to vehicles based on their origin direction (for stats panel)
VEHICLE_COLORS = {
    "North": "#60a5fa",
    "South": "#f87171",
    "East":  "#fbbf24",
    "West":  "#c084fc",
}

# Palette for assorted random vehicle body colors
VEHICLE_PALETTE = [
    "#60a5fa", "#f87171", "#fbbf24", "#c084fc",
    "#34d399", "#fb923c", "#f472b6", "#a78bfa",
    "#38bdf8", "#e879f9", "#2dd4bf", "#facc15",
    "#818cf8", "#fb7185", "#a3e635", "#22d3ee",
]

# Physical dimensions for different vehicle types in pixels
VEHICLE_CONFIGS = {
    "car":   {"width": 14, "height": 22},
    "van":   {"width": 15, "height": 26},
    "truck": {"width": 16, "height": 32}
}

class TrafficGUI:
    CANVAS_W = 600
    CANVAS_H = 600
    CX = 300
    CY = 300
    ROAD_W = 80  # Half-width of the total road area (spanning 2 lanes)
    LANE_W = 35 

    def __init__(self, root, scenario_name="normal"):
        self.root = root
        self.scenario_name = scenario_name
        self.sim = TrafficSimulation(scenario_name)
        
        # UI & Animation State
        self.paused = False
        self.speed_multiplier = 1.0
        self.update_interval_ms = 16
        self.sim_delta_per_step = 0.16 
        
        self._setup_window()
        self._build_layout()
        self._draw_static_elements()
        self._draw_traffic_lights()
        self._draw_pedestrian_light()
        
        # Object tracking for animation
        self.vehicle_objects = {d: [] for d in DIRECTIONS}
        self.pedestrian_objects = {d: [] for d in DIRECTIONS}
        self.passing_vehicles = []
        self.arriving_vehicles = []
        self.walking_pedestrians = []
        self.arriving_pedestrians = []
        self.last_departed_idx = 0
        self.last_arrivals = {d: 0 for d in DIRECTIONS}
        self.last_ped_departed_idx = 0
        self.last_ped_arrivals = {d: 0 for d in DIRECTIONS}
        self.anim_objects = {}
        self.ped_anim_objects = {}
        self.arriving_vehicle_ids = set()
        self.arriving_pedestrian_ids = set()
        
        self._schedule_update()

    def _setup_window(self):
        scenario_label = self.sim.config.get("label", self.scenario_name)
        self.root.title(f"Traffic Simulation - {scenario_label}")
        self.root.configure(bg=COLORS["bg"])
        self.root.geometry("1000x700")
        self.root.resizable(False, False)
        
        # Load custom fonts with fallback to system defaults
        try:
            self.font_title = ("Segoe UI", 16, "bold")
            self.font_stat = ("Consolas", 11)
            self.font_label = ("Segoe UI", 10, "bold")
        except:
            self.font_title = ("Helvetica", 16, "bold")
            self.font_stat = ("Courier", 11)
            self.font_label = ("Helvetica", 10, "bold")

    def _build_layout(self):
        # Header and info bar
        header = tk.Frame(self.root, bg=COLORS["bg"], pady=15)
        header.pack(fill=tk.X)
        
        title_frame = tk.Frame(header, bg=COLORS["bg"])
        title_frame.pack(side=tk.LEFT, padx=30)
        
        tk.Label(title_frame, text="TRAFFIC FLOW SIMULATOR", 
                 fg=COLORS["accent"], bg=COLORS["bg"], font=self.font_title).pack(anchor="w")
        
        scenario_label = self.sim.config.get('label')
        scenario_desc = self.sim.config.get('description')
        tk.Label(title_frame, text=f"Scenario: {scenario_label}", 
                 fg=COLORS["text"], bg=COLORS["bg"], font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(title_frame, text=scenario_desc, 
                 fg=COLORS["text_dim"], bg=COLORS["bg"], font=("Segoe UI", 9, "italic")).pack(anchor="w")

        # Global Progress Indicator
        progress_frame = tk.Frame(header, bg=COLORS["bg"], padx=30)
        progress_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        tk.Label(progress_frame, text="TOTAL PROGRESS", fg=COLORS["accent"], 
                 bg=COLORS["bg"], font=self.font_label).pack(anchor="e")
        
        self.progress = ttk.Progressbar(progress_frame, mode="determinate", length=200)
        self.progress.pack(pady=2)
        
        self.lbl_progress = tk.Label(progress_frame, text="0%", fg=COLORS["text_dim"], 
                                     bg=COLORS["bg"], font=self.font_stat)
        self.lbl_progress.pack(anchor="e")

        # Main Viewport
        main_frame = tk.Frame(self.root, bg=COLORS["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Map Area
        self.canvas_frame = tk.Frame(main_frame, bg=COLORS["panel"], bd=2, relief=tk.RIDGE)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(
            self.canvas_frame, width=self.CANVAS_W, height=self.CANVAS_H,
            bg=COLORS["bg"], highlightthickness=0
        )
        self.canvas.pack(padx=10, pady=10)

        # Interaction Sidebar
        self.panel = tk.Frame(main_frame, bg=COLORS["panel"], width=320, padx=20, pady=20)
        self.panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(15, 0))
        self.panel.pack_propagate(False)

        # Telemetry & Statistics
        self._create_panel_section("📊 REAL-TIME STATS")
        self.stat_time = self._create_stat_row("⏱ Time Elapsed", "0s / 0s")
        self.stat_phase = self._create_stat_row("🚦 Current Phase", "Initializing...")
        self.stat_pedestrian = self._create_stat_row("🚶 Pedestrian Signal", "DONT WALK")
        self.stat_arrived = self._create_stat_row("🚗 Total Arrived", "0")
        self.stat_departed = self._create_stat_row("🏁 Total Departed", "0")
        self.stat_avg_wait = self._create_stat_row("⌛ Avg Wait", "0.0s")
        
        self._create_panel_section("🛣 LANE QUEUES")
        self.lane_stats = {}
        for d in DIRECTIONS:
            icon = "⬆" if d == "North" else "⬇" if d == "South" else "➡" if d == "East" else "⬅"
            self.lane_stats[d] = self._create_stat_row(f"{icon} {d} Lane", "RED | 0 cars", color=VEHICLE_COLORS[d])

        self._create_panel_section("🚶 PEDESTRIAN QUEUES")
        self.ped_lane_stats = {}
        for d in DIRECTIONS:
            icon = "⬆" if d == "North" else "⬇" if d == "South" else "➡" if d == "East" else "⬅"
            self.ped_lane_stats[d] = self._create_stat_row(f"{icon} {d} Crossing", "0 waiting", color=COLORS["accent"])

        self._create_panel_section("SIMULATION CONTROLS")
        self.btn_pause = tk.Button(
            self.panel, text="⏸ PAUSE", command=self._toggle_pause,
            bg=COLORS["accent"], fg=COLORS["bg"], font=self.font_label,
            relief=tk.FLAT, bd=0, pady=8, cursor="hand2",
            activebackground=COLORS["text"], activeforeground=COLORS["bg"]
        )
        self.btn_pause.pack(fill=tk.X, pady=5)
        
        # Playback speed control
        speed_container = tk.Frame(self.panel, bg=COLORS["panel"])
        speed_container.pack(fill=tk.X, pady=(0, 10))
        tk.Label(speed_container, text="Simulation Speed", fg=COLORS["text_dim"], 
                 bg=COLORS["panel"], font=("Segoe UI", 9)).pack(anchor="w")
        
        slider_row = tk.Frame(speed_container, bg=COLORS["panel"])
        slider_row.pack(fill=tk.X, pady=5)
        tk.Label(slider_row, text="🐌", bg=COLORS["panel"], font=("Segoe UI", 12)).pack(side=tk.LEFT)
        self.speed_slider = ttk.Scale(
            slider_row, from_=0.1, to=10.0, value=1.0, 
            orient=tk.HORIZONTAL, command=self._update_speed
        )
        self.speed_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        tk.Label(slider_row, text="🚀", bg=COLORS["panel"], font=("Segoe UI", 12)).pack(side=tk.LEFT)
        
        self.lbl_speed = tk.Label(speed_container, text="1.0x (Real-time)", fg=COLORS["accent"], 
                                  bg=COLORS["panel"], font=self.font_stat)
        self.lbl_speed.pack(anchor="center")

    def _create_panel_section(self, title):
        tk.Label(self.panel, text=title, fg=COLORS["accent"], 
                 bg=COLORS["panel"], font=self.font_label).pack(anchor="w", pady=(10, 2))
        tk.Frame(self.panel, bg=COLORS["road_line"], height=1).pack(fill=tk.X, pady=(0, 5))

    def _create_stat_row(self, label, value, color=None):
        row = tk.Frame(self.panel, bg=COLORS["panel"])
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text=label, fg=COLORS["text_dim"], bg=COLORS["panel"], 
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        val_lbl = tk.Label(row, text=value, fg=color or COLORS["text"], bg=COLORS["panel"], 
                           font=("Consolas", 10, "bold"), anchor="e")
        val_lbl.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        return val_lbl

    def _draw_static_elements(self):
        """Renders the intersection environment: roads, sidewalks, and markings."""
        cx, cy, rw = self.CX, self.CY, self.ROAD_W
        w, h = self.CANVAS_W, self.CANVAS_H

        def draw_tree(x, y, scale=1.0):
            trunk_w = 8 * scale
            trunk_h = 24 * scale
            crown_r = 18 * scale
            self.canvas.create_rectangle(
                x - trunk_w / 2, y, x + trunk_w / 2, y + trunk_h,
                fill="#7c4a2d", outline=""
            )
            for dx, dy, mult in [
                (0, -10 * scale, 1.05),
                (-12 * scale, -2 * scale, 0.8),
                (12 * scale, -2 * scale, 0.8),
            ]:
                r = crown_r * mult
                self.canvas.create_oval(
                    x + dx - r, y + dy - r, x + dx + r, y + dy + r,
                    fill="#15803d", outline="#0f5132", width=2
                )
        
        # Ground layer
        self.canvas.create_rectangle(0, 0, w, h, fill=COLORS["grass"], outline="")

        # Tree clusters keep the outer field from feeling empty.
        tree_positions = [
            (70, 80, 1.0), (125, 45, 0.85), (50, 170, 1.1),
            (w - 70, 80, 1.0), (w - 125, 45, 0.85), (w - 50, 170, 1.1),
            (70, h - 80, 1.0), (125, h - 45, 0.85), (50, h - 170, 1.1),
            (w - 70, h - 80, 1.0), (w - 125, h - 45, 0.85), (w - 50, h - 170, 1.1),
        ]
        for x, y, scale in tree_positions:
            draw_tree(x, y, scale)
        
        # Sidewalk logic
        sw = 15 
        self.canvas.create_rectangle(0, cy - rw - sw, w, cy - rw, fill=COLORS["SIDEWALK"], outline="")
        self.canvas.create_rectangle(0, cy + rw, w, cy + rw + sw, fill=COLORS["SIDEWALK"], outline="")
        self.canvas.create_rectangle(cx - rw - sw, 0, cx - rw, h, fill=COLORS["SIDEWALK"], outline="")
        self.canvas.create_rectangle(cx + rw, 0, cx + rw + sw, h, fill=COLORS["SIDEWALK"], outline="")

        # Corner curb pads keep the crosswalk edges visually grounded.
        curb = 18
        for dx in (-1, 1):
            for dy in (-1, 1):
                x1 = cx + dx * (rw + sw - 2)
                y1 = cy + dy * (rw + sw - 2)
                self.canvas.create_rectangle(
                    x1 - curb, y1 - curb, x1 + curb, y1 + curb,
                    fill=COLORS["SIDEWALK"], outline=""
                )

        # Road surface
        self.canvas.create_rectangle(0, cy - rw, w, cy + rw, fill=COLORS["road"], outline="")
        self.canvas.create_rectangle(cx - rw, 0, cx + rw, h, fill=COLORS["road"], outline="")
        self.canvas.create_rectangle(cx - rw, cy - rw, cx + rw, cy + rw, fill=COLORS["road"], outline="")

        # Dashed center lines
        dash = (15, 15)
        self.canvas.create_line(cx, 0, cx, cy - rw - 30, fill=COLORS["MARKING"], width=2, dash=dash)
        self.canvas.create_line(cx, cy + rw + 30, cx, h, fill=COLORS["MARKING"], width=2, dash=dash)
        self.canvas.create_line(0, cy, cx - rw - 30, cy, fill=COLORS["MARKING"], width=2, dash=dash)
        self.canvas.create_line(cx + rw + 30, cy, w, cy, fill=COLORS["MARKING"], width=2, dash=dash)
        
        # Zebra crossings
        cw_w, stripe_w, gap = 34, 5, 6
        for i in range(-rw + 4, rw - 4, stripe_w + gap):
            self.canvas.create_rectangle(cx + i, cy - rw - cw_w, cx + i + stripe_w, cy - rw - 5, fill=COLORS["MARKING"], outline="")
            self.canvas.create_rectangle(cx + i, cy + rw + 5, cx + i + stripe_w, cy + rw + cw_w, fill=COLORS["MARKING"], outline="")
            self.canvas.create_rectangle(cx - rw - cw_w, cy + i, cx - rw - 5, cy + i + stripe_w, fill=COLORS["MARKING"], outline="")
            self.canvas.create_rectangle(cx + rw + 5, cy + i, cx + rw + cw_w, cy + i + stripe_w, fill=COLORS["MARKING"], outline="")

        # Solid stop lines
        stop_w = 3
        self.canvas.create_line(cx, cy - rw - 30, cx + rw, cy - rw - 30, fill=COLORS["MARKING"], width=stop_w)
        self.canvas.create_line(cx - rw, cy + rw + 30, cx, cy + rw + 30, fill=COLORS["MARKING"], width=stop_w)
        self.canvas.create_line(cx - rw - 30, cy, cx - rw - 30, cy + rw, fill=COLORS["MARKING"], width=stop_w)
        self.canvas.create_line(cx + rw + 30, cy - rw, cx + rw + 30, cy, fill=COLORS["MARKING"], width=stop_w)

    def _draw_traffic_lights(self):
        """Constructs 'Far-Side Mast Arm' style signal heads for modern realism."""
        cx, cy, rw = self.CX, self.CY, self.ROAD_W
        self.lights = {}
        
        # Placement configurations for poles and mast arms
        configs = {
            "North": (cx + rw + 15, cy + rw + 15, cx + 40, cy + rw + 15, "v"),
            "South": (cx - rw - 15, cy - rw - 15, cx - 40, cy - rw - 15, "v"),
            "East":  (cx - rw - 15, cy + rw + 15, cx - rw - 15, cy + 40, "h"),
            "West":  (cx + rw + 15, cy - rw - 15, cx + rw + 15, cy - 40, "h")
        }
        
        for d, (bx, by, ax, ay, orient) in configs.items():
            # Support pole
            self.canvas.create_oval(bx-8, by-8, bx+8, by+8, fill="#1e293b", outline="#334155", width=2)
            self.canvas.create_oval(bx-5, by-5, bx+5, by+5, fill="#475569", outline="#1e293b", width=1)
            self.canvas.create_line(bx, by, ax, ay, fill="#475569", width=6)
            
            self.lights[d] = {"RED": [], "YELLOW": [], "GREEN": []}
            hx, hy, horient = bx, by, orient
            
            bw, bh = (16, 40) if horient == "v" else (40, 16)
            self.canvas.create_rectangle(hx-bw/2, hy-bh/2, hx+bw/2, hy+bh/2, fill="#0f172a", outline="#334155", width=2)
            
            # Order bulbs logically based on orientation
            colors = ["GREEN", "YELLOW", "RED"] if d == "South" or horient == "h" else ["RED", "YELLOW", "GREEN"]
                
            for i, color in enumerate(colors):
                lx, ly = (hx, hy - 12 + i * 12) if horient == "v" else (hx - 12 + i * 12, hy)
                bulb = self.canvas.create_oval(lx-5, ly-5, lx+5, ly+5, fill=COLORS["OFF"], outline="#1e293b", width=1)
                self.lights[d][color].append(bulb)

    def _draw_pedestrian_light(self):
        """Draws dedicated pedestrian signals at opposite corners."""
        cx, cy, rw = self.CX, self.CY, self.ROAD_W
        signal_positions = [
            (cx + rw + 58, cy - rw - 48, "v"),
            (cx - rw - 58, cy + rw + 48, "v"),
        ]

        self.pedestrian_signal = []
        for px, py, orient in signal_positions:
            head = {"DONT_WALK": [], "WALK": [], "label": None}
            self.canvas.create_line(px, py, px, py + 18, fill="#475569", width=4)
            self.canvas.create_oval(px - 6, py + 18, px + 6, py + 30, fill="#1e293b", outline="#334155", width=1)
            self.canvas.create_rectangle(px - 20, py - 30, px + 20, py + 10, fill="#0f172a", outline="#334155", width=2)
            head["DONT_WALK"].append(
                self.canvas.create_oval(px - 10, py - 24, px + 10, py - 6, fill=COLORS["DONT_WALK"], outline="#ffffff", width=2)
            )
            head["WALK"].append(
                self.canvas.create_oval(px - 10, py + 0, px + 10, py + 18, fill=COLORS["OFF"], outline="#334155", width=1)
            )
            head["label"] = self.canvas.create_text(
                px, py + 42, text="DON'T WALK", fill=COLORS["text"], font=("Segoe UI", 8, "bold")
            )
            self.pedestrian_signal.append(head)

    def _toggle_pause(self):
        self.paused = not self.paused
        self.btn_pause.config(text="▶ RESUME" if self.paused else "⏸ PAUSE",
                               bg=COLORS["YELLOW"] if self.paused else COLORS["accent"])

    def _update_speed(self, val):
        self.speed_multiplier = float(val)
        self.lbl_speed.config(text=f"{self.speed_multiplier:.1f}x")

    def _schedule_update(self):
        """The main animation ticker. Drives the simulation engine and redraws the canvas."""
        if not self.paused:
            # Scale simulation progress by current playback speed
            delta = (self.update_interval_ms / 1000.0) * self.speed_multiplier
            still_running = self.sim.step(delta)
            
            self._detect_sim_changes()
            self._move_animated_vehicles(delta)
            self._move_animated_pedestrians(delta)
            self._sync_canvas()
            self._update_panel_stats()
            
            if not still_running:
                self._handle_completion()
                return

        self.root.after(self.update_interval_ms, self._schedule_update)

    def _detect_sim_changes(self):
        """Synchronizes visual sprites with new events in the background simulation."""
        sim = self.sim
        
        # Trigger 'passing' animations for vehicles leaving the queue
        new_departed = sim.departed_vehicles[self.last_departed_idx:]
        for v in new_departed:
            self._create_passing_vehicle(v.direction, v.vehicle_id)
        self.last_departed_idx = len(sim.departed_vehicles)

        # Trigger 'arrival' animations for vehicles entering the map
        for d in DIRECTIONS:
            current_arrivals = sim.stats["arrivals_per_dir"][d]
            if current_arrivals > self.last_arrivals[d]:
                for _ in range(current_arrivals - self.last_arrivals[d]):
                    self._create_arriving_vehicle(d)
                self.last_arrivals[d] = current_arrivals

        # Trigger pedestrian arrival animations and walking crossings
        new_ped_departed = sim.departed_pedestrians[self.last_ped_departed_idx:]
        for p in new_ped_departed:
            self._create_walking_pedestrian(p.crossing, p.pedestrian_id)
        self.last_ped_departed_idx = len(sim.departed_pedestrians)

        for d in DIRECTIONS:
            current_ped_arrivals = sim.stats["pedestrian_arrivals_per_crossing"][d]
            if current_ped_arrivals > self.last_ped_arrivals[d]:
                for _ in range(current_ped_arrivals - self.last_ped_arrivals[d]):
                    self._create_arriving_pedestrian(d)
                self.last_ped_arrivals[d] = current_ped_arrivals

    def _update_panel_stats(self):
        """Refreshes the sidebar with current data points."""
        sim = self.sim
        now, total = sim.env.now, sim.config["simulation_time"]
        self.stat_time.config(text=f"{int(now)}s / {total}s")
        
        ped_state = sim.pedestrian_light.state
        self.stat_pedestrian.config(text=ped_state.replace("_", " "))

        if ped_state == "WALK":
            phase = "PEDESTRIAN CROSSING 🚶"
        else:
            ns_state, ew_state = sim.lights["North"].state, sim.lights["East"].state
            if ns_state == "GREEN":
                phase = "PHASE A (N-S) 🟢"
            elif ew_state == "GREEN":
                phase = "PHASE B (E-W) 🟢"
            else:
                phase = "TRANSITION ⚠"
        self.stat_phase.config(text=phase)
        
        self.stat_arrived.config(text=f"{sim.stats['total_arrived']} vehicles")
        self.stat_departed.config(text=f"{sim.stats['total_departed']} vehicles")
        
        res = sim.get_results()
        self.stat_avg_wait.config(text=f"{res['avg_wait_time']:.1f}s")
        
        pct = min(int(now / total * 100), 100)
        self.progress["value"] = pct
        self.lbl_progress.config(text=f"{pct}%")

        for d in DIRECTIONS:
            state = sim.lights[d].state
            q_len = len(sim.queues[d])
            self.lane_stats[d].config(text=f"{state} | {q_len} {'car' if q_len == 1 else 'cars'}", fg=COLORS[state])
            ped_q_len = len(sim.pedestrian_queues[d])
            self.ped_lane_stats[d].config(text=f"{ped_q_len} waiting", fg=COLORS["accent"])

    def _get_stop_distance(self, direction, q_idx):
        """Determines exactly where a vehicle should stop in the queue to avoid overlapping."""
        queue = self.sim.queues[direction]
        if q_idx >= len(queue): return 1000

        vehicle = queue[q_idx]
        return self._get_vehicle_stop_offset(direction, vehicle)

    def _get_vehicle_stop_offset(self, direction, vehicle):
        """Returns the center-point distance from the stop line for a queued vehicle."""
        queue_slot = getattr(vehicle, 'queue_slot', 0)
        stop_line_dist = 115
        slot_gap = 42
        my_height = VEHICLE_CONFIGS.get(getattr(vehicle, 'v_type', 'car'), VEHICLE_CONFIGS['car'])["height"]
        return stop_line_dist + my_height / 2 + queue_slot * slot_gap

    def _move_animated_vehicles(self, delta):
        """Applies frame-by-frame coordinate shifts to active vehicle sprites."""
        current_pos = {}
        speed = 120 # Pixels per sim-second
        
        # Handle vehicles exiting the intersection
        remaining_passing = []
        for v in self.passing_vehicles:
            speed = v.get('speed', 120)
            v['x'] += v['dx'] * speed * delta
            v['y'] += v['dy'] * speed * delta
            if -50 < v['x'] < self.CANVAS_W + 50 and -50 < v['y'] < self.CANVAS_H + 50:
                remaining_passing.append(v)
                vid = int(v['id'].split('_')[1])
                current_pos[vid] = v
        self.passing_vehicles = remaining_passing

        # Handle vehicles approaching the intersection
        remaining_arriving = []
        cx, cy = self.CX, self.CY
        for v in self.arriving_vehicles:
            d = v['dir']
            vobj = v['vehicle_obj']
            speed = v.get('speed', 120)
            
            # Check if this vehicle is still in the queue
            try:
                q_idx = self.sim.queues[d].index(vobj)
            except ValueError:
                # Vehicle departed — will be handled by passing sprite
                self.arriving_vehicle_ids.discard(vobj.vehicle_id)
                continue

            my_lane = getattr(vobj, 'lane', 0)
            my_length = VEHICLE_CONFIGS[v['type']]["height"]
            
            ahead_vid = None
            for j in range(q_idx - 1, -1, -1):
                if getattr(self.sim.queues[d][j], 'lane', 0) == my_lane:
                    ahead_vid = self.sim.queues[d][j].vehicle_id
                    break
            
            if ahead_vid is None:
                for pass_v in reversed(self.passing_vehicles):
                    if pass_v['dir'] == d and pass_v['lane'] == my_lane:
                        ahead_vid = int(pass_v['id'].split('_')[1])
                        break

            ahead_limit = None
            if ahead_vid is not None and ahead_vid in current_pos:
                ahead_v = current_pos[ahead_vid]
                ahead_length = VEHICLE_CONFIGS[ahead_v['type']]["height"]
                gap_size = 10 + ahead_length / 2 + my_length / 2
                if d == "North": ahead_limit = ahead_v['y'] - gap_size
                elif d == "South": ahead_limit = ahead_v['y'] + gap_size
                elif d == "East": ahead_limit = ahead_v['x'] + gap_size
                elif d == "West": ahead_limit = ahead_v['x'] - gap_size

            stop_dist = self._get_stop_distance(d, q_idx)
            v['x'] += v['dx'] * speed * delta
            v['y'] += v['dy'] * speed * delta
            
            reached = False
            if d == "North" and v['y'] >= cy - stop_dist: reached = True
            elif d == "South" and v['y'] <= cy + stop_dist: reached = True
            elif d == "East" and v['x'] <= cx + stop_dist: reached = True
            elif d == "West" and v['x'] >= cx - stop_dist: reached = True
                
            if not reached:
                remaining_arriving.append(v)
            else:
                # Vehicle reached stop position — remove from tracking so it
                # becomes visible as a static queued sprite in _sync_canvas
                self.arriving_vehicle_ids.discard(vobj.vehicle_id)
        self.arriving_vehicles = remaining_arriving

    def _get_pedestrian_wait_position(self, crossing, index):
        cx, cy, rw = self.CX, self.CY, self.ROAD_W
        spacing = 16
        curb_offset = 62

        # Queue pedestrians on the grass corners, away from the road and crossing lane.
        if crossing == "North":
            return cx - 92 - index * spacing, cy - rw - curb_offset - index * 4
        if crossing == "South":
            return cx + 92 + index * spacing, cy + rw + curb_offset + index * 4
        if crossing == "East":
            return cx + rw + curb_offset + index * 4, cy - 92 - index * spacing
        return cx - rw - curb_offset - index * 4, cy + 92 + index * spacing

    def _get_pedestrian_path(self, crossing):
        cx, cy, rw = self.CX, self.CY, self.ROAD_W
        if crossing == "North":
            return (cx - rw + 10, cy - rw - 20), (cx + rw - 10, cy - rw - 20), "h"
        if crossing == "South":
            return (cx + rw - 10, cy + rw + 20), (cx - rw + 10, cy + rw + 20), "h"
        if crossing == "East":
            return (cx + rw + 20, cy - rw + 10), (cx + rw + 20, cy + rw - 10), "v"
        return (cx - rw - 20, cy + rw - 10), (cx - rw - 20, cy - rw + 10), "v"

    def _get_vehicle_stop_position(self, direction, vehicle):
        cx, cy = self.CX, self.CY
        lane_id = getattr(vehicle, 'lane', 0)
        lane_offset = 20 if lane_id == 0 else 55
        stop_offset = self._get_vehicle_stop_offset(direction, vehicle)

        if direction == "North":
            return cx + lane_offset, cy - stop_offset, "v"
        if direction == "South":
            return cx - lane_offset, cy + stop_offset, "v"
        if direction == "East":
            return cx + stop_offset, cy - lane_offset, "h"
        return cx - stop_offset, cy + lane_offset, "h"

    def _move_animated_pedestrians(self, delta):
        speed = 70

        remaining_arriving = []
        for p in self.arriving_pedestrians:
            p["x"] += p["dx"] * speed * delta
            p["y"] += p["dy"] * speed * delta

            reached = False
            if p["orient"] == "v":
                if (p["dy"] > 0 and p["y"] >= p["target_y"]) or (p["dy"] < 0 and p["y"] <= p["target_y"]):
                    reached = True
            else:
                if (p["dx"] > 0 and p["x"] >= p["target_x"]) or (p["dx"] < 0 and p["x"] <= p["target_x"]):
                    reached = True

            if reached:
                self.arriving_pedestrian_ids.discard(p["pedestrian_obj"].pedestrian_id)
            else:
                remaining_arriving.append(p)
        self.arriving_pedestrians = remaining_arriving

        remaining_walking = []
        for p in self.walking_pedestrians:
            p["x"] += p["dx"] * speed * delta
            p["y"] += p["dy"] * speed * delta

            if p["orient"] == "v":
                done = (p["dy"] > 0 and p["y"] > p["target_y"] + 18) or (p["dy"] < 0 and p["y"] < p["target_y"] - 18)
            else:
                done = (p["dx"] > 0 and p["x"] > p["target_x"] + 18) or (p["dx"] < 0 and p["x"] < p["target_x"] - 18)

            if done:
                if p["id"] in self.ped_anim_objects:
                    for item in self.ped_anim_objects[p["id"]]:
                        self.canvas.delete(item)
                    del self.ped_anim_objects[p["id"]]
            else:
                remaining_walking.append(p)
        self.walking_pedestrians = remaining_walking

    def _create_arriving_vehicle(self, direction):
        """Spawns a new vehicle sprite at the map edge."""
        cx, cy = self.CX, self.CY
        queue = self.sim.queues[direction]
        
        # Find the newest vehicle that does NOT already have a sprite
        vehicle_obj = None
        for v_obj in reversed(queue):
            if v_obj.vehicle_id not in self.arriving_vehicle_ids:
                vehicle_obj = v_obj
                break
        if vehicle_obj is None:
            return
            
        if not hasattr(vehicle_obj, 'v_type'):
            vehicle_obj.v_type = random.choice(["car", "car", "car", "van", "truck"])
        if not hasattr(vehicle_obj, 'color'):
            vehicle_obj.color = random.choice(VEHICLE_PALETTE)
        
        self.arriving_vehicle_ids.add(vehicle_obj.vehicle_id)
        anim_id = f"arr_{vehicle_obj.vehicle_id}"
        
        # Use the permanent lane assigned in the simulation
        lane_id = getattr(vehicle_obj, 'lane', 0)
            
        v = {
            'id': anim_id, 'vehicle_obj': vehicle_obj, 'dir': direction,
            'type': vehicle_obj.v_type, 'color': vehicle_obj.color,
            'x': 0, 'y': 0, 'dx': 0, 'dy': 0, 'orient': 'v', 'lane': lane_id,
            'speed': random.uniform(80, 160)
        }
        
        # Lane offsets: 2 lanes per direction, each 40px wide within the 80px half-road
        l1, l2 = 20, 55
        off = l1 if lane_id == 0 else l2
        
        margin = 30
        if direction == "North":
            v['x'], v['y'], v['dy'], v['orient'] = cx + off, -margin, 1, 'v'
        elif direction == "South":
            v['x'], v['y'], v['dy'], v['orient'] = cx - off, self.CANVAS_H + margin, -1, 'v'
        elif direction == "East":
            v['x'], v['y'], v['dx'], v['orient'] = self.CANVAS_W + margin, cy - off, -1, 'h'
        elif direction == "West":
            v['x'], v['y'], v['dx'], v['orient'] = -margin, cy + off, 1, 'h'
            
        self.arriving_vehicles.append(v)

    def _create_arriving_pedestrian(self, crossing):
        queue = self.sim.pedestrian_queues[crossing]

        pedestrian_obj = None
        for p_obj in reversed(queue):
            if p_obj.pedestrian_id not in self.arriving_pedestrian_ids:
                pedestrian_obj = p_obj
                break
        if pedestrian_obj is None:
            return

        if not hasattr(pedestrian_obj, 'color'):
            pedestrian_obj.color = random.choice(["#f8fafc", "#cbd5e1", "#60a5fa", "#fbbf24", "#f472b6"])

        self.arriving_pedestrian_ids.add(pedestrian_obj.pedestrian_id)
        wait_x, wait_y = self._get_pedestrian_wait_position(crossing, queue.index(pedestrian_obj))
        if crossing == "North":
            start_x, start_y = self.CX, self.CY - self.ROAD_W - 48
            target_x, target_y, dx, dy, orient = wait_x, wait_y, 1, 0, "h"
        elif crossing == "South":
            start_x, start_y = self.CX, self.CY + self.ROAD_W + 48
            target_x, target_y, dx, dy, orient = wait_x, wait_y, -1, 0, "h"
        elif crossing == "East":
            start_x, start_y = self.CANVAS_W + 48, self.CY
            target_x, target_y, dx, dy, orient = wait_x, wait_y, 0, 1, "v"
        else:
            start_x, start_y = -48, self.CY
            target_x, target_y, dx, dy, orient = wait_x, wait_y, 0, -1, "v"

        self.arriving_pedestrians.append({
            'id': f"ped_arr_{pedestrian_obj.pedestrian_id}",
            'pedestrian_obj': pedestrian_obj,
            'crossing': crossing,
            'x': start_x,
            'y': start_y,
            'dx': dx,
            'dy': dy,
            'target_x': target_x,
            'target_y': target_y,
            'orient': orient,
            'color': pedestrian_obj.color,
        })

    def _create_walking_pedestrian(self, crossing, pedestrian_id):
        found_arriving = next((p for p in self.arriving_pedestrians if p['pedestrian_obj'].pedestrian_id == pedestrian_id), None)
        start_pos, target_pos, orient = self._get_pedestrian_path(crossing)
        if found_arriving:
            color = found_arriving['color']
            self.arriving_pedestrians.remove(found_arriving)
            self.arriving_pedestrian_ids.discard(pedestrian_id)
            if found_arriving['id'] in self.ped_anim_objects:
                for item in self.ped_anim_objects[found_arriving['id']]:
                    self.canvas.delete(item)
                del self.ped_anim_objects[found_arriving['id']]
        else:
            color = random.choice(["#f8fafc", "#cbd5e1", "#60a5fa", "#fbbf24", "#f472b6"])

        start_x, start_y = start_pos

        if crossing == "North":
            dx, dy = 1, 0
        elif crossing == "South":
            dx, dy = -1, 0
        elif crossing == "East":
            dx, dy = 0, 1
        else:
            dx, dy = 0, -1

        self.walking_pedestrians.append({
            'id': f"ped_pass_{pedestrian_id}",
            'crossing': crossing,
            'x': start_x,
            'y': start_y,
            'dx': dx,
            'dy': dy,
            'target_x': target_pos[0],
            'target_y': target_pos[1],
            'orient': orient,
            'color': color,
        })

    def _create_passing_vehicle(self, direction, vehicle_id):
        """Converts an 'arriving' sprite into a 'passing' sprite that crosses the intersection."""
        cx, cy, rw = self.CX, self.CY, self.ROAD_W
        start_x, start_y, v_type, lane_id, v_color = 0, 0, "car", 0, random.choice(VEHICLE_PALETTE)
        existing_sprite_items = None
        pass_id = f"pass_{vehicle_id}"
        
        # Match by vehicle_id for accurate sprite transition
        found_arriving = next(
            (v for v in self.arriving_vehicles 
             if v['vehicle_obj'].vehicle_id == vehicle_id), None)
        v_speed = random.uniform(80, 160)
        if found_arriving:
            v_type, lane_id = found_arriving['type'], found_arriving['lane']
            v_color = found_arriving['color']
            v_speed = found_arriving.get('speed', v_speed)
            self.arriving_vehicles.remove(found_arriving)
            self.arriving_vehicle_ids.discard(vehicle_id)
            existing_sprite_items = self.anim_objects.pop(found_arriving['id'], None)
            departed_v = next(
                (v for v in self.sim.departed_vehicles 
                 if v.vehicle_id == vehicle_id), None)
            if departed_v is not None:
                start_x, start_y, _ = self._get_vehicle_stop_position(direction, departed_v)
            else:
                start_x, start_y = found_arriving['x'], found_arriving['y']
        else:
            # No arriving sprite — vehicle was either a static queued sprite
            # or was never visible. Look up the departed vehicle's attributes.
            departed_v = next(
                (v for v in self.sim.departed_vehicles 
                 if v.vehicle_id == vehicle_id), None)
            
            if departed_v and hasattr(departed_v, 'color'):
                # Vehicle was visible as a queued sprite — start from stop line
                lane_id = getattr(departed_v, 'lane', 0)
                v_type = getattr(departed_v, 'v_type', 'car')
                v_color = getattr(departed_v, 'color', random.choice(VEHICLE_PALETTE))

                start_x, start_y, _ = self._get_vehicle_stop_position(direction, departed_v)
                
                # Clean up the old queued sprite if it exists
                old_q_id = f"q_{direction}_{vehicle_id}"
                existing_sprite_items = self.anim_objects.pop(old_q_id, None)
            else:
                # Vehicle was truly never visible — skip entirely
                return

        v = {
            'id': pass_id, 'dir': direction, 'type': v_type,
            'color': v_color, 'x': start_x, 'y': start_y,
            'dx': 0, 'dy': 0, 'orient': 'v', 'lane': lane_id,
            'speed': v_speed
        }
        
        if direction == "North": v['dy'], v['orient'] = 1, 'v'
        elif direction == "South": v['dy'], v['orient'] = -1, 'v'
        elif direction == "East": v['dx'], v['orient'] = -1, 'h'
        elif direction == "West": v['dx'], v['orient'] = 1, 'h'

        if existing_sprite_items is not None:
            self.anim_objects[pass_id] = existing_sprite_items
            
        self.passing_vehicles.append(v)

    def _update_or_create_pedestrian(self, vid, x, y, orient, color, moving=False):
        body_color = color if moving else COLORS["CURB"]
        head_color = color
        if vid not in self.ped_anim_objects:
            head = self.canvas.create_oval(x-4, y-9, x+4, y-1, fill=head_color, outline="#0f172a", width=1)
            torso = self.canvas.create_line(x, y-1, x, y+8, fill=body_color, width=2)
            arm = self.canvas.create_line(x-4, y+2, x+4, y+2, fill=body_color, width=2)
            leg1 = self.canvas.create_line(x, y+8, x-4, y+14, fill=body_color, width=2)
            leg2 = self.canvas.create_line(x, y+8, x+4, y+14, fill=body_color, width=2)
            self.ped_anim_objects[vid] = [head, torso, arm, leg1, leg2]
            for item in self.ped_anim_objects[vid]:
                self.canvas.tag_raise(item)
        else:
            items = self.ped_anim_objects[vid]
            self.canvas.coords(items[0], x-4, y-9, x+4, y-1)
            self.canvas.coords(items[1], x, y-1, x, y+8)
            self.canvas.coords(items[2], x-4, y+2, x+4, y+2)
            self.canvas.coords(items[3], x, y+8, x-4, y+14)
            self.canvas.coords(items[4], x, y+8, x+4, y+14)
            self.canvas.itemconfig(items[0], fill=head_color)
            self.canvas.itemconfig(items[1], fill=body_color)
            self.canvas.itemconfig(items[2], fill=body_color)
            self.canvas.itemconfig(items[3], fill=body_color)
            self.canvas.itemconfig(items[4], fill=body_color)
            for item in items:
                self.canvas.tag_raise(item)

    def _sync_canvas(self):
        """High-level redraw: maps logical state to visual canvas objects."""
        active_ids = set()
        
        # Handle traffic light visual states (bulbs & glow)
        for d in DIRECTIONS:
            state = self.sim.lights[d].state
            for color, bulb_ids in self.lights[d].items():
                for b_id in bulb_ids:
                    self.canvas.itemconfig(b_id, fill=COLORS["OFF"], outline="#1e293b", width=1)
            if state in self.lights[d]:
                for b_id in self.lights[d][state]:
                    self.canvas.itemconfig(b_id, fill=COLORS[state], outline="#fff", width=2)
                    self.canvas.tag_raise(b_id)

        ped_state = self.sim.pedestrian_light.state
        for signal in self.pedestrian_signal:
            for item_id in signal["DONT_WALK"] + signal["WALK"]:
                self.canvas.itemconfig(item_id, fill=COLORS["OFF"], outline="#334155", width=1)
            if ped_state == "WALK":
                self.canvas.itemconfig(signal["WALK"][0], fill=COLORS["WALK"], outline="#fff", width=2)
                self.canvas.itemconfig(signal["label"], text="WALK")
            else:
                self.canvas.itemconfig(signal["DONT_WALK"][0], fill=COLORS["DONT_WALK"], outline="#fff", width=2)
                self.canvas.itemconfig(signal["label"], text="DON'T WALK")
        
        cx, cy, lane_offset = self.CX, self.CY, self.ROAD_W // 2
        
        # Render static queued vehicles (those that have arrived at their stop position)
        for d in DIRECTIONS:
            queue = self.sim.queues[d]
            for i in range(len(queue)):
                if i >= 20: break  # Performance cap
                vobj = queue[i]
                # Skip vehicles that still have an arriving animation
                if vobj.vehicle_id in self.arriving_vehicle_ids:
                    continue
                
                # Ensure vehicle has visual attributes
                if not hasattr(vobj, 'v_type'):
                    vobj.v_type = random.choice(["car", "car", "car", "van", "truck"])
                if not hasattr(vobj, 'color'):
                    vobj.color = random.choice(VEHICLE_PALETTE)
                    
                v_id = f"q_{d}_{vobj.vehicle_id}"
                active_ids.add(v_id)
                x, y, orient = self._get_vehicle_stop_position(d, vobj)
                
                self._update_or_create_car(v_id, x, y, orient, vobj.color, vobj.v_type)

        # Render static queued pedestrians
        for d in DIRECTIONS:
            queue = self.sim.pedestrian_queues[d]
            for i in range(len(queue)):
                if i >= 14:
                    break
                pobj = queue[i]
                if pobj.pedestrian_id in self.arriving_pedestrian_ids:
                    continue

                if not hasattr(pobj, 'color'):
                    pobj.color = random.choice(["#f8fafc", "#cbd5e1", "#60a5fa", "#fbbf24", "#f472b6"])

                p_id = f"p_{d}_{pobj.pedestrian_id}"
                active_ids.add(p_id)
                x, y = self._get_pedestrian_wait_position(d, i)
                self._update_or_create_pedestrian(p_id, x, y, "v" if d in ("North", "South") else "h", pobj.color, moving=False)

        # Render moving vehicles
        for v_list in [self.passing_vehicles, self.arriving_vehicles]:
            for v in v_list:
                active_ids.add(v['id'])
                self._update_or_create_car(v['id'], v['x'], v['y'], v['orient'], v['color'], v['type'])

        # Render moving pedestrians
        for p in [self.arriving_pedestrians, self.walking_pedestrians]:
            for ped in p:
                active_ids.add(ped['id'])
                self._update_or_create_pedestrian(ped['id'], ped['x'], ped['y'], ped['orient'], ped['color'], moving=True)

        # Garbage collect sprites for vehicles that left the map
        for vid in list(self.anim_objects.keys()):
            if vid not in active_ids:
                for item in self.anim_objects[vid]:
                    self.canvas.delete(item)
                del self.anim_objects[vid]

        for vid in list(self.ped_anim_objects.keys()):
            if vid not in active_ids:
                for item in self.ped_anim_objects[vid]:
                    self.canvas.delete(item)
                del self.ped_anim_objects[vid]

    def _update_or_create_car(self, vid, x, y, orient, color, v_type="car"):
        """Draws/moves a vehicle sprite including details like headlights and windshields."""
        cfg = VEHICLE_CONFIGS.get(v_type, VEHICLE_CONFIGS["car"])
        w, h = (cfg["width"], cfg["height"]) if orient == "v" else (cfg["height"], cfg["width"])
        
        if vid not in self.anim_objects:
            body = self.canvas.create_rectangle(x-w/2, y-h/2, x+w/2, y+h/2, fill=color, outline="#000", width=1)
            items = [body]
            
            if orient == "v":
                # Windshield & Roof
                items.append(self.canvas.create_rectangle(x-w*0.35, y-h*0.2, x+w*0.35, y+h*0.1, fill="#1e293b", outline=""))
                # Headlights (front)
                items.append(self.canvas.create_oval(x-w*0.4, y-h*0.45, x-w*0.1, y-h*0.35, fill="#fff", outline=""))
                items.append(self.canvas.create_oval(x+w*0.1, y-h*0.45, x+w*0.4, y-h*0.35, fill="#fff", outline=""))
                # Brake lights (back)
                items.append(self.canvas.create_rectangle(x-w*0.4, y+h*0.4, x-w*0.2, y+h*0.45, fill="#ef4444", outline=""))
                items.append(self.canvas.create_rectangle(x+w*0.2, y+h*0.4, x+w*0.4, y+h*0.45, fill="#ef4444", outline=""))
            else:
                items.append(self.canvas.create_rectangle(x-w*0.2, y-h*0.35, x+w*0.1, y+h*0.35, fill="#1e293b", outline=""))
                items.append(self.canvas.create_oval(x+w*0.35, y-h*0.4, x+w*0.45, y-h*0.1, fill="#fff", outline=""))
                items.append(self.canvas.create_oval(x+w*0.35, y+h*0.1, x+w*0.45, y+h*0.4, fill="#fff", outline=""))
                items.append(self.canvas.create_rectangle(x-w*0.45, y-h*0.4, x-w*0.4, y-h*0.2, fill="#ef4444", outline=""))
                items.append(self.canvas.create_rectangle(x-w*0.45, y+h*0.2, x-w*0.4, y+h*0.4, fill="#ef4444", outline=""))
            
            self.anim_objects[vid] = items
            for item in items: self.canvas.tag_raise(item)
        else:
            # Shift existing items to new coords
            items = self.anim_objects[vid]
            self.canvas.coords(items[0], x-w/2, y-h/2, x+w/2, y+h/2)
            if orient == "v":
                self.canvas.coords(items[1], x-w*0.35, y-h*0.2, x+w*0.35, y+h*0.1)
                self.canvas.coords(items[2], x-w*0.4, y-h*0.45, x-w*0.1, y-h*0.35)
                self.canvas.coords(items[3], x+w*0.1, y-h*0.45, x+w*0.4, y-h*0.35)
                self.canvas.coords(items[4], x-w*0.4, y+h*0.4, x-w*0.2, y+h*0.45)
                self.canvas.coords(items[5], x+w*0.2, y+h*0.4, x+w*0.4, y+h*0.45)
            else:
                self.canvas.coords(items[1], x-w*0.2, y-h*0.35, x+w*0.1, y+h*0.35)
                self.canvas.coords(items[2], x+w*0.35, y-h*0.4, x+w*0.45, y-h*0.1)
                self.canvas.coords(items[3], x+w*0.35, y+h*0.1, x+w*0.45, y+h*0.4)
                self.canvas.coords(items[4], x-w*0.45, y-h*0.4, x-w*0.4, y-h*0.2)
                self.canvas.coords(items[5], x-w*0.45, y+h*0.2, x-w*0.4, y+h*0.4)
            for item in items: self.canvas.tag_raise(item)

    def _handle_completion(self):
        self.paused = True
        self.btn_pause.config(text="FINISHED", state=tk.DISABLED, bg="#475569")
        messagebox.showinfo("Simulation Complete", 
                               f"The simulation has finished.\nTotal Vehicles: {self.sim.stats['total_arrived']}\nAvg Wait Time: {self.sim.get_results()['avg_wait_time']:.2f}s")

def launch_gui(scenario="normal"):
    root = tk.Tk()
    app = TrafficGUI(root, scenario)
    
    root.update_idletasks()
    width, height = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry('{}x{}+{}+{}'.format(width, height, x, y))
    
    root.mainloop()

if __name__ == "__main__":
    scenario = sys.argv[1] if len(sys.argv) > 1 else "normal"
    if scenario not in SCENARIOS:
        print(f"Unknown scenario. Using 'normal'.")
        scenario = "normal"
    launch_gui(scenario)