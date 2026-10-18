import matplotlib.pyplot as plt
import pandas as pd


class Analyser:
    def __init__(self, results: pd.DataFrame):
        self.results = results.copy()

    def plot_all(self):
        fig, axes = plt.subplots(
            nrows=4,
            ncols=1,
            figsize=(15, 12),
            sharex=True,
        )

        # 1. Battery state of charge
        axes[0].plot(
            self.results.index,
            self.results["battery_soc"] * 100,
            label="Battery SOC",
        )
        axes[0].set_ylabel("SOC (%)")
        axes[0].set_ylim(0, 100)
        axes[0].set_title("Battery Simulation")
        axes[0].grid(True)
        axes[0].legend()

        # 2. Grid import
        axes[1].plot(
            self.results.index,
            self.results["grid_import"],
            label="Before battery",
        )
        axes[1].plot(
            self.results.index,
            self.results["grid_import_after_battery"],
            label="After battery",
        )
        axes[1].set_ylabel("Import (kWh)")
        axes[1].grid(True)
        axes[1].legend()

        # 3. Grid export
        axes[2].plot(
            self.results.index,
            self.results["grid_export"],
            label="Before battery",
        )
        axes[2].plot(
            self.results.index,
            self.results["grid_export_after_battery"],
            label="After battery",
        )
        axes[2].set_ylabel("Export (kWh)")
        axes[2].grid(True)
        axes[2].legend()

        # 4. PV production and battery energy flows
        for column, label in [
            ("pv_prod", "PV production"),
            ("battery_charged_kwh", "Battery charging"),
            ("battery_discharged_kwh", "Battery discharging"),
        ]:
            axes[3].plot(
                self.results.index,
                self.results[column],
                label=label,
            )

        axes[3].set_ylabel("Energy (kWh)")
        axes[3].set_xlabel("Time")
        axes[3].grid(True)
        axes[3].legend()

        fig.tight_layout()
        plt.show()