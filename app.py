"""Battery comparison web tool. Start with: streamlit run app.py"""

from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from comparison import (
    Economics,
    Scenario,
    compare,
    hourly_profile,
    monthly,
    period_days,
    size_sweep,
)
from data_fetcher import DataFetcher

DATA_DIR = Path(__file__).parent / "data"

# Fixed categorical order (colorblind-validated). Color follows the battery's row.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
BASELINE = "#898781"
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"
GOOD = "#006300"
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
MAX_BATTERIES = len(SERIES)

DEFAULT_BATTERIES = pd.DataFrame([
    {"Name": "5 kWh", "Capacity (kWh)": 5.0, "Charge (kW)": 2.5, "Discharge (kW)": 2.5,
     "Efficiency (%)": 95.0, "Min SOC (%)": 10.0, "Max SOC (%)": 90.0, "Price (CHF)": None},
    {"Name": "10 kWh", "Capacity (kWh)": 10.0, "Charge (kW)": 5.0, "Discharge (kW)": 5.0,
     "Efficiency (%)": 95.0, "Min SOC (%)": 10.0, "Max SOC (%)": 90.0, "Price (CHF)": None},
    {"Name": "15 kWh", "Capacity (kWh)": 15.0, "Charge (kW)": 5.0, "Discharge (kW)": 5.0,
     "Efficiency (%)": 95.0, "Min SOC (%)": 10.0, "Max SOC (%)": 90.0, "Price (CHF)": None},
    {"Name": "20 kWh", "Capacity (kWh)": 20.0, "Charge (kW)": 5.0, "Discharge (kW)": 5.0,
     "Efficiency (%)": 95.0, "Min SOC (%)": 10.0, "Max SOC (%)": 90.0, "Price (CHF)": None},
]).astype({"Price (CHF)": float})


st.set_page_config(page_title="Battery Comparison", page_icon="🔋", layout="wide")

