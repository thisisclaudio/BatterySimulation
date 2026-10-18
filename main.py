from data_fetcher import DataFetcher
from battery import Battery
from simulation import Simulation
from analyse import Analyser

DATA_PATH = "data/energiedaten_2026-01-01_bis_2026-08-01.csv"

fetcher = DataFetcher(DATA_PATH)
data = fetcher.fetch()

battery = Battery(
    capacity_kwh=20.0,
    efficiency_charging=0.95,
    efficiency_discharging=0.95,
    max_charging_power_w=5000,
    max_discharging_power_w=5000,
    min_soc=0.10,
    max_soc=0.90,
    initial_soc=0.90,
)

simulation = Simulation(battery=battery, data=data)
results = simulation.run()

print(results.head(n=20))

analyser = Analyser(results)
analyser.plot_all()