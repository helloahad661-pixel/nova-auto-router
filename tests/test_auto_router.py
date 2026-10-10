"""Tests: policy picks, failover, health learning, budget cap. Stdlib only.
Run: python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nova_auto_router.health import Health
from nova_auto_router.providers import Provider
from nova_auto_router.router import AutoRouter, BudgetExceeded


def fake(text, in_tok=100, out_tok=50, fail=False):
    def run(messages):
        if fail:
            raise RuntimeError("backend down")
        return {"text": text, "input_tokens": in_tok,
                "output_tokens": out_tok}
    return run


def fleet():
    return [
        Provider("cheap", price_in=0.10, price_out=0.30, latency=0.9,
                 quality=0.4, chat_fn=fake("cheap-answer")),
        Provider("fast", price_in=1.00, price_out=3.00, latency=0.1,
                 quality=0.5, chat_fn=fake("fast-answer")),
        Provider("smart", price_in=5.00, price_out=15.00, latency=1.5,
                 quality=1.0, chat_fn=fake("smart-answer")),
    ]


class TestPolicies(unittest.TestCase):
    def test_cheapest_picks_cheap(self):
        r = AutoRouter(fleet(), policy="cheapest")
        self.assertEqual(r.pick()[0].name, "cheap")

    def test_fastest_picks_fast(self):
        r = AutoRouter(fleet(), policy="fastest")
        self.assertEqual(r.pick()[0].name, "fast")

    def test_quality_picks_smart(self):
        r = AutoRouter(fleet(), policy="quality")
        self.assertEqual(r.pick()[0].name, "smart")

    def test_unknown_policy_rejected(self):
        with self.assertRaises(ValueError):
            AutoRouter(fleet(), policy="luxury")


class TestFailover(unittest.TestCase):
    def test_dead_first_choice_falls_through(self):
        ps = fleet()
        ps[0]._chat = fake("x", fail=True)  # kill 'cheap'
        r = AutoRouter(ps, policy="cheapest")
        out = r.chat([{"role": "user", "content": "hi"}])
        self.assertNotEqual(out["provider"], "cheap")
        self.assertIn("provider", out)

    def test_two_dead_providers_dont_crash_pick(self):
        ps = fleet()
        ps[0]._chat = fake("x", fail=True)
        ps[1]._chat = fake("y", fail=True)
        r = AutoRouter(ps, policy="cheapest")
        r.chat([{"role": "user", "content": "hi"}])  # smart serves
        order = [p.name for p in r.pick()]  # two at -inf: must not raise
        self.assertEqual(order[0], "smart")
        self.assertEqual(set(order[1:]), {"cheap", "fast"})

    def test_repeated_failures_sink_provider(self):
        ps = fleet()
        ps[0]._chat = fake("x", fail=True)
        r = AutoRouter(ps, policy="cheapest")
        for _ in range(3):
            try:
                r.chat([{"role": "user", "content": "hi"}])
            except RuntimeError:
                pass
        # cheap failed every time: health 0 -> never picked first again
        self.assertNotEqual(r.pick()[0].name, "cheap")


class TestBudget(unittest.TestCase):
    def test_budget_stops_spend(self):
        r = AutoRouter(fleet(), policy="cheapest", budget_usd=0.000001)
        with self.assertRaises(BudgetExceeded):
            for _ in range(50):
                r.chat([{"role": "user", "content": "hi"}])

    def test_spend_tracked(self):
        r = AutoRouter(fleet(), policy="cheapest")
        r.chat([{"role": "user", "content": "hi"}])
        self.assertGreater(r.spent_usd, 0)
        self.assertEqual(r.calls, 1)


class TestHealth(unittest.TestCase):
    def test_unknown_starts_trusted(self):
        self.assertEqual(Health().score("new"), 1.0)

    def test_score_tracks_success_rate(self):
        h = Health()
        h.report("p", True)
        h.report("p", False)
        self.assertEqual(h.score("p"), 0.5)


if __name__ == "__main__":
    unittest.main()
