from pathlib import Path
import pandas as pd


TIMEZONE = "Europe/Zurich"


class DataFetcher:
    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)

    def fetch(self) -> pd.DataFrame:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file '{self.csv_path}' not found.")

        raw = pd.read_csv(self.csv_path, dtype={"Zeit": str})

        # Timestamps with UTC offset (new export) are unambiguous across DST;
        # older exports contain naive local times
        if raw["Zeit"].str.contains(r"[+-]\d{2}:?\d{2}$").any():
            raw["Zeit"] = pd.to_datetime(raw["Zeit"], utc=True).dt.tz_convert(TIMEZONE)
        else:
            raw["Zeit"] = pd.to_datetime(raw["Zeit"])
        raw = raw.set_index("Zeit")


        # TRANSFORM DATA INTO SIM INPUT FORMAT
        source_columns = ["WR1_kWh", "WR2_kWh", "Netzbezug_kWh", "Netzeinspeisung_kWh"]
        missing = raw[source_columns].isna().sum()
        if missing.any():
            print("Warning: missing values replaced with 0:")
            print(missing[missing > 0].to_string())

        data = pd.DataFrame(index=raw.index)

        data["pv_prod"] = raw["WR1_kWh"].fillna(0) + raw["WR2_kWh"].fillna(0)

        data["grid_import"] = raw["Netzbezug_kWh"].fillna(0)
        data["grid_export"] = raw["Netzeinspeisung_kWh"].fillna(0)


        #Validation
        required_columns = ["pv_prod", "grid_import", "grid_export"]
        if (data[required_columns] < 0).any().any():
            raise ValueError("Energy data contains negative energy values.")

        if data.index.duplicated().any():
            raise ValueError("Energy data contains duplicate timestamps.")


        return data[required_columns].sort_index()
