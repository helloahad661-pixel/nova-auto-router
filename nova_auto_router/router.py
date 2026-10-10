"""AutoRouter: picks the best provider per policy, executes, learns from
the outcome, enforces a spend budget. Stdlib only."""
import time

from .health import Health
from .providers import POLICIES, score


class BudgetExceeded(Exception):
    pass


class AutoRouter:
    def __init__(self, providers, policy="balanced", budget_usd=None):
        if policy not in POLICIES:
            raise ValueError("unknown policy: %s (pick %s)"
                             % (policy, sorted(POLICIES)))
        self.providers = {p.name: p for p in providers}
        self.policy = policy
        self.budget_usd = budget_usd
        self.spent_usd = 0.0
        self.health = Health()
        self.calls = 0

    def set_policy(self, policy):
        if policy not in POLICIES:
            raise ValueError("unknown policy: %s" % policy)
        self.policy = policy

    def pick(self, in_tok=1000, out_tok=500):
        # key= sort: never compares Provider objects (tuple sort would crash
        # on ties, e.g. two fully-unhealthy providers at -inf).
        return sorted(self.providers.values(),
                      key=lambda p: score(p, self.policy, self.health,
                                          in_tok, out_tok),
                      reverse=True)

    def chat(self, messages, in_tok=1000, out_tok=500):
        if self.budget_usd is not None and self.spent_usd >= self.budget_usd:
            raise BudgetExceeded("spent $%.6f of $%.6f budget"
                                 % (self.spent_usd, self.budget_usd))
        errors = []
        for p in self.pick(in_tok, out_tok):
            t0 = time.monotonic()
            try:
                r = p.chat(messages)
                cost = p.est_cost(r.get("input_tokens", in_tok),
                                  r.get("output_tokens", out_tok))
                self.spent_usd += cost
                self.calls += 1
                self.health.report(p.name, True)
                r["provider"] = p.name
                r["est_cost_usd"] = round(cost, 6)
                r["latency"] = round(time.monotonic() - t0, 3)
                return r
            except Exception as e:
                self.health.report(p.name, False)
                errors.append("%s: %s" % (p.name, e))
        raise RuntimeError("all providers failed: %s" % " | ".join(errors))
