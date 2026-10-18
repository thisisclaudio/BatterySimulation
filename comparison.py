from dataclasses import dataclass

import numpy as np
import pandas as pd

from battery import Battery
from simulation import Simulation


@dataclass
class Scenario:
    name: str
    capacity_kwh: float
    charge_kw: float = 5.0
    discharge_kw: float = 5.0
    efficiency: float = 0.95
    min_soc: float = 0.10
    max_soc: float = 0.90
    price_chf: float | None = None

    def battery(self) -> Battery:
        return Battery(
            capacity_kwh=self.capacity_kwh,
            efficiency_charging=self.efficiency,
            efficiency_discharging=self.efficiency,
            max_charging_power_w=self.charge_kw * 1000,
            max_discharging_power_w=self.discharge_kw * 1000,
            min_soc=self.min_soc,
            max_soc=self.max_soc,
            # Start empty so stored energy isn't counted as savings
            initial_soc=self.min_soc,
        )


@dataclass
class Economics:
    import_price: float = 0.30      # CHF/kWh paid for grid import
    feed_in_price: float = 0.08     # CHF/kWh received for export
    cost_per_kwh: float = 600.0     # CHF per kWh capacity, used when no price is given
    fixed_cost: float = 2000.0      # CHF installation, used when no price is given
    lifetime_years: float = 15.0

    def battery_cost(self, scenario: Scenario) -> float:
        if scenario.price_chf is not None and not np.isnan(scenario.price_chf):
            return scenario.price_chf
        if scenario.capacity_kwh <= 0:
            return 0.0
        return self.fixed_cost + self.cost_per_kwh * scenario.capacity_kwh


def period_days(data: pd.DataFrame) -> float:
    if len(data) < 2:
        return len(data) / 24
    step = data.index.to_series().diff().median()
    return len(data) * step / pd.Timedelta(days=1)


def run_scenario(scenario: Scenario, data: pd.DataFrame) -> pd.DataFrame:
    return Simulation(battery=scenario.battery(), data=data).run()


def summarize(
    scenario: Scenario,
    results: pd.DataFrame,
    economics: Economics,
    days: float,
) -> dict:
    r = results
    import_before = r["grid_import"].sum()
    import_after = r["grid_import_after_battery"].sum()
    export_before = r["grid_export"].sum()
    export_after = r["grid_export_after_battery"].sum()
    charged = r["battery_charged_kwh"].sum()
    discharged = r["battery_discharged_kwh"].sum()

    # Consumption = PV used in the house + import. Missing PV hours are 0,
    # so clip to avoid negative consumption in those hours.
    consumption = (r["pv_prod"] - r["grid_export"] + r["grid_import"]).clip(lower=0).sum()

    usable_kwh = scenario.capacity_kwh * (scenario.max_soc - scenario.min_soc)
    drawn_kwh = discharged / scenario.efficiency
    cycles = drawn_kwh / usable_kwh if usable_kwh > 0 else 0.0

    eps = 1e-6
    empty = (r["battery_soc"] <= scenario.min_soc + eps) & (r["grid_import_after_battery"] > eps)
    full = (r["battery_soc"] >= scenario.max_soc - eps) & (r["grid_export_after_battery"] > eps)

    savings = (
        (import_before - import_after) * economics.import_price
        - (export_before - export_after) * economics.feed_in_price
    )
    per_year = 365 / days if days > 0 else 0.0
    savings_year = savings * per_year
    cost = economics.battery_cost(scenario)
    payback = cost / savings_year if savings_year > 0 else np.inf

    return {
        "name": scenario.name,
        "capacity_kwh": scenario.capacity_kwh,
        "usable_kwh": usable_kwh,
        "import_before_kwh": import_before,
        "import_after_kwh": import_after,
        "import_reduction_kwh": import_before - import_after,
        "import_reduction_pct": (import_before - import_after) / import_before * 100 if import_before else 0.0,
        "export_after_kwh": export_after,
        "battery_charged_kwh": charged,
        "battery_discharged_kwh": discharged,
        "self_sufficiency_before_pct": (1 - import_before / consumption) * 100 if consumption else 0.0,
        "self_sufficiency_after_pct": (1 - import_after / consumption) * 100 if consumption else 0.0,
        "cycles_per_year": cycles * per_year,
        "hours_empty_pct": empty.mean() * 100,
        "hours_full_pct": full.mean() * 100,
        "cost_chf": cost,
        "savings_chf_year": savings_year,
        "payback_years": payback,
        "net_benefit_chf": savings_year * economics.lifetime_years - cost,
    }


def compare(
    scenarios: list[Scenario],
    data: pd.DataFrame,
    economics: Economics,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    days = period_days(data)
    runs = {s.name: run_scenario(s, data) for s in scenarios}
    summary = pd.DataFrame([summarize(s, runs[s.name], economics, days) for s in scenarios])
    return summary, runs


def size_sweep(
    data: pd.DataFrame,
    economics: Economics,
    capacities: list[float],
    power_kw: float,
    c_rate: float | None,
    efficiency: float,
    min_soc: float,
    max_soc: float,
) -> pd.DataFrame:
    """Simulate a range of capacities. With c_rate set, power scales with capacity."""
    days = period_days(data)
    rows = []
    for cap in capacities:
        if cap <= 0:
            rows.append({
                "capacity_kwh": 0.0,
                "import_reduction_kwh": 0.0,
                "import_reduction_pct": 0.0,
                "savings_chf_year": 0.0,
                "cost_chf": 0.0,
                "net_benefit_chf": 0.0,
                "payback_years": np.inf,
            })
            continue
        power = cap * c_rate if c_rate else power_kw
        s = Scenario(f"{cap:g} kWh", cap, power, power, efficiency, min_soc, max_soc)
        summary = summarize(s, run_scenario(s, data), economics, days)
        rows.append({k: summary[k] for k in [
            "capacity_kwh", "import_reduction_kwh", "import_reduction_pct",
            "savings_chf_year", "cost_chf", "net_benefit_chf", "payback_years",
        ]})

    sweep = pd.DataFrame(rows)
    # Extra import reduction gained per additional kWh of capacity
    sweep["marginal_kwh_per_kwh"] = (
        sweep["import_reduction_kwh"].diff() / sweep["capacity_kwh"].diff()
    )
    return sweep


def monthly(runs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Grid import per month: one column for the baseline plus one per scenario."""
    first = next(iter(runs.values()))
    out = pd.DataFrame({"No battery": first["grid_import"]})
    for name, r in runs.items():
        out[name] = r["grid_import_after_battery"]
    index = out.index.tz_localize(None) if out.index.tz is not None else out.index
    return out.groupby(index.to_period("M")).sum()


def hourly_profile(runs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Average grid import per hour of day."""
    first = next(iter(runs.values()))
    out = pd.DataFrame({"No battery": first["grid_import"]})
    for name, r in runs.items():
        out[name] = r["grid_import_after_battery"]
    return out.groupby(out.index.hour).mean()
