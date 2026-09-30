"""
What a benchmark run cost, or would cost, in euros.

Three very different bases:

  API models (provider openai)   tokens x the provider's list price. Completion
                                 tokens already include reasoning tokens, which
                                 OpenAI bills as output. Runs don't record
                                 cached-input tokens, so all input is priced
                                 at the uncached rate - an upper bound.
  rented GPUs (llama.cpp on a    GPU-hours: inference time x the GPUs the run
  GPU in GPU_HOUR_PRICES)        was given x a per-GPU-hour rate. This is how
                                 shared GPUs are paid for - by allocation, not
                                 by energy - and it's unaffected by what other
                                 jobs on the node draw, which a power reading
                                 isn't. The run's settings record its GPUs
                                 (runner/providers/hardware.py).
  own machine (llama.cpp on any  electricity only, at the Italian household
  other GPU)                     price. Hardware depreciation is not included.
                                 Owned hardware has no GPU-hour price; the
                                 cost of using it once more is its energy.
                                   measured  runs recorded since power sampling
                                             was added (runner/providers/power.py)
                                             carry each call's energy: GPU board +
                                             CPU package, a lower bound on wall
                                             energy (RAM, display, PSU losses are
                                             not measured).
                                   assumed   older runs, or machines without a
                                             readable sensor: inference time x an
                                             assumed wall-power draw, with a
                                             low-high band around it.

Only the model call is costed - `execution_time` is the model's latency; the
compile / test / SonarQube time a sonar case also takes is harness cost that
every model pays alike.

Each trial is costed on its own basis, so a run with measurements for only
some calls still uses them where it has them. Every figure and CSV that
shows a cost says which bases and assumptions it rests on.

All prices below are as of PRICES_AS_OF; override them from the command line
(see add_cost_arguments) rather than editing them for a one-off.
"""

import argparse
import math
from dataclasses import asdict, dataclass, field

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

@dataclass(frozen=True)
class GpuHourPrice:
    """EUR per GPU-hour, with a band around it."""
    eur: float
    low: float
    high: float


# On-demand market rates, USD per GPU-hour, 2026-09-28 (getdeploying.com):
# H200 NVL 1x at RunPod $3.79 (central), 2x at Vast.ai $3.52 (cheapest NVL
# listing), and $4.50, the median H200 rate across 35 providers. Keys are
# GPU names exactly as nvidia-smi reports them. A cluster with its own
# internal rate should use that instead: --gpu-hour-price "NAME=EUR".
GPU_HOUR_PRICES_USD = {
    "NVIDIA H200 NVL": (3.79, 3.52, 4.50),
}
GPU_HOUR_SOURCE = "https://getdeploying.com/gpus/nvidia-h200"

# Wall-power draw while a local model generates. The local runs were made on
# a laptop with an RTX 4050 Laptop GPU (60 W default power limit) and a
# Ryzen 7 7735HS (35-54 W): ~90 W is GPU near its limit plus a partly loaded
# CPU and the rest of the platform; 60-120 W brackets a mostly idle CPU to
# both chips at full tilt.
LOCAL_WATTS = 90.0
LOCAL_WATTS_RANGE = (60.0, 120.0)

API = "api"
GPU_HOURS = "gpu-hours"
ELECTRICITY = "electricity"                    # assumed power draw
ELECTRICITY_MEASURED = "electricity-measured"  # recorded energy
UNPRICED = "unpriced"


@dataclass(frozen=True)
class CostAssumptions:
    usd_per_eur: float = USD_PER_EUR
    eur_per_kwh: float = ELECTRICITY_EUR_PER_KWH
    local_watts: float = LOCAL_WATTS
    local_watts_low: float = LOCAL_WATTS_RANGE[0]
    local_watts_high: float = LOCAL_WATTS_RANGE[1]
    prices_as_of: str = PRICES_AS_OF
    # GPU name as nvidia-smi reports it -> EUR per GPU-hour (matched ignoring case).
    gpu_hour_prices: dict[str, GpuHourPrice] = field(default_factory=lambda: default_gpu_hour_prices(USD_PER_EUR))
    gpu_hour_overridden: tuple[str, ...] = ()

    def gpu_hour_price(self, gpus: list[str]) -> GpuHourPrice | None:
        """The summed hourly rate of these GPUs, or None unless every one
        of them has a price (a run on any other machine is costed by its
        electricity instead)."""
        by_name = {name.lower(): price for name, price in self.gpu_hour_prices.items()}
        prices = [by_name.get(name.lower()) for name in gpus]
        if not prices or any(p is None for p in prices):
            return None
        return GpuHourPrice(*(sum(getattr(p, f) for p in prices) for f in ("eur", "low", "high")))

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
        if GPU_HOURS in bases:
            rates = ", ".join(
                f"{name} €{p.eur:.2f}/GPU-h" + ("" if p.low == p.high else f" (band €{p.low:.2f}-{p.high:.2f})")
                for name, p in self.gpu_hour_prices.items())
            source = ("site rate" if self.gpu_hour_overridden
                      else f"on-demand market rate as of {self.prices_as_of}")
            parts.append(f"rented GPU: inference time × GPUs × {rates}, {source}")
        if ELECTRICITY_MEASURED in bases:
            parts.append(f"local (measured): recorded GPU board + CPU package energy × "
                         f"€{self.eur_per_kwh:.4f}/kWh (ARERA, Q3 2026) - excludes RAM, display, PSU losses")
        if ELECTRICITY in bases:
            parts.append(f"local (assumed): inference time × {self.local_watts:g} W "
                         f"(band {self.local_watts_low:g}-{self.local_watts_high:g} W) × "
                         f"€{self.eur_per_kwh:.4f}/kWh (ARERA, Q3 2026)")
        return "  ·  ".join(parts)

    def as_dict(self) -> dict:
        return {
            **asdict(self),
            "openai_prices_usd_per_1m": {m: asdict(p) for m, p in OPENAI_PRICES_USD_PER_1M.items()},
            "sources": {
                "openai": OPENAI_PRICING_SOURCE,
                "gpu_hour": GPU_HOUR_SOURCE,
                "usd_per_eur": USD_PER_EUR_SOURCE,
                "electricity": ELECTRICITY_SOURCE,
            },
        }


