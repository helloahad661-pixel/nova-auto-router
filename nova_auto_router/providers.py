"""Provider profiles + policy scoring. Cost and latency are declared per
1M tokens / per call so routing stays arithmetic, not vibes."""


class Provider:
    def __init__(self, name, price_in=0.0, price_out=0.0, latency=0.0,
                 quality=1.0, chat_fn=None):
        self.name = name
        self.price_in = price_in      # USD per 1M input tokens
        self.price_out = price_out    # USD per 1M output tokens
        self.latency = latency        # expected seconds per call
        self.quality = quality        # 0..1, higher is smarter
        self._chat = chat_fn

    def est_cost(self, in_tok=1000, out_tok=500):
        return (in_tok * self.price_in + out_tok * self.price_out) / 1e6

    def chat(self, messages):
        if self._chat is None:
            raise RuntimeError("no backend wired for %s" % self.name)
        return self._chat(messages)


# policy -> weights over (cost, latency, quality). Higher score wins.
POLICIES = {
    "cheapest": {"cost": 3.0, "latency": 0.5, "quality": 0.2},
    "fastest": {"cost": 0.5, "latency": 3.0, "quality": 0.2},
    "balanced": {"cost": 1.0, "latency": 1.0, "quality": 1.0},
    "quality": {"cost": 0.2, "latency": 0.5, "quality": 3.0},
}


def score(provider, policy, health, in_tok=1000, out_tok=500):
    w = POLICIES[policy]
    h = health.score(provider.name)
    if h <= 0.0:
        return float("-inf")  # fully unhealthy: never picked, always sorts last
    cost = provider.est_cost(in_tok, out_tok)
    # lower cost/latency is better, higher quality/health is better.
    # cost is ~1e-3 dollars, so x100 keeps the three terms comparable.
    return (w["quality"] * provider.quality * h
            - w["cost"] * cost * 100.0
            - w["latency"] * provider.latency)
