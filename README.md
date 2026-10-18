# Battery Simulation

I have a PV system at home and wanted to know how much a home battery would
actually cut my grid imports before buying one. This project takes the real
hourly meter data from Home Assistant and replays it with a simulated battery
in between.

The idea is simple: whenever the house exported energy to the grid, the battery
tries to store it instead. Whenever the house imported from the grid, the
battery tries to cover it. At the end you get the import and export before and
after, plus some plots.

## How it works

- `ha-energy-export/export_energy.py` pulls hourly long-term statistics from
  Home Assistant (two inverters, grid import, grid export) and writes them to a
  CSV in `data/`.
- `data_fetcher.py` reads that CSV.
- `battery.py` is the battery model: capacity, charge/discharge efficiency,
  power limits and SOC limits.
- `simulation.py` goes through the data hour by hour and charges/discharges the
  battery.
- `analyse.py` prints a summary and plots SOC, import, export and battery flows.
- `main.py` ties it all together. This is where you set the battery parameters.

Since the input is the grid meter, self-consumption of the PV is already
included in the data. The battery only sees what would otherwise have gone to
or come from the grid.

## Setup

Python 3.9 or newer.

```
pip install -r requirements.txt
```

## Getting the data

Create a `.env` file in the project folder:

```
HA_URL=ws://homeassistant.local:8123/api/websocket
HA_TOKEN=your_long_lived_access_token
```

You can create the token in Home Assistant under your profile ->
Security -> Long-lived access tokens.

The sensor IDs and the time range are set at the top of
`ha-energy-export/export_energy.py`. Change them to match your setup, then run:

```
python ha-energy-export/export_energy.py
```

The CSV ends up in `data/`. CSV files and `.env` are ignored by git.

## Running the simulation

Set the path to the CSV and the battery parameters in `main.py`:

```python
battery = Battery(
    capacity_kwh=20.0,
    efficiency_charging=0.95,
    efficiency_discharging=0.95,
    max_charging_power_w=5000,
    max_discharging_power_w=5000,
    min_soc=0.10,
    max_soc=0.90,
    initial_soc=0.10,
)
```

Then:

```
python main.py
```

It prints something like this and opens the plots:

```
Netzbezug vorher:          4157.5 kWh
Netzbezug nachher:         2329.4 kWh
Reduktion Netzbezug:       1828.0 kWh (44.0 %)
...
```

To compare battery sizes, just change `capacity_kwh` and run it again.

## Comparing batteries in the web tool

There's also a small web app to compare several batteries side by side:

```
pip install -r requirements.txt
streamlit run app.py
```

It opens in the browser. You can enter up to 8 batteries in a table
(capacity, power, efficiency, SOC limits and optionally the price from an
offer), and set electricity prices and battery lifetime in the sidebar.

What you get:

- a short verdict which battery is the best value, plus a card per battery
  with import saved, savings per year and payback time
- a size curve that runs every capacity from 0 up to e.g. 30 kWh, so you can
  see where more capacity stops paying off
- grid import per month and an average day, before and after
- state of charge over a chosen week, and a heatmap of the whole period
- a table with all numbers, downloadable as CSV

The money part is simple: savings = avoided import × import price minus the
feed-in income you lose. Yearly values are scaled up from the data period, so
with data from January to July only, the yearly numbers are a guess. The
default prices and battery costs are placeholders, put in your own.

The logic behind the app lives in `comparison.py` and can be used from Python
directly as well.

## Limitations

Keep in mind it's a rough estimate, not a guarantee:

- The data is hourly. Short load peaks get averaged out, so the power limit
  rarely kicks in. In reality the battery would cover a bit less.
- Standby consumption and self-discharge of the battery are not modelled.
- If an hour has both import and export, the simulation assumes the import
  came first. That's slightly pessimistic.
- Battery aging is ignored.

So the real number is probably a bit lower than what the simulation says, but
in the same range.
