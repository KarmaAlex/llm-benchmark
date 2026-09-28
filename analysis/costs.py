"""
What a benchmark run cost, or would cost, in euros.

Two very different bases:

  API models (provider openai)   tokens x the provider's list price. Completion
                                 tokens already include reasoning tokens, which
                                 OpenAI bills as output. Runs don't record
                                 cached-input tokens, so all input is priced
                                 at the uncached rate - an upper bound.
  local models (llama.cpp)       electricity only: inference time x an assumed
                                 wall-power draw x the Italian household
                                 electricity price. Hardware depreciation is
                                 not included.

Only the model call is costed - `execution_time` is the model's latency; the
compile / test / SonarQube time a sonar case also takes is harness cost that
every model pays alike.

No power was measured while the runs ran (nvidia-smi reports no usable
power figure on the laptop the local runs were made on), so the draw is an
assumption with a low-high band around it rather than a measurement. Every
figure and CSV that shows a cost carries these assumptions with it.

All prices below are as of PRICES_AS_OF; override them from the command line
(see add_cost_arguments) rather than editing them for a one-off.
"""

import argparse
import math
from dataclasses import asdict, dataclass

import pandas as pd

from analysis.aggregate import RunRef, api_model_ids, model_catalog, rep_frame

PRICES_AS_OF = "2026-09-28"


@dataclass(frozen=True)
class ApiPrice:
    """USD per 1M tokens, standard tier."""
    input: float
    cached_input: float
    output: float


# https://developers.openai.com/api/docs/pricing (standard tier), 2026-09-28.
OPENAI_PRICES_USD_PER_1M = {
    "gpt-5": ApiPrice(input=1.25, cached_input=0.125, output=10.00),
    "gpt-5-mini": ApiPrice(input=0.25, cached_input=0.025, output=2.00),
}
OPENAI_PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing"

# ECB euro reference rate, 25 September 2026 (the latest published on
# 2026-09-28): 1 EUR = 1.1403 USD.
USD_PER_EUR = 1.1403
USD_PER_EUR_SOURCE = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"

# ARERA reference price for the typical household customer (Maggior Tutela),
# III quarter 2026, taxes and system charges included: 31.63 c€/kWh.
ELECTRICITY_EUR_PER_KWH = 0.3163
ELECTRICITY_SOURCE = (
    "https://www.arera.it/comunicati-stampa/dettaglio/"
    "elettricita-maggior-tutela-46-nel-iii-trimestre-2026-per-i-clienti-vulnerabili"
)

# Wall-power draw while a local model generates. The local runs were made on
# a laptop with an RTX 4050 Laptop GPU (60 W default power limit) and a
# Ryzen 7 7735HS (35-54 W): ~90 W is GPU near its limit plus a partly loaded
# CPU and the rest of the platform; 60-120 W brackets a mostly idle CPU to
# both chips at full tilt.
LOCAL_WATTS = 90.0
LOCAL_WATTS_RANGE = (60.0, 120.0)

API = "api"
ELECTRICITY = "electricity"
UNPRICED = "unpriced"


@dataclass(frozen=True)
class CostAssumptions:
    usd_per_eur: float = USD_PER_EUR
    eur_per_kwh: float = ELECTRICITY_EUR_PER_KWH
    local_watts: float = LOCAL_WATTS
    local_watts_low: float = LOCAL_WATTS_RANGE[0]
    local_watts_high: float = LOCAL_WATTS_RANGE[1]
    prices_as_of: str = PRICES_AS_OF

    def api_eur(self, api_model: str, prompt_tokens: float, completion_tokens: float) -> float:
        price = OPENAI_PRICES_USD_PER_1M.get(api_model)
        if price is None:
            return math.nan
        usd = (prompt_tokens * price.input + completion_tokens * price.output) / 1_000_000
        return usd / self.usd_per_eur

    def electricity_eur(self, seconds: float, watts: float) -> float:
        return self.kwh(seconds, watts) * self.eur_per_kwh

    @staticmethod
    def kwh(seconds: float, watts: float) -> float:
        return seconds / 3600 * watts / 1000

    def note(self, bases: set[str]) -> str:
        """One line stating the assumptions behind a cost figure."""
        parts = []
        if API in bases:
            parts.append(f"API: OpenAI standard list prices as of {self.prices_as_of}, uncached input, "
                         f"1 € = {self.usd_per_eur} $ (ECB)")
        if ELECTRICITY in bases:
            parts.append(f"local: electricity only, inference time × {self.local_watts:g} W "
                         f"(band {self.local_watts_low:g}-{self.local_watts_high:g} W) × "
                         f"€{self.eur_per_kwh:.4f}/kWh (ARERA, Q3 2026)")
        return "  ·  ".join(parts)

    def as_dict(self) -> dict:
        return {
            **asdict(self),
            "openai_prices_usd_per_1m": {m: asdict(p) for m, p in OPENAI_PRICES_USD_PER_1M.items()},
            "sources": {
                "openai": OPENAI_PRICING_SOURCE,
                "usd_per_eur": USD_PER_EUR_SOURCE,
                "electricity": ELECTRICITY_SOURCE,
            },
        }


