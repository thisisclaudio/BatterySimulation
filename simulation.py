import pandas as pd
from battery import Battery


class Simulation:
    def __init__(self, battery: Battery, data: pd.DataFrame):
        self.battery = battery
        self.data = data.copy()
        self.results = None

    def run(self) -> pd.DataFrame:
        results = []

        for timestamp, row in self.data.iterrows():
            pv_prod = row["pv_prod"]
            grid_import = row["grid_import"]
            grid_export = row["grid_export"]

            charged_kwh = 0.0
            discharged_kwh = 0.0


            net_grid_energy = grid_export - grid_import

            if net_grid_energy > 0:
                charged_kwh = self.battery.charge(
                    power_w=net_grid_energy * 1000,
                    duration_h=1.0,
                )
            elif net_grid_energy < 0:
                discharged_kwh = self.battery.discharge(
                    power_w=-net_grid_energy * 1000,
                    duration_h=1.0,
                )

            net_grid_energy_after_battery = net_grid_energy - charged_kwh + discharged_kwh
            grid_import_after_battery = max(0, -net_grid_energy_after_battery)
            grid_export_after_battery = max(0, net_grid_energy_after_battery)

            results.append({
                "Zeit": timestamp,
                "pv_prod": pv_prod,
                "grid_import": grid_import,
                "grid_export": grid_export,
                "battery_charged_kwh": charged_kwh,
                "battery_discharged_kwh": discharged_kwh,
                "grid_import_after_battery": grid_import_after_battery,
                "grid_export_after_battery": grid_export_after_battery,
                "battery_soc": self.battery.soc,
            })


        
        self.results = pd.DataFrame(results).set_index("Zeit")
        return self.results


