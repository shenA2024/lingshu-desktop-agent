import math
import unittest
from metrics import summarize


class MetricSemantics(unittest.TestCase):
    def test_grouped_totals_and_pending_are_independent(self):
        result = summarize([{"details": [
            {"mode": "exact", "actual": [0, 0, 0], "distance": 0.2, "bound": 0.55, "hit": True, "status": "verified"},
            {"mode": "bounded_stochastic", "actual": [1, 0, 0], "distance": 1.0, "bound": 0.5, "hit": False, "status": "verified"},
            {"mode": "bounded_stochastic", "actual": None, "distance": None, "bound": 2, "hit": None, "status": "pending"},
            {"mode": "future_mode", "actual": None, "distance": None, "bound": 2, "hit": None, "status": "pending"},
        ]}])
        self.assertEqual((result["hits"], result["verified"], result["pending"]), (1, 2, 2))
        self.assertEqual(result["hit_rate"], 0.5)
        groups = {g["mode"]: g for g in result["groups"]}
        self.assertEqual(groups["bounded_stochastic"]["mean_bound"], 0.5)
        self.assertEqual(groups["bounded_stochastic"]["mean_distance"], 1.0)
        self.assertIsNone(groups["future_mode"]["hit_rate"])
        self.assertIsNone(groups["future_mode"]["mean_distance"])
        self.assertIsNone(summarize([])["hit_rate"])

    def test_reach_uses_estimated_motion_not_simulator_speed(self):
        import workbench
        scene, model = workbench.create_world("pursuit")
        seen_bounds = []
        for _ in range(18):
            prediction = model.generate()
            for eid, item in prediction["predictions"].items():
                if item["mode"] == "bounded_stochastic":
                    estimate = model._patterns["speed_estimates"][eid]
                    self.assertEqual(item["bound"], round(max(model.hit_threshold, estimate * 1.5 + model.pad), 3))
                    # No perturbation, valid in-bounds rounded previous position:
                    # Previous and new positions are rounded to two decimals;
                    # for these exact two-decimal speeds each axis delta <= v.
                    max_step = math.ceil(scene.entities[eid].speed * 100) / 100 * math.sqrt(2)
                    if scene.entities[eid].behavior == "wander":
                        seen_bounds.append((item["bound"], max_step))
            scene.step(); model.perceive()
        self.assertTrue(seen_bounds)
        # The 0.35 and 0.18 wanderers have a threshold floor covering their
        # one-step maximum even if their estimated speed gets very small.
        self.assertTrue(all(bound > maximum for bound, maximum in seen_bounds))