def add_cost_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("cost assumptions")
    group.add_argument("--local-watts", type=float, default=LOCAL_WATTS,
                       help=f"Assumed wall-power draw of a local model while generating (default: {LOCAL_WATTS:g}).")
    group.add_argument("--local-watts-range", type=float, nargs=2, metavar=("LOW", "HIGH"),
                       default=list(LOCAL_WATTS_RANGE),
                       help="Band drawn around the local estimate (default: %(default)s).")
    group.add_argument("--kwh-price", type=float, default=ELECTRICITY_EUR_PER_KWH,
                       help=f"Electricity price in €/kWh (default: {ELECTRICITY_EUR_PER_KWH}, ARERA Q3 2026).")
    group.add_argument("--usd-per-eur", type=float, default=USD_PER_EUR,
                       help=f"Exchange rate for API prices (default: {USD_PER_EUR}, ECB 2026-09-25).")


def assumptions_from_args(args: argparse.Namespace) -> CostAssumptions:
    low, high = sorted(args.local_watts_range)
    return CostAssumptions(
        usd_per_eur=args.usd_per_eur,
        eur_per_kwh=args.kwh_price,
        local_watts=args.local_watts,
        local_watts_low=min(low, args.local_watts),
        local_watts_high=max(high, args.local_watts),
    )


# --------------------------------------------------------------------------- #
# frames
# --------------------------------------------------------------------------- #


def trial_costs(ref: RunRef, assumptions: CostAssumptions,
                providers: dict[str, str] | None = None, model_ids: dict[str, str] | None = None) -> pd.DataFrame:
    """One row per (suite, repetition, case) with its cost in euros, and a
    low/high band for electricity-costed trials (equal to the estimate for
    API trials, whose price is known)."""
    providers = model_catalog() if providers is None else providers
    model_ids = api_model_ids() if model_ids is None else model_ids
    trials = rep_frame(ref)
    if trials.empty:
        return trials

    configs = trials["config"].fillna("")
    provider = configs.map(lambda c: providers.get(c) or providers.get(ref.model, ""))
    api_model = configs.map(lambda c: model_ids.get(c) or model_ids.get(ref.model, ""))
    # Only an API model id means anything here; for llama.cpp it's a file path.
    api_model = api_model.where(provider != "llama.cpp", "")
    seconds = trials["execution_time"].fillna(0.0)
    prompt = trials["prompt_tokens"].fillna(0)
    completion = trials["completion_tokens"].fillna(0)

    rows = []
    for i in trials.index:
        if provider[i] == "openai" and api_model[i] in OPENAI_PRICES_USD_PER_1M:
            cost = assumptions.api_eur(api_model[i], prompt[i], completion[i])
            rows.append((API, cost, cost, cost, math.nan))
        elif provider[i] == "llama.cpp":
            rows.append((
                ELECTRICITY,
                assumptions.electricity_eur(seconds[i], assumptions.local_watts),
                assumptions.electricity_eur(seconds[i], assumptions.local_watts_low),
                assumptions.electricity_eur(seconds[i], assumptions.local_watts_high),
                assumptions.kwh(seconds[i], assumptions.local_watts),
            ))
        else:
            rows.append((UNPRICED, math.nan, math.nan, math.nan, math.nan))

    costed = pd.DataFrame(rows, index=trials.index,
                          columns=["cost_basis", "cost_eur", "cost_eur_low", "cost_eur_high", "kwh"])
    return trials.assign(provider=provider, api_model=api_model).join(costed)


def cost_summary(trials: pd.DataFrame, summary: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per (model, suite): what the whole run cost, what one repetition of
    the suite costs, and - joined with the pass counts in `summary` - what
    one passing trial costs."""
    rows = []
    for (model, group, suite), frame in trials.groupby(["model", "group", "suite"], sort=False):
        repetitions = frame["rep"].nunique()
        total = frame[["cost_eur", "cost_eur_low", "cost_eur_high"]].sum(min_count=1)
        rows.append({
            "model": model,
            "group": group,
            "suite": suite,
            "cost_basis": "/".join(sorted(set(frame["cost_basis"]))),
            "api_model": "/".join(sorted({m for m in frame["api_model"] if m})),
            "repetitions": repetitions,
            "trials": len(frame),
            "prompt_tokens": int(frame["prompt_tokens"].fillna(0).sum()),
            "completion_tokens": int(frame["completion_tokens"].fillna(0).sum()),
            "inference_seconds": frame["execution_time"].fillna(0).sum(),
            "kwh": frame["kwh"].sum(min_count=1),
            "total_cost_eur": total["cost_eur"],
            "cost_per_rep_eur": total["cost_eur"] / repetitions,
            "cost_per_rep_eur_low": total["cost_eur_low"] / repetitions,
            "cost_per_rep_eur_high": total["cost_eur_high"] / repetitions,
            "cost_per_trial_eur": total["cost_eur"] / len(frame),
        })
    costs = pd.DataFrame(rows)
    if summary is not None and not costs.empty:
        passes = summary[["model", "suite", "passes"]]
        costs = costs.merge(passes, on=["model", "suite"], how="left")
        per_pass = costs["passes"].where(costs["passes"] > 0)
        for suffix in ("", "_low", "_high"):
            costs[f"cost_per_pass_eur{suffix}"] = costs["cost_per_rep_eur" + suffix] * costs["repetitions"] / per_pass
    return costs


def format_eur(value: float) -> str:
    """Two significant figures below €1, cents above: €5.83, €0.56, €0.0021."""
    if value is None or math.isnan(value):
        return "n/a"
    if value == 0:
        return "€0"
    if value >= 10:
        return f"€{value:,.0f}"
    digits = max(2, 1 - math.floor(math.log10(abs(value))))
    return f"€{value:.{digits}f}"