st.markdown(
    f"""
    <style>
      .block-container {{ padding-top: 2rem; max-width: 1400px; }}
      h1, h2, h3 {{ letter-spacing: -0.01em; }}
      [data-testid="stMetricValue"] {{ font-size: 1.6rem; }}
      .swatch {{ display: inline-block; width: 12px; height: 12px; border-radius: 3px;
                 margin-right: 8px; vertical-align: baseline; }}
      .card-title {{ font-weight: 600; font-size: 1.05rem; color: {INK}; }}
      .muted {{ color: {INK_2}; font-size: 0.9rem; }}
      .best {{ border-left: 4px solid {GOOD}; padding: 0.75rem 1rem; background: #f3f8f1;
               border-radius: 6px; margin-bottom: 1rem; color: {INK}; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- helpers ----------

def style(fig: go.Figure, height: int = 380, y_title: str = "", x_title: str = "") -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family=FONT, color=INK_2, size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
        hoverlabel=dict(bgcolor="white", font=dict(family=FONT, color=INK)),
        barcornerradius=4,
        bargap=0.25,
        bargroupgap=0.08,
    )
    fig.update_xaxes(title=x_title, gridcolor=GRID, linecolor=AXIS, tickfont=dict(color=MUTED),
                     zeroline=False, showline=True)
    fig.update_yaxes(title=y_title, gridcolor=GRID, linecolor=AXIS, tickfont=dict(color=MUTED),
                     zeroline=False, rangemode="tozero")
    return fig


def show(fig: go.Figure):
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


def color_of(names: list[str]) -> dict[str, str]:
    colors = {"No battery": BASELINE}
    colors.update({n: SERIES[i] for i, n in enumerate(names)})
    return colors


def swatch(color: str) -> str:
    return f'<span class="swatch" style="background:{color}"></span>'


def fmt_years(v: float) -> str:
    return "never" if not np.isfinite(v) or v > 99 else f"{v:.1f} years"


@st.cache_data(show_spinner=False)
def load_data(path: str, mtime: float) -> pd.DataFrame:
    return DataFetcher(path).fetch()


@st.cache_data(show_spinner="Simulating batteries…")
def run_compare(scenarios: list[Scenario], data: pd.DataFrame, economics: Economics):
    return compare(scenarios, data, economics)


@st.cache_data(show_spinner="Running size sweep…")
def run_sweep(data, economics, capacities, power_kw, c_rate, efficiency, min_soc, max_soc):
    return size_sweep(data, economics, capacities, power_kw, c_rate, efficiency, min_soc, max_soc)


def parse_batteries(table: pd.DataFrame) -> tuple[list[Scenario], list[str]]:
    scenarios, errors, seen = [], [], set()
    for i, row in table.reset_index(drop=True).iterrows():
        name = str(row["Name"]).strip() if pd.notna(row["Name"]) else ""
        if not name:
            if row.drop("Name").notna().any():
                errors.append(f"Row {i + 1}: missing name")
            continue
        if name in seen or name == "No battery":
            errors.append(f"{name}: name must be unique")
            continue
        try:
            price = row["Price (CHF)"]
            s = Scenario(
                name=name,
                capacity_kwh=float(row["Capacity (kWh)"]),
                charge_kw=float(row["Charge (kW)"]),
                discharge_kw=float(row["Discharge (kW)"]),
                efficiency=float(row["Efficiency (%)"]) / 100,
                min_soc=float(row["Min SOC (%)"]) / 100,
                max_soc=float(row["Max SOC (%)"]) / 100,
                price_chf=float(price) if pd.notna(price) else None,
            )
            s.battery()  # validates parameters
        except (TypeError, ValueError) as e:
            errors.append(f"{name}: {e}")
            continue
        seen.add(name)
        scenarios.append(s)
    if len(scenarios) > MAX_BATTERIES:
        errors.append(f"Only the first {MAX_BATTERIES} batteries are compared")
        scenarios = scenarios[:MAX_BATTERIES]
    return scenarios, errors


# ---------- sidebar ----------

with st.sidebar:
    st.header("Data")
    files = sorted(DATA_DIR.glob("*.csv"))
    if not files:
        st.error(f"No CSV files in {DATA_DIR}. Run the Home Assistant export first.")
        st.stop()
    data_file = st.selectbox("Energy data", files, format_func=lambda p: p.name)

    st.header("Prices")
    import_price = st.number_input("Grid import (CHF/kWh)", 0.0, 2.0, 0.30, 0.01, format="%.2f")
    feed_in_price = st.number_input("Feed-in tariff (CHF/kWh)", 0.0, 2.0, 0.08, 0.01, format="%.2f")
    lifetime = st.number_input("Battery lifetime (years)", 1, 40, 15)
    st.caption("Battery cost, used when a battery has no price of its own:")
    cost_per_kwh = st.number_input("Cost per kWh (CHF)", 0, 5000, 600, 50)
    fixed_cost = st.number_input("Fixed installation cost (CHF)", 0, 20000, 2000, 250)

    st.header("Size sweep")
    sweep_max = st.slider("Largest capacity (kWh)", 5, 60, 30, 5)
    sweep_step = st.select_slider("Step (kWh)", [0.5, 1.0, 2.0, 2.5, 5.0], value=1.0)
    scale_power = st.toggle("Power scales with capacity", value=True,
                            help="Bigger batteries usually come with more inverter power.")
    if scale_power:
        c_rate = st.slider("C-rate (kW per kWh)", 0.1, 1.0, 0.5, 0.05)
        sweep_power = 5.0
    else:
        c_rate = None
        sweep_power = st.number_input("Power (kW)", 0.5, 30.0, 5.0, 0.5)
    sweep_eff = st.slider("Efficiency (%)", 80, 100, 95) / 100
    sweep_soc = st.slider("SOC window (%)", 0, 100, (10, 90))

economics = Economics(import_price, feed_in_price, cost_per_kwh, fixed_cost, lifetime)
data = load_data(str(data_file), data_file.stat().st_mtime)
days = period_days(data)


# ---------- header & setup ----------

st.title("Battery Comparison")
st.markdown(
    f'<p class="muted">Replays {days:.0f} days of measured grid data '
    f"({data.index.min():%d.%m.%Y} – {data.index.max():%d.%m.%Y}) with different home batteries "
    f"and shows how much grid import each one saves. Yearly values are scaled up from this period.</p>",
    unsafe_allow_html=True,
)

st.subheader("Batteries")
st.caption(f"Add, remove or edit rows (up to {MAX_BATTERIES}). Leave the price empty to use the "
           "cost estimate from the sidebar.")
table = st.data_editor(
    DEFAULT_BATTERIES,
    num_rows="dynamic",
    width="stretch",
    hide_index=True,
    key="batteries",
    column_config={
        "Name": st.column_config.TextColumn(required=True),
        "Capacity (kWh)": st.column_config.NumberColumn(min_value=0.1, step=0.5, required=True),
        "Charge (kW)": st.column_config.NumberColumn(min_value=0.0, step=0.5, required=True),
        "Discharge (kW)": st.column_config.NumberColumn(min_value=0.0, step=0.5, required=True),
        "Efficiency (%)": st.column_config.NumberColumn(min_value=50.0, max_value=100.0, step=0.5,
                                                        required=True, help="One-way, applied to charge and discharge"),
        "Min SOC (%)": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=5.0, required=True),
        "Max SOC (%)": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=5.0, required=True),
        "Price (CHF)": st.column_config.NumberColumn(min_value=0.0, step=100.0, format="%.0f"),
    },
)

scenarios, errors = parse_batteries(table)
for e in errors:
    st.warning(e)
if not scenarios:
    st.info("Add at least one battery to compare.")
    st.stop()

summary, runs = run_compare(scenarios, data, economics)
names = [s.name for s in scenarios]
colors = color_of(names)
baseline_import = summary["import_before_kwh"].iloc[0]


# ---------- verdict & cards ----------

st.subheader("Results")

best_value = summary.loc[summary["net_benefit_chf"].idxmax()]
most_saved = summary.loc[summary["import_reduction_kwh"].idxmax()]
if best_value["net_benefit_chf"] > 0:
    verdict = (f"<b>Best value: {best_value['name']}</b>. It saves about "
               f"{best_value['savings_chf_year']:,.0f} CHF per year, pays for itself in "
               f"{fmt_years(best_value['payback_years'])} and leaves "
               f"{best_value['net_benefit_chf']:,.0f} CHF over {lifetime} years.")
else:
    verdict = (f"<b>None of these batteries pays for itself within {lifetime} years</b> at the "
               f"current prices. The closest is {best_value['name']}.")
if most_saved["name"] != best_value["name"]:
    verdict += (f" {most_saved['name']} cuts the most grid import "
                f"(−{most_saved['import_reduction_pct']:.0f} %), but the extra capacity costs more "
                f"than it saves.")
st.markdown(f'<div class="best">{verdict}</div>', unsafe_allow_html=True)

per_row = 4
for start in range(0, len(scenarios), per_row):
    cols = st.columns(per_row)
    for col, (_, row) in zip(cols, summary.iloc[start:start + per_row].iterrows()):
        with col.container(border=True):
            st.markdown(f'<div class="card-title">{swatch(colors[row["name"]])}{row["name"]}</div>',
                        unsafe_allow_html=True)
            st.metric("Grid import saved", f"{row['import_reduction_pct']:.1f} %",
                      f"-{row['import_reduction_kwh']:,.0f} kWh", delta_color="inverse")
            st.metric("Savings per year", f"{row['savings_chf_year']:,.0f} CHF")
            st.metric("Payback", fmt_years(row["payback_years"]))
            st.markdown(
                f'<p class="muted">Self-sufficiency {row["self_sufficiency_before_pct"]:.0f} % → '
                f'<b>{row["self_sufficiency_after_pct"]:.0f} %</b><br>'
                f'{row["cycles_per_year"]:.0f} full cycles / year · cost {row["cost_chf"]:,.0f} CHF</p>',
                unsafe_allow_html=True,
            )


# ---------- charts ----------

tab_overview, tab_size, tab_month, tab_day, tab_time, tab_heat, tab_table = st.tabs(
    ["Overview", "Size curve", "Monthly", "Daily profile", "Time series", "SOC heatmap", "Table"]
)

with tab_overview:
    left, right = st.columns(2)
    with left:
        st.markdown("**Grid import over the period**")
        labels = ["No battery", *names]
        values = [baseline_import, *summary["import_after_kwh"]]
        fig = go.Figure(go.Bar(
            x=values, y=labels, orientation="h",
            marker_color=[colors[n] for n in labels],
            text=[f"{v:,.0f} kWh" for v in values], textposition="outside",
            textfont=dict(color=INK_2), cliponaxis=False,
            hovertemplate="%{y}: %{x:,.0f} kWh<extra></extra>",
        ))
        style(fig, height=80 + 50 * len(labels), x_title="kWh")
        fig.update_yaxes(autorange="reversed", rangemode=None, showgrid=False)
        fig.update_xaxes(range=[0, max(values) * 1.3])
        show(fig)
    with right:
        st.markdown(f"**Net benefit over {lifetime} years**")
        values = summary["net_benefit_chf"]
        fig = go.Figure(go.Bar(
            x=values, y=names, orientation="h",
            marker_color=[colors[n] for n in names],
            text=[f"{v:,.0f} CHF" for v in values], textposition="outside",
            textfont=dict(color=INK_2), cliponaxis=False,
            customdata=np.stack([summary["savings_chf_year"], summary["cost_chf"]], axis=1),
            hovertemplate="%{y}<br>Net benefit %{x:,.0f} CHF<br>Savings %{customdata[0]:,.0f} CHF/yr"
                          "<br>Cost %{customdata[1]:,.0f} CHF<extra></extra>",
        ))
        style(fig, height=80 + 50 * (len(names) + 1), x_title="CHF")
        lo, hi = min(0, values.min()), max(0, values.max())
        pad = max(hi - lo, 1) * 0.3
        fig.update_xaxes(range=[lo - pad if lo < 0 else 0, hi + pad],
                         zeroline=True, zerolinecolor=AXIS, rangemode=None)
        fig.update_yaxes(autorange="reversed", rangemode=None, showgrid=False)
        show(fig)
    st.caption("Net benefit = yearly savings × lifetime − battery cost. Savings count avoided import "
               "minus the feed-in income you lose by storing instead of exporting.")

with tab_size:
    capacities = list(np.round(np.arange(0, sweep_max + sweep_step / 2, sweep_step), 2))
    sweep = run_sweep(data, economics, capacities, sweep_power, c_rate, sweep_eff,
                      sweep_soc[0] / 100, sweep_soc[1] / 100)
    power_note = f"{c_rate:g} kW per kWh" if c_rate else f"{sweep_power:g} kW"
    st.caption(f"Every capacity from 0 to {sweep_max} kWh, with {power_note} power, "
               f"{sweep_eff * 100:.0f} % efficiency and {sweep_soc[0]}–{sweep_soc[1]} % SOC window. "
               "Dots are your batteries from the table.")

    st.markdown("**Grid import saved vs. capacity**")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sweep["capacity_kwh"], y=sweep["import_reduction_pct"], mode="lines",
        line=dict(color=BASELINE, width=2), name="Size sweep",
        hovertemplate="%{x:g} kWh: −%{y:.1f} %<extra></extra>",
    ))
    for _, row in summary.iterrows():
        fig.add_trace(go.Scatter(
            x=[row["capacity_kwh"]], y=[row["import_reduction_pct"]], mode="markers",
            marker=dict(size=12, color=colors[row["name"]], line=dict(color=SURFACE, width=2)),
            name=row["name"],
            hovertemplate=f"{row['name']}: −%{{y:.1f}} %<extra></extra>",
        ))
    style(fig, x_title="Capacity (kWh)", y_title="Import saved (%)")
    fig.update_layout(hovermode="closest")
    show(fig)

    left, right = st.columns(2)
    with left:
        st.markdown(f"**Net benefit over {lifetime} years**")
        best_idx = sweep["net_benefit_chf"].idxmax()
        best = sweep.loc[best_idx]
        fig = go.Figure(go.Scatter(
            x=sweep["capacity_kwh"], y=sweep["net_benefit_chf"], mode="lines",
            line=dict(color=SERIES[0], width=2), name="Net benefit",
            hovertemplate="%{x:g} kWh: %{y:,.0f} CHF<extra></extra>",
        ))
        if best["net_benefit_chf"] > 0:
            fig.add_trace(go.Scatter(
                x=[best["capacity_kwh"]], y=[best["net_benefit_chf"]], mode="markers+text",
                marker=dict(size=12, color=SERIES[0], line=dict(color=SURFACE, width=2)),
                text=[f"best: {best['capacity_kwh']:g} kWh"], textposition="top center",
                textfont=dict(color=INK), hoverinfo="skip", showlegend=False,
            ))
        style(fig, height=340, x_title="Capacity (kWh)", y_title="CHF")
        fig.update_yaxes(rangemode="normal", zeroline=True, zerolinecolor=AXIS)
        fig.update_layout(showlegend=False)
        show(fig)
    with right:
        st.markdown("**Extra import saved per extra kWh of capacity**")
        m = sweep.dropna(subset=["marginal_kwh_per_kwh"])
        fig = go.Figure(go.Bar(
            x=m["capacity_kwh"], y=m["marginal_kwh_per_kwh"], marker_color=SERIES[0],
            hovertemplate="up to %{x:g} kWh: %{y:.1f} kWh saved per kWh added<extra></extra>",
        ))
        style(fig, height=340, x_title="Capacity (kWh)", y_title="kWh saved per kWh added")
        show(fig)
    st.caption("The right chart shows diminishing returns: once a bar gets small, more capacity "
               "barely helps because the battery is rarely emptied.")

with tab_month:
    st.markdown("**Grid import per month**")
    mon = monthly(runs)
    fig = go.Figure()
    for name in mon.columns:
        fig.add_trace(go.Bar(
            x=mon.index.strftime("%b %Y"), y=mon[name], name=name, marker_color=colors[name],
            hovertemplate=f"{name}: %{{y:,.0f}} kWh<extra></extra>",
        ))
    style(fig, height=420, y_title="kWh")
    fig.update_layout(barmode="group", hovermode="x unified")
    show(fig)
    st.caption("Winter months show the limit of any battery: there is little PV surplus to store.")

with tab_day:
    st.markdown("**Average grid import by hour of day**")
    prof = hourly_profile(runs)
    fig = go.Figure()
    for name in prof.columns:
        fig.add_trace(go.Scatter(
            x=prof.index, y=prof[name], name=name, mode="lines",
            line=dict(color=colors[name], width=2, dash="dot" if name == "No battery" else "solid"),
            hovertemplate=f"{name}: %{{y:.2f}} kWh<extra></extra>",
        ))
    style(fig, height=420, x_title="Hour of day", y_title="kWh per hour")
    fig.update_xaxes(tickmode="linear", dtick=2, range=[0, 23])
    fig.update_layout(hovermode="x unified")
    show(fig)

with tab_time:
    first_day = data.index.min().date()
    last_day = data.index.max().date()
    default_start = max(first_day, min(last_day - timedelta(days=7), first_day + timedelta(days=90)))
    picked = st.date_input("Period", (default_start, default_start + timedelta(days=7)),
                           min_value=first_day, max_value=last_day, format="DD.MM.YYYY")
    if isinstance(picked, (tuple, list)) and len(picked) == 2:
        start, end = picked
        idx_dates = data.index.date
        mask = (idx_dates >= start) & (idx_dates <= end)

        st.markdown("**State of charge**")
        fig = go.Figure()
        for name in names:
            r = runs[name][mask]
            fig.add_trace(go.Scatter(
                x=r.index, y=r["battery_soc"] * 100, name=name, mode="lines",
                line=dict(color=colors[name], width=2),
                hovertemplate=f"{name}: %{{y:.0f}} %<extra></extra>",
            ))
        style(fig, height=340, y_title="SOC (%)")
        fig.update_yaxes(range=[0, 100])
        fig.update_layout(hovermode="x unified")
        show(fig)

        st.markdown("**Grid import**")
        fig = go.Figure()
        base = runs[names[0]][mask]
        fig.add_trace(go.Scatter(
            x=base.index, y=base["grid_import"], name="No battery", mode="lines",
            line=dict(color=BASELINE, width=2, dash="dot"),
            hovertemplate="No battery: %{y:.2f} kWh<extra></extra>",
        ))
        for name in names:
            r = runs[name][mask]
            fig.add_trace(go.Scatter(
                x=r.index, y=r["grid_import_after_battery"], name=name, mode="lines",
                line=dict(color=colors[name], width=2),
                hovertemplate=f"{name}: %{{y:.2f}} kWh<extra></extra>",
            ))
        style(fig, height=340, y_title="kWh per hour")
        fig.update_layout(hovermode="x unified")
        show(fig)
    else:
        st.info("Pick a start and an end date.")

with tab_heat:
    pick = st.selectbox("Battery", names, key="heat_battery")
    r = runs[pick]
    picked_scenario = next(s for s in scenarios if s.name == pick)
    soc = r["battery_soc"] * 100
    index = soc.index.tz_localize(None) if soc.index.tz is not None else soc.index
    grid = (pd.DataFrame({"date": index.date, "hour": index.hour, "soc": soc.values})
            .pivot_table(index="hour", columns="date", values="soc", aggfunc="mean"))
    st.markdown(f"**State of charge of {pick}, every hour of the period**")
    fig = go.Figure(go.Heatmap(
        z=grid.values, x=grid.columns, y=grid.index,
        colorscale=[[i / (len(BLUE_RAMP) - 1), c] for i, c in enumerate(BLUE_RAMP)],
        zmin=picked_scenario.min_soc * 100, zmax=picked_scenario.max_soc * 100, xgap=1, ygap=1,
        colorbar=dict(title="SOC %", outlinewidth=0, thickness=12),
        hovertemplate="%{x|%d.%m.%Y} %{y}:00<br>SOC %{z:.0f} %<extra></extra>",
    ))
    style(fig, height=420, y_title="Hour of day")
    fig.update_yaxes(dtick=3, autorange="reversed", rangemode=None)
    fig.update_xaxes(showgrid=False)
    show(fig)
    s = summary.set_index("name").loc[pick]
    st.caption(
        f"Light = empty, dark = full. {pick} is empty while the house still needs power in "
        f"{s['hours_empty_pct']:.0f} % of all hours, and full while PV is still exported in "
        f"{s['hours_full_pct']:.0f} %. Lots of 'full' hours in summer and 'empty' hours in winter "
        "is normal; lots of 'full' hours all year means the battery is bigger than needed."
    )

with tab_table:
    view = summary.rename(columns={
        "name": "Battery",
        "capacity_kwh": "Capacity (kWh)",
        "usable_kwh": "Usable (kWh)",
        "import_after_kwh": "Import after (kWh)",
        "import_reduction_kwh": "Import saved (kWh)",
        "import_reduction_pct": "Import saved (%)",
        "export_after_kwh": "Export after (kWh)",
        "self_sufficiency_after_pct": "Self-sufficiency (%)",
        "cycles_per_year": "Cycles / year",
        "hours_empty_pct": "Hours empty (%)",
        "hours_full_pct": "Hours full (%)",
        "cost_chf": "Cost (CHF)",
        "savings_chf_year": "Savings / year (CHF)",
        "payback_years": "Payback (years)",
        "net_benefit_chf": f"Net benefit {lifetime} y (CHF)",
    }).drop(columns=["import_before_kwh", "battery_charged_kwh", "battery_discharged_kwh",
                     "self_sufficiency_before_pct"])
    view["Payback (years)"] = view["Payback (years)"].replace(np.inf, np.nan)
    st.dataframe(view.round(1), width="stretch", hide_index=True)
    st.download_button("Download as CSV", view.to_csv(index=False).encode("utf-8"),
                       "battery_comparison.csv", "text/csv")
    st.caption(
        f"Baseline grid import without battery: {baseline_import:,.0f} kWh. "
        "Self-sufficiency uses the PV data, which has some missing hours, so treat it as approximate."
    )
