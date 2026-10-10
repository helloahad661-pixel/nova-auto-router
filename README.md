# nova-auto-router

The router that **chooses**, not just fails over. Given a fleet of LLM
providers, it picks the best one per request from a policy — `cheapest`,
`fastest`, `balanced`, or `quality` — learns provider health from outcomes,
enforces a spend budget, and falls through the ranking when one dies.

```bash
python -m unittest discover -s tests -v   # 10 tests, no network, no keys
```

Companion to [nova-llmops](https://github.com/helloahad661-pixel/nova-llmops),
whose router tries providers in fixed order: use that one for deterministic
failover, this one when cost, latency, and health should decide.

## What's inside

| Module | What it does |
|---|---|
| `providers.py` | Provider profiles (price, latency, quality) + policy weights. Scoring is arithmetic, not vibes. |
| `health.py` | Rolling success rate per provider over the last 20 outcomes. Unknown providers start trusted; fully-dead ones are never picked. |
| `router.py` | `AutoRouter(policy, budget_usd)` — ranks, executes, records spend, learns health, raises `BudgetExceeded` instead of overspending. |

## Try it (no keys needed)

```python
from nova_auto_router.providers import Provider
from nova_auto_router.router import AutoRouter

fleet = [Provider("cheap", price_in=0.10, price_out=0.30, latency=0.9, quality=0.6, chat_fn=my_fn),
         Provider("smart", price_in=5.00, price_out=15.00, latency=1.5, quality=1.0, chat_fn=my_fn2)]
r = AutoRouter(fleet, policy="balanced", budget_usd=5.00)
print(r.chat([{"role": "user", "content": "What time is check-in?"}]))
# {'text': ..., 'provider': 'cheap', 'est_cost_usd': ..., 'latency': ...}
```

Wire any backend with `chat_fn(messages)` returning
`{"text", "input_tokens", "output_tokens"}`. Switch policy mid-day with
`set_policy("cheapest")` when the budget runs hot.

Part of [Nova](https://github.com/helloahad661-pixel/Nova), my macOS assistant system — `laya_agent` looks after this piece.
