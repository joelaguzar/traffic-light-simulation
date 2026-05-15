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

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Ensure we can import modules from the current directory
sys.path.insert(0, os.path.dirname(__file__))
from simulation import TrafficSimulation
from config import DIRECTIONS, SCENARIOS

COLORS = {
    "bg": "#0f172a",
    "panel": "#1e293b",
    "accent": "#38bdf8",
    "road": "#6b7280",
    "road_line": "#94a3b8",
    "grass": "#5a9e4a",
    "text": "#f8fafc",
    "text_dim": "#94a3b8",
    "GREEN": "#10b981",
    "RED": "#ef4444",
    "YELLOW": "#f59e0b",
    "OFF": "#1e293b",
    "SIDEWALK": "#c8b89a",
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

# Physical dimensions for different vehicle types in pixels.
# Width = across the lane (~40px lane, so ~26-28px leaves good margins).
# Height = along the lane (maintained near the original 2:1 image aspect ratio).
VEHICLE_CONFIGS = {
    "car":      {"width": 20, "height": 41},  # 895×436 PNG → 2.05:1
    "van":      {"width": 20, "height": 53},  # kalesa 769×292 → 2.63:1
    "truck":    {"width": 20, "height": 40},  # 527×262 → 2.01:1
    "jeep":     {"width": 20, "height": 43},  # 780×361 → 2.16:1
    "bus":      {"width": 20, "height": 47},  # 1042×446 → 2.34:1
    "tricycle": {"width": 20, "height": 24},  # 450×377 → 1.19:1
}

class TrafficGUI:
    CANVAS_W = 600
    CANVAS_H = 600
    CX = 300        # intersection centre x  (658/1312 × 600 ≈ 0.5015 × W)
    CY = 327        # intersection centre y  (654/1199 × 600 ≈ 0.5455 × H)
    ROAD_W = 41     # half-width of road
    LANE_W = 20
    LANE_1 = 14     # inner lane offset — 4 px margin from road centre line
    LANE_2 = 42     # outer lane offset — keeps 8 px side gap at width=20
    STOP_NS = 125   # 0.1952 × 600 + 10 px clearance (measured to crosswalk far edge)
    STOP_EW = 120   # 0.1761 × 600 + 10 px clearance (full crosswalk depth accounted)

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
        self._load_assets()
        self._build_layout()
        self.root.update_idletasks()
        self._rescale_to_canvas()
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

    # PIL rotation angles so the car front faces the direction of travel.
    # Source PNGs have the car front pointing RIGHT (landscape orientation).
    # PIL rotates counterclockwise: 90° CCW turns right-facing → up-facing (South).
    _DIR_ROTATIONS = {"North": 270, "South": 90, "East": 180, "West": 0}

    # Fallback candidates per vehicle type, tried in order.
    _ASSET_CANDIDATES = {
        "car":      ["car.png", "redcar.png"],
        "van":      ["van.png", "kalesa.png", "redcar.png", "car.png"],
        "truck":    ["truck.png", "redcar.png", "car.png"],
        "jeep":     ["jeep.png", "redcar.png", "car.png"],
        "bus":      ["bus.png", "truck.png"],
        "tricycle": ["trycicle.png", "tricycle.png", "redcar.png", "car.png"],
    }

    def _load_assets(self):
        """Load per-type PNG sprites from the assets/ folder and pre-rotate for each direction."""
        self.vehicle_images = {}
        if not HAS_PIL:
            return

        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        if not os.path.isdir(assets_dir):
            return

        for v_type, cfg in VEHICLE_CONFIGS.items():
            img_path = None
            for candidate in self._ASSET_CANDIDATES.get(v_type, [f"{v_type}.png"]):
                p = os.path.join(assets_dir, candidate)
                if os.path.exists(p):
                    img_path = p
                    break
            if not img_path:
                continue

            try:
                base = Image.open(img_path).convert("RGBA")
                self.vehicle_images[v_type] = {}
                for direction, angle in self._DIR_ROTATIONS.items():
                    rotated = base.rotate(angle, expand=True)
                    if direction in ("North", "South"):
                        size = (cfg["width"], cfg["height"])
                    else:
                        size = (cfg["height"], cfg["width"])
                    resized = rotated.resize(size, Image.LANCZOS)
                    self.vehicle_images[v_type][direction] = ImageTk.PhotoImage(resized)
            except Exception:
                pass

        # Progress bar frame PNG
        self.progressbar_img = None
        bar_path = os.path.join(assets_dir, "progressionbar.png")
        if HAS_PIL and os.path.exists(bar_path):
            try:
                bar = Image.open(bar_path).convert("RGBA")
                bar = bar.resize((240, 40), Image.LANCZOS)
                self.progressbar_img = ImageTk.PhotoImage(bar)
            except Exception:
                pass

        # Start / Pause button images
        self.img_pause = None
        self.img_start = None
        for attr, fname in [("img_pause", "Pause.png"), ("img_start", "Start.png")]:
            p = os.path.join(assets_dir, fname)
            if HAS_PIL and os.path.exists(p):
                try:
                    im = Image.open(p).convert("RGBA")
                    im = im.resize((240, 41), Image.LANCZOS)
                    setattr(self, attr, ImageTk.PhotoImage(im))
                except Exception:
                    pass

        # Speed bar frame + button
        self.speed_bar_img = None
        self.speed_btn_img = None
        spd_path = os.path.join(assets_dir, "speed.png")
        btn_path = os.path.join(assets_dir, "speed_button.png")
        if HAS_PIL and os.path.exists(spd_path):
            try:
                sb = Image.open(spd_path).convert("RGBA")
                sb = sb.resize((240, 34), Image.LANCZOS)
                self.speed_bar_img = ImageTk.PhotoImage(sb)
            except Exception:
                pass
        if HAS_PIL and os.path.exists(btn_path):
            try:
                bb = Image.open(btn_path).convert("RGBA")
                bb = bb.resize((30, 30), Image.LANCZOS)
                self.speed_btn_img = ImageTk.PhotoImage(bb)
            except Exception:
                pass

        # Map background
        self.layout_img = None
        layout_path = os.path.join(assets_dir, "layout-night.png")
        if HAS_PIL and os.path.exists(layout_path):
            try:
                bg = Image.open(layout_path).convert("RGB")
                bg = bg.resize((self.CANVAS_W, self.CANVAS_H), Image.LANCZOS)
                self.layout_img = ImageTk.PhotoImage(bg)
            except Exception:
                pass

    def _rescale_to_canvas(self):
        """Measure the actual canvas size and rescale all road geometry to fit."""
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 50 or h < 50:
            return  # not laid out yet, keep defaults
        self.CANVAS_W = w
        self.CANVAS_H = h
        sx = w / 600
        sy = h / 600
        s = min(sx, sy)
        self.CX     = int(round(0.5015 * w))   # 658/1312 image ratio
        self.CY     = int(round(0.5455 * h))   # 654/1199 image ratio (crosswalk midpoint)
        self.ROAD_W = int(round(41 / 600 * s * 600))
        self.LANE_1 = int(round(14 / 600 * s * 600))
        self.LANE_2 = int(round(42 / 600 * s * 600))
        self.STOP_NS = int(round(0.1952 * h)) + 10  # far edge of N/S crosswalk + clearance
        self.STOP_EW = int(round(0.1761 * w)) + 10  # far edge of E/W crosswalk + clearance
        # Reload background image at exact canvas size
        if HAS_PIL:
            assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
            layout_path = os.path.join(assets_dir, "layout-night.png")
            if os.path.exists(layout_path):
                try:
                    bg = Image.open(layout_path).convert("RGB")
                    bg = bg.resize((w, h), Image.LANCZOS)
                    self.layout_img = ImageTk.PhotoImage(bg)
                except Exception:
                    pass

    def _setup_window(self):
        scenario_label = self.sim.config.get("label", self.scenario_name)
        self.root.title(f"Traffic Simulation - {scenario_label}")
        self.root.configure(bg=COLORS["bg"])
        self.root.geometry("1000x700")
        self.root.resizable(False, False)
        
        # Pick the best available pixel/monospace font
        import tkinter.font as tkFont
        available = tkFont.families()
        pixel_candidates = [
            "Press Start 2P", "VT323", "Silkscreen",
            "Fixedsys", "Minecraft", "Courier New", "Courier",
        ]
        pf = next((f for f in pixel_candidates if f in available), "Courier")
        self.font_title = (pf, 18, "bold")
        self.font_stat  = (pf, 8)
        self.font_label = (pf, 8, "bold")

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
        
        if self.progressbar_img:
            self.progress_canvas = tk.Canvas(
                progress_frame, width=240, height=40,
                bg=COLORS["bg"], highlightthickness=0
            )
            self.progress_canvas.pack(pady=2)
            self._bar_frame_id = self.progress_canvas.create_image(
                0, 0, image=self.progressbar_img, anchor=tk.NW
            )
        else:
            self.progress_canvas = None
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
            self.canvas_frame,
            bg=COLORS["bg"], highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Interaction Sidebar
        self.panel = tk.Frame(main_frame, bg=COLORS["panel"], width=320, padx=20, pady=20, bd=2, relief=tk.RIDGE)
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
        if self.img_pause:
            self.btn_pause = tk.Label(
                self.panel, image=self.img_pause,
                bg=COLORS["panel"], cursor="hand2"
            )
            self.btn_pause.bind("<Button-1>", lambda e: self._toggle_pause())
        else:
            self.btn_pause = tk.Button(
                self.panel, text="⏸ PAUSE", command=self._toggle_pause,
                bg=COLORS["accent"], fg=COLORS["bg"], font=self.font_label,
                relief=tk.FLAT, bd=0, pady=8, cursor="hand2"
            )
        self.btn_pause.pack(pady=5)
        
        # Playback speed control
        speed_container = tk.Frame(self.panel, bg=COLORS["panel"])
        speed_container.pack(fill=tk.X, pady=(0, 10))
        tk.Label(speed_container, text="Simulation Speed", fg=COLORS["text_dim"],
                 bg=COLORS["panel"], font=self.font_label).pack(anchor="center")
        
        slider_row = tk.Frame(speed_container, bg=COLORS["panel"])
        slider_row.pack(anchor="center", pady=5)
        # Pixel-art snail/rocket icons from speed.png (already embedded in that image)
        self._speed_min, self._speed_max = 0.1, 10.0
        self._speed_val = 1.0
        self.speed_canvas = tk.Canvas(
            slider_row, width=240, height=34,
            bg=COLORS["panel"], highlightthickness=0
        )
        self.speed_canvas.pack(side=tk.LEFT, padx=4)
        self._spd_bar_id = None
        self._spd_btn_id = None
        self.speed_canvas.bind("<ButtonPress-1>",   self._on_speed_click)
        self.speed_canvas.bind("<B1-Motion>",       self._on_speed_drag)
        self.speed_canvas.bind("<ButtonRelease-1>", self._on_speed_release)
        self._draw_speed_bar(self._speed_val)
        
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
        """Draw the background map image, falling back to the old procedural layout."""
        if self.layout_img:
            self.canvas.create_image(0, 0, image=self.layout_img, anchor=tk.NW)
        else:
            self.canvas.create_rectangle(0, 0, self.CANVAS_W, self.CANVAS_H,
                                         fill="#0f172a", outline="")

    def _draw_traffic_lights(self):
        """Place signal heads at the 4 intersection corners measured from the background image."""
        w, h = self.CANVAS_W, self.CANVAS_H

        # Corner positions derived from crosswalk-edge ratios (measured from layout-night.png).
        # Offset outward by 12 px so heads sit just outside the intersection box.
        off = 12
        nw = (int(0.3567 * w) - off, int(0.3503 * h) - off)
        ne = (int(0.6456 * w) + off, int(0.3503 * h) - off)
        sw = (int(0.3567 * w) - off, int(0.7039 * h) + off)
        se = (int(0.6456 * w) + off, int(0.7039 * h) + off)

        # Orientations match the reference layout:
        # NW/NE/SW corners → horizontal (h), SE corner → vertical (v)
        configs = {
            "North": (*sw, "h"),  # SW corner — horizontal
            "South": (*ne, "h"),  # NE corner — horizontal
            "East":  (*nw, "v"),  # NW corner — vertical
            "West":  (*se, "v"),  # SE corner — vertical
        }

        self.lights = {}
        for d, (hx, hy, horient) in configs.items():
            bw, bh = (14, 36) if horient == "v" else (36, 14)
            self.canvas.create_rectangle(
                hx - bw/2, hy - bh/2, hx + bw/2, hy + bh/2,
                fill="#0f172a", outline="#475569", width=2
            )
            self.lights[d] = {"RED": [], "YELLOW": [], "GREEN": []}
            colors = ["RED", "YELLOW", "GREEN"]
            for i, color in enumerate(colors):
                lx = hx if horient == "v" else hx - 10 + i * 10
                ly = hy - 10 + i * 10 if horient == "v" else hy
                bulb = self.canvas.create_oval(
                    lx-5, ly-5, lx+5, ly+5,
                    fill=COLORS["OFF"], outline="#1e293b", width=1
                )
                self.lights[d][color].append(bulb)

    def _toggle_pause(self):
        self.paused = not self.paused
        if self.img_start and self.img_pause:
            self.btn_pause.config(image=self.img_start if self.paused else self.img_pause)
        else:
            self.btn_pause.config(text="▶ RESUME" if self.paused else "⏸ PAUSE",
                                   bg=COLORS["YELLOW"] if self.paused else COLORS["accent"])

    def _draw_speed_bar(self, value):
        """Draw the pixel-art speed bar: dark-blue→light-blue gradient fill + button."""
        sc = self.speed_canvas
        sc.delete("spd_fill")

        # Interior fill bounds (scanned from 240×34 scaled speed.png)
        x0, y0, x1, y1 = 42, 14, 202, 25
        fill_w = x1 - x0  # 160 px

        pct = (value - self._speed_min) / (self._speed_max - self._speed_min)
        filled_w = fill_w * pct
        n = 40

        for i in range(n):
            sx0 = x0 + i * fill_w / n
            sx1 = x0 + min((i + 1) * fill_w / n, filled_w)
            if sx1 <= sx0:
                break
            t = i / (n - 1) if n > 1 else 0
            # dark blue #1e3a6e → light blue #5baad8
            r = int(0x1e + (0x5b - 0x1e) * t)
            g = int(0x3a + (0xaa - 0x3a) * t)
            b = int(0x6e + (0xd8 - 0x6e) * t)
            sc.create_rectangle(sx0, y0, sx1, y1,
                                fill=f"#{r:02x}{g:02x}{b:02x}", outline="",
                                tags="spd_fill")

        # Overlay the frame image
        if self.speed_bar_img:
            if self._spd_bar_id:
                sc.delete(self._spd_bar_id)
            self._spd_bar_id = sc.create_image(0, 0, image=self.speed_bar_img, anchor=tk.NW)

        # Draw the thumb button at the filled position
        btn_x = x0 + int(filled_w)
        btn_y = (y0 + y1) // 2
        if self.speed_btn_img:
            if self._spd_btn_id:
                sc.delete(self._spd_btn_id)
            self._spd_btn_id = sc.create_image(btn_x, btn_y, image=self.speed_btn_img,
                                               anchor=tk.CENTER, tags="spd_fill")
            sc.tag_raise(self._spd_btn_id)

    def _speed_from_x(self, x):
        x0, x1 = 42, 202
        pct = max(0.0, min(1.0, (x - x0) / (x1 - x0)))
        return self._speed_min + pct * (self._speed_max - self._speed_min)

    def _on_speed_click(self, event):
        val = self._speed_from_x(event.x)
        self._update_speed(val)

    def _on_speed_drag(self, event):
        val = self._speed_from_x(event.x)
        self._update_speed(val)

    def _on_speed_release(self, event):
        val = self._speed_from_x(event.x)
        self._update_speed(val)

    def _update_speed(self, val):
        self._speed_val = float(val)
        self.speed_multiplier = self._speed_val
        self.lbl_speed.config(text=f"{self.speed_multiplier:.1f}x")
        self._draw_speed_bar(self._speed_val)

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
        self._draw_progress_bar(pct)
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
        
        if direction in ("North", "South"):
            stop_line_dist = self.STOP_NS
        else:
            stop_line_dist = self.STOP_EW
        gap = 12
        
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
        
        # Pre-populate current_pos with un-updated positions for safe collision detection
        for v in self.passing_vehicles:
            vid = int(v['id'].split('_')[1])
            current_pos[vid] = v
        for v in self.arriving_vehicles:
            vid = v['vehicle_obj'].vehicle_id
            current_pos[vid] = v

        # Handle vehicles exiting the intersection
        remaining_passing = []
        for i, v in enumerate(self.passing_vehicles):
            speed = v.get('speed', 120)
            
            # Find car ahead in passing_vehicles
            ahead_vid = None
            for j in range(i - 1, -1, -1):
                pass_v = self.passing_vehicles[j]
                if pass_v['dir'] == v['dir'] and pass_v['lane'] == v['lane']:
                    ahead_vid = int(pass_v['id'].split('_')[1])
                    break
                    
            ahead_limit = None
            if ahead_vid is not None and ahead_vid in current_pos:
                ahead_v = current_pos[ahead_vid]
                ahead_length = VEHICLE_CONFIGS[ahead_v['type']]["height"]
                my_length = VEHICLE_CONFIGS[v['type']]["height"]
                gap_size = 12 + ahead_length / 2 + my_length / 2
                
                if v['dir'] == "North": ahead_limit = ahead_v['y'] - gap_size
                elif v['dir'] == "South": ahead_limit = ahead_v['y'] + gap_size
                elif v['dir'] == "East": ahead_limit = ahead_v['x'] + gap_size
                elif v['dir'] == "West": ahead_limit = ahead_v['x'] - gap_size

            # Move
            new_x = v['x'] + v['dx'] * speed * delta
            new_y = v['y'] + v['dy'] * speed * delta
            
            if ahead_limit is not None:
                if v['dir'] == "North": new_y = min(new_y, ahead_limit)
                elif v['dir'] == "South": new_y = max(new_y, ahead_limit)
                elif v['dir'] == "East": new_x = max(new_x, ahead_limit)
                elif v['dir'] == "West": new_x = min(new_x, ahead_limit)
                
            v['x'] = new_x
            v['y'] = new_y
            
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
                gap_size = 12 + ahead_length / 2 + my_length / 2
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
                
            current_pos[vobj.vehicle_id] = v
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
            vehicle_obj.v_type = random.choice([
                "car", "car", "car", "van", "truck",
                "jeep", "jeep", "bus", "tricycle", "tricycle",
            ])
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
        l1, l2 = self.LANE_1, self.LANE_2
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
                
                l1, l2 = self.LANE_1, self.LANE_2
                off = l1 if lane_id == 0 else l2
                stop_dist = self.STOP_NS if direction in ("North", "South") else self.STOP_EW
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
                l1, l2 = self.LANE_1, self.LANE_2
                off = l1 if lane_id == 0 else l2
                
                if d == "North": x, y, orient = cx + off, cy - dist, "v"
                elif d == "South": x, y, orient = cx - off, cy + dist, "v"
                elif d == "East": x, y, orient = cx + dist, cy - off, "h"
                else: x, y, orient = cx - dist, cy + off, "h"
                
                self._update_or_create_car(v_id, x, y, orient, vobj.color, vobj.v_type, direction=d)

        # Render moving vehicles
        for v_list in [self.passing_vehicles, self.arriving_vehicles]:
            for v in v_list:
                active_ids.add(v['id'])
                self._update_or_create_car(v['id'], v['x'], v['y'], v['orient'], v['color'], v['type'], direction=v['dir'])

        # Garbage collect sprites for vehicles that left the map
        for vid in list(self.anim_objects.keys()):
            if vid not in active_ids:
                for item in self.anim_objects[vid]:
                    self.canvas.delete(item)
                del self.anim_objects[vid]

    def _update_or_create_car(self, vid, x, y, orient, color, v_type="car", direction=None):
        """Draws/moves a vehicle sprite. Uses a PNG asset when available, else draws shapes."""
        cfg = VEHICLE_CONFIGS.get(v_type, VEHICLE_CONFIGS["car"])
        w, h = (cfg["width"], cfg["height"]) if orient == "v" else (cfg["height"], cfg["width"])

        img = (self.vehicle_images.get(v_type) or self.vehicle_images.get("car", {})).get(direction) \
              if direction else None

        if vid not in self.anim_objects:
            if img:
                item = self.canvas.create_image(x, y, image=img, anchor=tk.CENTER)
                items = [item]
            else:
                body = self.canvas.create_rectangle(x-w/2, y-h/2, x+w/2, y+h/2, fill=color, outline="#000", width=1)
                items = [body]
                if orient == "v":
                    items.append(self.canvas.create_rectangle(x-w*0.35, y-h*0.2, x+w*0.35, y+h*0.1, fill="#1e293b", outline=""))
                    items.append(self.canvas.create_oval(x-w*0.4, y-h*0.45, x-w*0.1, y-h*0.35, fill="#fff", outline=""))
                    items.append(self.canvas.create_oval(x+w*0.1, y-h*0.45, x+w*0.4, y-h*0.35, fill="#fff", outline=""))
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
            items = self.anim_objects[vid]
            if len(items) == 1:
                # PNG sprite — just move it
                self.canvas.coords(items[0], x, y)
            else:
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

    def _draw_progress_bar(self, pct):
        """Fill the pixel-art progress bar with a red→yellow gradient up to pct%."""
        if not self.progress_canvas:
            self.progress["value"] = pct
            return

        # True interior found by scanning the scaled 240×40 image directly:
        # outer border x=19-27, gap x=28-31, inner border x=32-35, interior x=36-213
        x0, y0, x1, y1 = 36, 11, 213, 30
        fill_w = x1 - x0        # 177 px of fillable interior
        filled_w = fill_w * pct / 100

        self.progress_canvas.delete("gradient")

        n = 50  # number of gradient segments
        seg_w = fill_w / n
        for i in range(n):
            sx0 = x0 + i * seg_w
            sx1 = x0 + min((i + 1) * seg_w, filled_w)
            if sx1 <= sx0:
                break
            t = i / (n - 1) if n > 1 else 0
            # red #ef4444 (239,68,68) → yellow #f59e0b (245,158,11)
            r = int(239 + 6 * t)
            g = int(68 + 90 * t)
            b = int(68 - 57 * t)
            self.progress_canvas.create_rectangle(
                sx0, y0, sx1, y1,
                fill=f"#{r:02x}{g:02x}{b:02x}", outline="", tags="gradient"
            )

        # Keep the PNG frame on top so its opaque border covers the gradient edges
        self.progress_canvas.tag_raise(self._bar_frame_id)

    def _handle_completion(self):
        self.paused = True
        if self.img_start:
            self.btn_pause.config(image=self.img_start, state=tk.DISABLED)
        else:
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