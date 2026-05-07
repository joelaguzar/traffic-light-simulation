import simpy
import numpy as np
import sys
import os

# Set up the search path so we can import local modules easily
sys.path.insert(0, os.path.dirname(__file__))

from vehicle import Vehicle
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

        # Initialize hardware: 4 lights and 4 FIFO queues
        self.lights = {
            d: TrafficLight(self.env, d, self.config)
            for d in DIRECTIONS
        }
        self.queues = {d: [] for d in DIRECTIONS}
        self.lane_counters = {d: 0 for d in DIRECTIONS}  # For alternating lane assignment

        self.departed_vehicles = []
        self.stats = {
            "total_arrived": 0,
            "total_departed": 0,
            "arrivals_per_dir": {d: 0 for d in DIRECTIONS},
            "max_queue": {d: 0 for d in DIRECTIONS}
        }

        # Data for time-series charts (sampled periodically)
        self.queue_history = {d: [] for d in DIRECTIONS}
        self.queue_time_points = []

    def traffic_light_controller(self):
        """
        The "brain" of the intersection. Cycles through predefined phases 
        (e.g., N-S Green, then E-W Green) with yellow transitions in between.
        """
        green = self.config["green_duration"]
        yellow = self.config["yellow_duration"]

        while True:
            # North-South green light phase
            for d in PHASES["phase_A"]:
                self.lights[d].set_state("GREEN")
            for d in PHASES["phase_B"]:
                self.lights[d].set_state("RED")

            yield self.env.timeout(green)

            # Warning period before switching directions
            for d in PHASES["phase_A"]:
                self.lights[d].set_state("YELLOW")
            yield self.env.timeout(yellow)

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
            "queue_history": dict(self.queue_history),
            "queue_time_points": list(self.queue_time_points),
            "vehicles": self.departed_vehicles,
            "light_state_log": {
                d: self.lights[d].state_log for d in DIRECTIONS
            }
        }
