import simpy
import numpy as np
import sys
import os

# Set up the search path so we can import local modules easily
sys.path.insert(0, os.path.dirname(__file__))

from vehicle import Vehicle
from pedestrian import Pedestrian
from traffic_light import TrafficLight
from config import SCENARIOS, DIRECTIONS, PHASES

class TrafficSimulation:
    """
    Main engine for the discrete-event traffic simulation.
    
    This class orchestrates the interaction between traffic lights, vehicle arrivals,
    and queuing logic using SimPy. It tracks metrics like wait times and queue 
    lengths for later analysis.
    """

    def __init__(self, scenario_name):
        if scenario_name not in SCENARIOS:
            raise ValueError(f"Unknown scenario: '{scenario_name}'. "
                             f"Valid options: {list(SCENARIOS.keys())}")

        self.scenario_name = scenario_name
        self.config = SCENARIOS[scenario_name]
        self.env = simpy.Environment()

        # Each scenario run should start with vehicle ID 1
        Vehicle.reset_counter()
        Pedestrian.reset_counter()

        # Initialize hardware: 4 lights and 4 FIFO queues
        self.lights = {
            d: TrafficLight(self.env, d, self.config)
            for d in DIRECTIONS
        }
        self.pedestrian_light = TrafficLight(
            self.env,
            "Pedestrians",
            self.config,
            valid_states=("DONT_WALK", "WALK"),
            default_state="DONT_WALK"
        )
        self.queues = {d: [] for d in DIRECTIONS}
        self.pedestrian_queues = {d: [] for d in DIRECTIONS}
        self.lane_counters = {d: 0 for d in DIRECTIONS}  # For alternating lane assignment

        self.departed_vehicles = []
        self.departed_pedestrians = []
        self.stats = {
            "total_arrived": 0,
            "total_departed": 0,
            "arrivals_per_dir": {d: 0 for d in DIRECTIONS},
            "max_queue": {d: 0 for d in DIRECTIONS},
            "pedestrian_total_arrived": 0,
            "pedestrian_total_departed": 0,
            "pedestrian_arrivals_per_crossing": {d: 0 for d in DIRECTIONS},
            "pedestrian_max_queue": {d: 0 for d in DIRECTIONS},
        }

        # Data for time-series charts (sampled periodically)
        self.queue_history = {d: [] for d in DIRECTIONS}
        self.queue_time_points = []
        self.pedestrian_queue_history = {d: [] for d in DIRECTIONS}

    def pedestrian_arrival(self, crossing):
        """
        Generates pedestrian arrivals as independent Poisson processes per crossing.
        Each pedestrian joins a curbside queue and waits for a WALK phase.
        """
        rate = self.config.get("pedestrian_arrival_rate", 4 / 60)

        while True:
            inter_arrival = np.random.exponential(1.0 / rate)
            yield self.env.timeout(inter_arrival)

            pedestrian = Pedestrian(crossing, self.env.now)
            self.pedestrian_queues[crossing].append(pedestrian)

            self.stats["pedestrian_total_arrived"] += 1
            self.stats["pedestrian_arrivals_per_crossing"][crossing] += 1

            q_len = len(self.pedestrian_queues[crossing])
            if q_len > self.stats["pedestrian_max_queue"][crossing]:
                self.stats["pedestrian_max_queue"][crossing] = q_len

    def pedestrian_departure_lane(self, crossing):
        """
        Serves one pedestrian queue whenever the WALK signal is active.
        Pedestrians leave in a realistic staggered stream rather than all at once.
        """
        walk_interval = self.config.get("pedestrian_crossing_interval", 1.2)
        was_walk = False

        while True:
            yield self.env.timeout(0.1)

            if self.pedestrian_light.state == "WALK" and self.pedestrian_queues[crossing]:
                if not was_walk:
                    was_walk = True
                    reaction = np.random.uniform(0.2, 0.8)
                    yield self.env.timeout(reaction)
                    if self.pedestrian_light.state != "WALK" or not self.pedestrian_queues[crossing]:
                        continue

                pedestrian = self.pedestrian_queues[crossing].pop(0)
                pedestrian.depart(self.env.now)
                self.departed_pedestrians.append(pedestrian)
                self.stats["pedestrian_total_departed"] += 1

                jitter = np.random.uniform(-0.25, 0.35)
                crossing_delay = max(0.6, walk_interval + jitter)
                yield self.env.timeout(crossing_delay)
            else:
                if self.pedestrian_light.state != "WALK":
                    was_walk = False

    def traffic_light_controller(self):
        """
        The "brain" of the intersection. Cycles through predefined phases 
        (e.g., N-S Green, then E-W Green) with yellow transitions in between.
        """
        green = self.config["green_duration"]
        yellow = self.config["yellow_duration"]
        pedestrian_walk = self.config.get("pedestrian_walk_duration", 20)

        while True:
            # North-South green light phase
            self.pedestrian_light.set_state("DONT_WALK")
            for d in PHASES["phase_A"]:
                self.lights[d].set_state("GREEN")
            for d in PHASES["phase_B"]:
                self.lights[d].set_state("RED")

            yield self.env.timeout(green)

            # Warning period before switching directions
            for d in PHASES["phase_A"]:
                self.lights[d].set_state("YELLOW")
            yield self.env.timeout(yellow)

            # All-red pedestrian crossing phase
            for d in DIRECTIONS:
                self.lights[d].set_state("RED")
            self.pedestrian_light.set_state("WALK")
            yield self.env.timeout(pedestrian_walk)
            self.pedestrian_light.set_state("DONT_WALK")

            # East-West green light phase
            for d in PHASES["phase_B"]:
                self.lights[d].set_state("GREEN")
            for d in PHASES["phase_A"]:
                self.lights[d].set_state("RED")

            yield self.env.timeout(green)

            # Warning period for East-West
            for d in PHASES["phase_B"]:
                self.lights[d].set_state("YELLOW")
            yield self.env.timeout(yellow)

            # All-red pedestrian crossing phase
            for d in DIRECTIONS:
                self.lights[d].set_state("RED")
            self.pedestrian_light.set_state("WALK")
            yield self.env.timeout(pedestrian_walk)
            self.pedestrian_light.set_state("DONT_WALK")

    def vehicle_arrival(self, direction):
        """
        Generates new vehicles based on a Poisson process.
        The 'arrival_rate' determines the frequency of new cars entering the lane.
        """
        rate = self.config["arrival_rate"]

        while True:
            # Use exponential distribution to model random arrival intervals
            inter_arrival = np.random.exponential(1.0 / rate)
            yield self.env.timeout(inter_arrival)

            vehicle = Vehicle(direction, self.env.now)
            vehicle.lane = self.lane_counters[direction] % 2
            self.lane_counters[direction] += 1
            vehicle.queue_slot = sum(
                1 for queued in self.queues[direction]
                if getattr(queued, 'lane', 0) == vehicle.lane
            )
            self.queues[direction].append(vehicle)
            
            self.stats["total_arrived"] += 1
            self.stats["arrivals_per_dir"][direction] += 1

            # Update the peak queue length recorded so far
            q_len = len(self.queues[direction])
            if q_len > self.stats["max_queue"][direction]:
                self.stats["max_queue"][direction] = q_len

    def vehicle_departure_lane(self, direction, lane_id):
        """
        Handles vehicles exiting from a single lane of the intersection.
        Two of these processes run in parallel per direction (one per lane),
        modeling a real 2-lane road where multiple cars pass simultaneously.
        """
        was_green = False

        while True:
            # Small polling delay for responsive checking
            yield self.env.timeout(0.05)

            if self.lights[direction].is_green() and self.queues[direction]:
                # No reaction delay - vehicles immediately flow to create continuous movement
                if not was_green:
                    was_green = True

                # Pop the first vehicle from the shared queue (FIFO)
                vehicle = self.queues[direction].pop(0)
                vehicle.depart(self.env.now)
                vehicle.lane = lane_id
                self.departed_vehicles.append(vehicle)
                self.stats["total_departed"] += 1
                
                # Very short headway (0.3s) matches the visual movement speed (120px/s)
                # This prevents following cars from stopping at the line waiting to be popped
                yield self.env.timeout(0.3)
            else:
                # Reset state if light is no longer green
                if not self.lights[direction].is_green():
                    was_green = False

    def queue_monitor(self):
        """
        Snapshots queue lengths every minute for time-series visualization.
        """
        while True:
            self.queue_time_points.append(round(self.env.now))
            for d in DIRECTIONS:
                self.queue_history[d].append(len(self.queues[d]))
                self.pedestrian_queue_history[d].append(len(self.pedestrian_queues[d]))
            yield self.env.timeout(60)

    def start(self):
        """Initialize all SimPy processes."""
        self.env.process(self.traffic_light_controller())
        self.env.process(self.queue_monitor())
        for direction in DIRECTIONS:
            self.env.process(self.vehicle_arrival(direction))
            # Two independent lane processes per direction for true parallel flow
            self.env.process(self.vehicle_departure_lane(direction, 0))
            self.env.process(self.vehicle_departure_lane(direction, 1))
            self.env.process(self.pedestrian_arrival(direction))
            self.env.process(self.pedestrian_departure_lane(direction))
        self._started = True

    def step(self, delta=1.0):
        """
        Advances the clock by 'delta' seconds. 
        Useful for real-time visualization/GUIs.
        """
        if not getattr(self, "_started", False):
            self.start()
        target = min(self.env.now + delta, self.config["simulation_time"])
        self.env.run(until=target)
        return self.env.now < self.config["simulation_time"]

    def is_done(self):
        return self.env.now >= self.config["simulation_time"]

    def run(self):
        """Executes the entire simulation duration in one go."""
        self.start()
        self.env.run(until=self.config["simulation_time"])

        label = self.config.get("label", self.scenario_name)
        print(f"[{label}] Simulation complete. "
              f"Arrived={self.stats['total_arrived']}, "
              f"Departed={self.stats['total_departed']}")

        return self.get_results()

    def get_results(self):
        """Aggregates all collected data into a structured report."""
        wait_times = [
            v.wait_time for v in self.departed_vehicles
            if v.wait_time is not None
        ]
        pedestrian_wait_times = [
            p.wait_time for p in self.departed_pedestrians
            if p.wait_time is not None
        ]

        throughput_ratio = (
            round(self.stats["total_departed"] / self.stats["total_arrived"], 4)
            if self.stats["total_arrived"] > 0 else 0
        )

        return {
            "scenario": self.scenario_name,
            "label": self.config.get("label", self.scenario_name),
            "description": self.config.get("description", ""),
            "total_arrived": self.stats["total_arrived"],
            "total_departed": self.stats["total_departed"],
            "throughput_ratio": throughput_ratio,
            "avg_wait_time": float(np.mean(wait_times)) if wait_times else 0.0,
            "max_wait_time": float(np.max(wait_times)) if wait_times else 0.0,
            "min_wait_time": float(np.min(wait_times)) if wait_times else 0.0,
            "std_wait_time": float(np.std(wait_times)) if wait_times else 0.0,
            "max_queue_per_lane": dict(self.stats["max_queue"]),
            "pedestrian_total_arrived": self.stats["pedestrian_total_arrived"],
            "pedestrian_total_departed": self.stats["pedestrian_total_departed"],
            "pedestrian_avg_wait_time": float(np.mean(pedestrian_wait_times)) if pedestrian_wait_times else 0.0,
            "pedestrian_max_queue_per_crossing": dict(self.stats["pedestrian_max_queue"]),
            "queue_history": dict(self.queue_history),
            "pedestrian_queue_history": dict(self.pedestrian_queue_history),
            "queue_time_points": list(self.queue_time_points),
            "vehicles": self.departed_vehicles,
            "pedestrians": self.departed_pedestrians,
            "light_state_log": {
                d: self.lights[d].state_log for d in DIRECTIONS
            },
            "pedestrian_light_state_log": list(self.pedestrian_light.state_log)
        }
