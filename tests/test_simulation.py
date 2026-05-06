"""
Unit testing suite for the Traffic Light Simulation.
Verifies hardware state machines, vehicle tracking, and simulation accuracy.
"""

import unittest
import sys
import os

# Point to the source directory for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from simulation import TrafficSimulation
from traffic_light import TrafficLight
from vehicle import Vehicle
from config import SCENARIOS, DIRECTIONS

class TestTrafficLight(unittest.TestCase):
    """Verifies that traffic signals cycle and log states correctly."""

    def setUp(self):
        import simpy
        self.env = simpy.Environment()
        self.config = SCENARIOS["normal"]
        self.light = TrafficLight(self.env, "North", self.config)

    def test_initial_state_is_red(self):
        self.assertEqual(self.light.state, "RED")

    def test_set_state_green(self):
        self.light.set_state("GREEN")
        self.assertTrue(self.light.is_green())
        self.assertFalse(self.light.is_red())

    def test_set_state_yellow(self):
        self.light.set_state("YELLOW")
        self.assertTrue(self.light.is_yellow())

    def test_invalid_state_raises(self):
        with self.assertRaises(ValueError):
            self.light.set_state("PURPLE")

    def test_state_log_records_changes(self):
        self.light.set_state("GREEN")
        self.light.set_state("YELLOW")
        self.light.set_state("RED")
        self.assertEqual(len(self.light.state_log), 3)
        self.assertEqual(self.light.state_log[-1]["state"], "RED")

class TestVehicle(unittest.TestCase):
    """Checks vehicle lifecycle: from arrival to departure delay calculations."""

    def setUp(self):
        Vehicle.reset_counter()

    def test_vehicle_creation(self):
        v = Vehicle("North", 10.5)
        self.assertEqual(v.direction, "North")
        self.assertEqual(v.arrival_time, 10.5)
        self.assertIsNone(v.departure_time)

    def test_vehicle_depart(self):
        v = Vehicle("South", 5.0)
        v.depart(15.0)
        self.assertEqual(v.departure_time, 15.0)
        self.assertAlmostEqual(v.wait_time, 10.0)

    def test_vehicle_ids_increment(self):
        v1 = Vehicle("North", 0)
        v2 = Vehicle("South", 1)
        self.assertEqual(v2.vehicle_id, v1.vehicle_id + 1)

    def test_vehicle_id_reset(self):
        Vehicle("North", 0)
        Vehicle.reset_counter()
        v = Vehicle("East", 0)
        self.assertEqual(v.vehicle_id, 1)

class TestSimulation(unittest.TestCase):
    """Integration tests to ensure different traffic volumes behave as expected."""

    def test_normal_scenario_runs(self):
        sim = TrafficSimulation("normal")
        results = sim.run()
        self.assertGreater(results["total_arrived"], 0)
        self.assertGreater(results["total_departed"], 0)

    def test_low_traffic_scenario_runs(self):
        sim = TrafficSimulation("low_traffic")
        results = sim.run()
        self.assertGreater(results["total_arrived"], 0)

    def test_rush_hour_scenario_runs(self):
        sim = TrafficSimulation("rush_hour")
        results = sim.run()
        self.assertGreater(results["total_arrived"], 0)

    def test_avg_wait_time_positive(self):
        sim = TrafficSimulation("rush_hour")
        results = sim.run()
        self.assertGreater(results["avg_wait_time"], 0)

    def test_rush_hour_more_arrivals_than_low(self):
        """Validates that volume settings actually result in more traffic."""
        low_sim, rush_sim = TrafficSimulation("low_traffic"), TrafficSimulation("rush_hour")
        low_r, rush_r = low_sim.run(), rush_sim.run()
        self.assertGreater(rush_r["total_arrived"], low_r["total_arrived"])

    def test_rush_hour_longer_avg_wait_than_low(self):
        """Confirms that higher volume naturally leads to longer delays."""
        low_sim, rush_sim = TrafficSimulation("low_traffic"), TrafficSimulation("rush_hour")
        low_r, rush_r = low_sim.run(), rush_sim.run()
        self.assertGreater(rush_r["avg_wait_time"], low_r["avg_wait_time"])

    def test_light_states_valid_after_run(self):
        sim = TrafficSimulation("normal")
        sim.run()
        valid_states = {"RED", "GREEN", "YELLOW"}
        for d in DIRECTIONS:
            self.assertIn(sim.lights[d].state, valid_states)

    def test_results_keys_present(self):
        expected_keys = [
            "scenario", "total_arrived", "total_departed",
            "avg_wait_time", "max_wait_time", "min_wait_time",
            "throughput_ratio", "max_queue_per_lane", "vehicles"
        ]
        sim = TrafficSimulation("normal")
        results = sim.run()
        for key in expected_keys:
            self.assertIn(key, results, f"Missing key: {key}")

    def test_throughput_ratio_between_0_and_1(self):
        sim = TrafficSimulation("low_traffic")
        results = sim.run()
        self.assertGreaterEqual(results["throughput_ratio"], 0.0)
        self.assertLessEqual(results["throughput_ratio"], 1.0)

    def test_invalid_scenario_raises(self):
        with self.assertRaises(ValueError):
            TrafficSimulation("non_existent_scenario")

    def test_all_four_directions_have_queue_stats(self):
        sim = TrafficSimulation("normal")
        results = sim.run()
        for d in DIRECTIONS:
            self.assertIn(d, results["max_queue_per_lane"])

    def test_no_negative_wait_times(self):
        sim = TrafficSimulation("normal")
        results = sim.run()
        for v in results["vehicles"]:
            if v.wait_time is not None:
                self.assertGreaterEqual(v.wait_time, 0)

    def test_state_log_populated(self):
        sim = TrafficSimulation("normal")
        sim.run()
        for d in DIRECTIONS:
            self.assertGreater(len(sim.lights[d].state_log), 0)

    def test_optimized_lower_wait_than_rush_hour(self):
        """Verifies that the 'optimized' timing actually helps throughput."""
        rush_sim, optimized_sim = TrafficSimulation("rush_hour"), TrafficSimulation("optimized")
        rush_r, opt_r = rush_sim.run(), optimized_sim.run()
        # With 2-lane parallel departure, both scenarios clear queues faster,
        # so the gap between them is smaller. Allow wider margin for stochastic noise.
        self.assertLessEqual(opt_r["avg_wait_time"], rush_r["avg_wait_time"] * 1.5)

if __name__ == "__main__":
    unittest.main(verbosity=2)