def default_gpu_hour_prices(usd_per_eur: float) -> dict[str, GpuHourPrice]:
    return {name: GpuHourPrice(*(usd / usd_per_eur for usd in prices))
            for name, prices in GPU_HOUR_PRICES_USD.items()}


def parse_gpu_hour_prices(values: list[str] | None) -> dict[str, GpuHourPrice]:
    """`--gpu-hour-price "NAME=EUR"` arguments -> {name: price}."""
    prices = {}
    for value in values or []:
        name, _, eur = value.rpartition("=")
        try:
            rate = float(eur)
        except ValueError:
            rate = -1.0
        if not name.strip() or rate < 0:
            raise ValueError(f"Bad --gpu-hour-price '{value}': expected \"GPU NAME=EUR\", "
                             "e.g. \"NVIDIA H200 NVL=3.20\"")
        prices[name.strip()] = GpuHourPrice(rate, rate, rate)
    return prices


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
    group.add_argument("--gpu-hour-price", action="append", metavar="\"GPU NAME=EUR\"",
                       help="Price a GPU (named as nvidia-smi reports it) by the GPU-hour, e.g. a "
                            "cluster's internal rate; replaces the market rate for that GPU. Repeatable.")


def assumptions_from_args(args: argparse.Namespace) -> CostAssumptions:
    low, high = sorted(args.local_watts_range)
    try:
        overrides = parse_gpu_hour_prices(getattr(args, "gpu_hour_price", None))
    except ValueError as e:
        raise SystemExit(str(e))
    return CostAssumptions(
        # A site rate replaces the market rate for its GPU, however it's capitalised.
        gpu_hour_prices={
            **{name: price for name, price in default_gpu_hour_prices(args.usd_per_eur).items()
               if name.lower() not in {o.lower() for o in overrides}},
            **overrides,
        },
        gpu_hour_overridden=tuple(overrides),
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
    low/high band where the price is uncertain (equal to the estimate for
    API trials and measured energy)."""
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
    energy_wh = trials["energy_wh"] if "energy_wh" in trials else pd.Series(math.nan, index=trials.index)
    hardware = ref.settings.get("hardware") or {}
    gpus = hardware.get("gpus") or []
    gpu_rate = assumptions.gpu_hour_price(gpus)
    # A SLURM job on a GPU with no GPU-hour price isn't "my own machine":
    # household electricity would be the wrong price for it, so leave it
    # unpriced (compare_models warns) until --gpu-hour-price covers it.
    on_cluster = bool(hardware.get("slurm_job_id"))

    rows = []
    for i in trials.index:
        if provider[i] == "openai" and api_model[i] in OPENAI_PRICES_USD_PER_1M:
            cost = assumptions.api_eur(api_model[i], prompt[i], completion[i])
            rows.append((API, cost, cost, cost, math.nan))
        elif provider[i] == "llama.cpp" and gpu_rate is not None:
            hours = seconds[i] / 3600
            kwh = energy_wh[i] / 1000 if pd.notna(energy_wh[i]) else math.nan
            rows.append((GPU_HOURS, hours * gpu_rate.eur, hours * gpu_rate.low, hours * gpu_rate.high, kwh))
        elif provider[i] == "llama.cpp" and on_cluster:
            rows.append((UNPRICED, math.nan, math.nan, math.nan,
                         energy_wh[i] / 1000 if pd.notna(energy_wh[i]) else math.nan))
        elif provider[i] == "llama.cpp" and pd.notna(energy_wh[i]):
            kwh = energy_wh[i] / 1000
            cost = kwh * assumptions.eur_per_kwh
            rows.append((ELECTRICITY_MEASURED, cost, cost, cost, kwh))
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
    # GPU-hours are a resource count for any local run whose GPUs are known,
    # whatever it's priced by.
    gpu_count = len(gpus) if gpus else math.nan
    trials = trials.assign(provider=provider, api_model=api_model, gpus=gpu_count).join(costed)
    trials["gpu_hours"] = (seconds / 3600 * gpu_count).where(provider == "llama.cpp")
    return trials


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
            # Model time on the GPU(s), and how long the GPU(s) were held in
            # all - the rest is loading, compiling, testing and SonarQube,
            # which a cluster bills too but no model is responsible for.
            "gpu_hours": frame["gpu_hours"].sum(min_count=1) if "gpu_hours" in frame else math.nan,
            "allocated_gpu_hours": _allocated_gpu_hours(frame),
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


def _allocated_gpu_hours(frame: pd.DataFrame) -> float:
    if "rep_wall_time" not in frame or frame["gpus"].isna().all():
        return math.nan
    wall = frame.groupby("rep")["rep_wall_time"].first().sum(min_count=1)
    return wall / 3600 * frame["gpus"].iloc[0]


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
