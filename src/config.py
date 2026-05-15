# Centralized simulation settings
# Arrival rates are defined in vehicles per second per direction

SCENARIOS = {
    "low_traffic": {
        "arrival_rate": 5 / 60,
        "green_duration": 30,
        "yellow_duration": 5,
        "departure_interval": 1.0,
        "simulation_time": 3600,
        "label": "Low Traffic",
        "description": "Late night (~1-2 AM) — 5 vehicles/min/lane"
    },
    "normal": {
        "arrival_rate": 10 / 60,
        "green_duration": 30,
        "yellow_duration": 5,
        "departure_interval": 1.0,
        "simulation_time": 3600,
        "label": "Normal",
        "description": "Night (~9-10 PM) — 10 vehicles/min/lane"
    },
    "rush_hour": {
        "arrival_rate": 20 / 60,
        "green_duration": 45,
        "yellow_duration": 5,
        "departure_interval": 1.0,
        "simulation_time": 3600,
        "label": "Rush Hour",
        "description": "Weekend night rush (~11 PM-1 AM) — 20 vehicles/min/lane"
    },
    "optimized": {
        "arrival_rate": 20 / 60,
        "green_duration": 60,
        "yellow_duration": 5,
        "departure_interval": 1.0,
        "simulation_time": 3600,
        "label": "Optimized",
        "description": "Night rush with optimized signal timing — green=60s"
    }
}

DIRECTIONS = ["North", "South", "East", "West"]

# Defines which lanes share a green light
PHASES = {
    "phase_A": ["North", "South"],
    "phase_B": ["East", "West"]
}
