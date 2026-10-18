import pandas as pd
from battery import Battery


class Simulation:
    def __init__(self, battery: Battery, data: pd.DataFrame):
        self.battery = battery
        self.data = data.copy()
        self.results = None

    def _timestep_h(self) -> float:
        # Typical spacing between rows; the median ignores DST jumps and single gaps
        if len(self.data) < 2:
            return 1.0
        return self.data.index.to_series().diff().median() / pd.Timedelta(hours=1)

    def run(self) -> pd.DataFrame:
        results = []
        duration_h = self._timestep_h()

        for timestamp, row in self.data.iterrows():
            pv_prod = row["pv_prod"]
            grid_import = row["grid_import"]
            grid_export = row["grid_export"]

            # Import and export are handled separately, because both can occur
            # within the same interval. Netting them would reduce imports even
            # without a battery. Discharging is applied first (conservative):
            # energy exported in this interval cannot cover its own imports.
            discharged_kwh = 0.0
            charged_kwh = 0.0

            if grid_import > 0:
                discharged_kwh = self.battery.discharge(
                    power_w=grid_import / duration_h * 1000,
                    duration_h=duration_h,
                )

            if grid_export > 0:
                charged_kwh = self.battery.charge(
                    power_w=grid_export / duration_h * 1000,
                    duration_h=duration_h,
                )

            grid_import_after_battery = max(0.0, grid_import - discharged_kwh)
            grid_export_after_battery = max(0.0, grid_export - charged_kwh)

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
