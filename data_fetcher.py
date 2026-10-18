from pathlib import Path
import pandas as pd


class DataFetcher:
    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)

    def fetch(self) -> pd.DataFrame:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file '{self.csv_path}' not found.")

        raw = pd.read_csv(
            self.csv_path,
            parse_dates=["Zeit"],
            index_col="Zeit",
        )


        # TRANSFORM DATA INTO SIM INPUT FORMAT
        data = pd.DataFrame(index=raw.index)

        data["pv_prod"] = raw["WR1_kWh"].fillna(0) + raw["WR2_kWh"].fillna(0)

        data["grid_import"] = raw["Netzbezug_kWh"].fillna(0)
        data["grid_export"] = raw["Netzeinspeisung_kWh"].fillna(0)




        #Validation
        required_columns = ["pv_prod", "grid_import", "grid_export"]
        if data[required_columns].isna().any().any():
            raise ValueError("Energy data contains missing values.")

        if (data[required_columns] < 0).any().any():
            raise ValueError("Energy data contains negative energy values.")


        return data[required_columns].sort_index()
