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
    "OFF": "#1e293b",
    "SIDEWALK": "#475569",
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
        
        # Object tracking for animation
        self.vehicle_objects = {d: [] for d in DIRECTIONS}
        self.passing_vehicles = []
        self.arriving_vehicles = []
        self.last_departed_idx = 0
        self.last_arrivals = {d: 0 for d in DIRECTIONS}
        self.anim_objects = {}
        self.arriving_vehicle_ids = set()
        
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
        self.stat_arrived = self._create_stat_row("🚗 Total Arrived", "0")
        self.stat_departed = self._create_stat_row("🏁 Total Departed", "0")
        self.stat_avg_wait = self._create_stat_row("⌛ Avg Wait", "0.0s")
        
        self._create_panel_section("🛣 LANE QUEUES")
        self.lane_stats = {}
        for d in DIRECTIONS:
            icon = "⬆" if d == "North" else "⬇" if d == "South" else "➡" if d == "East" else "⬅"
            self.lane_stats[d] = self._create_stat_row(f"{icon} {d} Lane", "RED | 0 cars", color=VEHICLE_COLORS[d])

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
        
        # Ground layer
        self.canvas.create_rectangle(0, 0, w, h, fill=COLORS["grass"], outline="")
        
        # Sidewalk logic
        sw = 15 
        self.canvas.create_rectangle(0, cy - rw - sw, w, cy - rw, fill=COLORS["SIDEWALK"], outline="")
        self.canvas.create_rectangle(0, cy + rw, w, cy + rw + sw, fill=COLORS["SIDEWALK"], outline="")
        self.canvas.create_rectangle(cx - rw - sw, 0, cx - rw, h, fill=COLORS["SIDEWALK"], outline="")
        self.canvas.create_rectangle(cx + rw, 0, cx + rw + sw, h, fill=COLORS["SIDEWALK"], outline="")

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
        cw_w, stripe_w, gap = 25, 4, 6
        for i in range(-rw + 5, rw - 5, stripe_w + gap):
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

    def _update_panel_stats(self):
        """Refreshes the sidebar with current data points."""
        sim = self.sim
        now, total = sim.env.now, sim.config["simulation_time"]
        self.stat_time.config(text=f"{int(now)}s / {total}s")
        
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

    def _get_stop_distance(self, direction, q_idx):
        """Determines exactly where a vehicle should stop in the queue to avoid overlapping."""
        queue = self.sim.queues[direction]
        if q_idx >= len(queue): return 1000
        
        vehicle = queue[q_idx]
        my_lane = getattr(vehicle, 'lane', 0)
        my_height = VEHICLE_CONFIGS[getattr(vehicle, 'v_type', 'car')]["height"]
        
        stop_line_dist = 115
        gap = 10
        
        # Collect heights of vehicles AHEAD in the SAME lane
        ahead_heights = []
        for j in range(q_idx):
            v = queue[j]
            if getattr(v, 'lane', 0) == my_lane:
                vt = getattr(v, 'v_type', 'car')
                ahead_heights.append(VEHICLE_CONFIGS[vt]["height"])
        
        if not ahead_heights:
            # First car in this lane
            return stop_line_dist + my_height / 2
        
        # Stack: first car, then each subsequent car with gap
        dist = stop_line_dist + ahead_heights[0] / 2
        for k in range(1, len(ahead_heights)):
            dist += ahead_heights[k - 1] / 2 + gap + ahead_heights[k] / 2
        dist += ahead_heights[-1] / 2 + gap + my_height / 2
        
        return dist

    def _move_animated_vehicles(self, delta):
        """Applies frame-by-frame coordinate shifts to active vehicle sprites."""
        current_pos = {}
        
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

        for v in self.arriving_vehicles:
            vid = v['vehicle_obj'].vehicle_id
            current_pos[vid] = v

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
            
            # Move towards target
            if d == "North":
                target_y = cy - stop_dist
                if ahead_limit is not None: target_y = min(target_y, ahead_limit)
                if v['y'] < target_y:
                    v['y'] += speed * delta
                    if v['y'] > target_y: v['y'] = target_y
            elif d == "South":
                target_y = cy + stop_dist
                if ahead_limit is not None: target_y = max(target_y, ahead_limit)
                if v['y'] > target_y:
                    v['y'] -= speed * delta
                    if v['y'] < target_y: v['y'] = target_y
            elif d == "East":
                target_x = cx + stop_dist
                if ahead_limit is not None: target_x = max(target_x, ahead_limit)
                if v['x'] > target_x:
                    v['x'] -= speed * delta
                    if v['x'] < target_x: v['x'] = target_x
            elif d == "West":
                target_x = cx - stop_dist
                if ahead_limit is not None: target_x = min(target_x, ahead_limit)
                if v['x'] < target_x:
                    v['x'] += speed * delta
                    if v['x'] > target_x: v['x'] = target_x
                
            remaining_arriving.append(v)
            
        self.arriving_vehicles = remaining_arriving

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

    def _create_passing_vehicle(self, direction, vehicle_id):
        """Converts an 'arriving' sprite into a 'passing' sprite that crosses the intersection."""
        cx, cy, rw = self.CX, self.CY, self.ROAD_W
        start_x, start_y, v_type, lane_id, v_color = 0, 0, "car", 0, random.choice(VEHICLE_PALETTE)
        
        # Match by vehicle_id for accurate sprite transition
        found_arriving = next(
            (v for v in self.arriving_vehicles 
             if v['vehicle_obj'].vehicle_id == vehicle_id), None)
        v_speed = random.uniform(80, 160)
        if found_arriving:
            start_x, start_y = found_arriving['x'], found_arriving['y']
            v_type, lane_id = found_arriving['type'], found_arriving['lane']
            v_color = found_arriving['color']
            v_speed = found_arriving.get('speed', v_speed)
            self.arriving_vehicles.remove(found_arriving)
            self.arriving_vehicle_ids.discard(vehicle_id)
            if found_arriving['id'] in self.anim_objects:
                for item in self.anim_objects[found_arriving['id']]:
                    self.canvas.delete(item)
                del self.anim_objects[found_arriving['id']]
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
                
                l1, l2 = 20, 55
                off = l1 if lane_id == 0 else l2
                stop_dist = 115  # Match the stop_line_dist from _get_stop_distance
                if direction == "North": start_x, start_y = cx + off, cy - stop_dist
                elif direction == "South": start_x, start_y = cx - off, cy + stop_dist
                elif direction == "East": start_x, start_y = cx + stop_dist, cy - off
                elif direction == "West": start_x, start_y = cx - stop_dist, cy + off
                
                # Clean up the old queued sprite if it exists
                old_q_id = f"q_{direction}_{vehicle_id}"
                if old_q_id in self.anim_objects:
                    for item in self.anim_objects[old_q_id]:
                        self.canvas.delete(item)
                    del self.anim_objects[old_q_id]
            else:
                # Vehicle was truly never visible — skip entirely
                return

        v = {
            'id': f"pass_{vehicle_id}", 'dir': direction, 'type': v_type,
            'color': v_color, 'x': start_x, 'y': start_y,
            'dx': 0, 'dy': 0, 'orient': 'v', 'lane': lane_id,
            'speed': v_speed
        }
        
        if direction == "North": v['dy'], v['orient'] = 1, 'v'
        elif direction == "South": v['dy'], v['orient'] = -1, 'v'
        elif direction == "East": v['dx'], v['orient'] = -1, 'h'
        elif direction == "West": v['dx'], v['orient'] = 1, 'h'
            
        self.passing_vehicles.append(v)

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
                dist = self._get_stop_distance(d, i)
                
                # Use permanent lane from vehicle object
                lane_id = getattr(vobj, 'lane', 0)
                l1, l2 = 20, 55
                off = l1 if lane_id == 0 else l2
                
                if d == "North": x, y, orient = cx + off, cy - dist, "v"
                elif d == "South": x, y, orient = cx - off, cy + dist, "v"
                elif d == "East": x, y, orient = cx + dist, cy - off, "h"
                else: x, y, orient = cx - dist, cy + off, "h"
                
                self._update_or_create_car(v_id, x, y, orient, vobj.color, vobj.v_type)

        # Render moving vehicles
        for v_list in [self.passing_vehicles, self.arriving_vehicles]:
            for v in v_list:
                active_ids.add(v['id'])
                self._update_or_create_car(v['id'], v['x'], v['y'], v['orient'], v['color'], v['type'])

        # Garbage collect sprites for vehicles that left the map
        for vid in list(self.anim_objects.keys()):
            if vid not in active_ids:
                for item in self.anim_objects[vid]:
                    self.canvas.delete(item)
                del self.anim_objects[vid]

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