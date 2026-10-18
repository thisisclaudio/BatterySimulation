import math
import numpy as np


class Battery:
    def __init__(
        self,
        capacity_kwh: float,
        efficiency_charging: float,
        efficiency_discharging: float,
        max_charging_power_w: float,
        max_discharging_power_w: float,
        min_soc: float = 0.0,
        max_soc: float = 1.0,
        initial_soc: float = 0.0,
    ):
        """
        Parameters
        ----------
        capacity_kwh : float
            Nominale Batteriekapazität in kWh.
        efficiency_charging : float
            Ladewirkungsgrad, z. B. 0.95 für 95 %.
        efficiency_discharging : float
            Entladewirkungsgrad, z. B. 0.95 für 95 %.
        max_charging_power_w : float
            Maximale Ladeleistung in W.
        max_discharging_power_w : float
            Maximale Entladeleistung in W.
        min_soc : float
            Minimaler Ladezustand als Anteil, z. B. 0.10 für 10 %.
        max_soc : float
            Maximaler Ladezustand als Anteil, z. B. 0.90 für 90 %.
        initial_soc : float
            Anfangsladezustand als Anteil, z. B. 0.50 für 50 %. Standard ist 0.0 (leer).
        """

        if capacity_kwh <= 0:
            raise ValueError("capacity_kwh must be positive")

        if not 0 < efficiency_charging <= 1:
            raise ValueError("efficiency_charging must be in (0, 1]")

        if not 0 < efficiency_discharging <= 1:
            raise ValueError("efficiency_discharging must be in (0, 1]")

        if max_charging_power_w < 0 or max_discharging_power_w < 0:
            raise ValueError("Power limits cannot be negative")

        if not 0 <= min_soc < max_soc <= 1:
            raise ValueError("SOC limits must satisfy 0 <= min_soc < max_soc <= 1")

        if not min_soc <= initial_soc <= max_soc:
            raise ValueError("initial_soc must be within SOC limits")

        self.capacity_kwh = capacity_kwh
        self.efficiency_charging = efficiency_charging
        self.efficiency_discharging = efficiency_discharging
        self.max_charging_power_w = max_charging_power_w
        self.max_discharging_power_w = max_discharging_power_w
        self.min_soc = min_soc
        self.max_soc = max_soc
        self.soc = initial_soc





    def charge(self, power_w: float, duration_h: float) -> float:
        if power_w < 0:
            raise ValueError("Charging power must be non-negative")
        if duration_h < 0:
            raise ValueError("Duration must be non-negative")

        power_w = min(power_w, self.max_charging_power_w)

        available_energy_kwh = (self.capacity_kwh * (self.max_soc - self.soc))

        input_kwh = power_w * duration_h / 1000
        stored_kwh = min(input_kwh * self.efficiency_charging, available_energy_kwh)

        consumed_kwh = stored_kwh / self.efficiency_charging

        #Calc new SoC
        self.soc = self.soc + stored_kwh / self.capacity_kwh


        return consumed_kwh


    def discharge(self, power_w: float, duration_h: float) -> float:
        if power_w < 0:
            raise ValueError("Discharging power must be non-negative")
        if duration_h < 0:
            raise ValueError("Duration must be non-negative")

        power_w = min(power_w, self.max_discharging_power_w)

        available_energy_kwh = (self.capacity_kwh * (self.soc - self.min_soc))

        output_kwh = power_w * duration_h / 1000
        delivered_kwh = min(output_kwh / self.efficiency_discharging, available_energy_kwh)

        #Calc new SoC
        self.soc = self.soc - delivered_kwh / self.capacity_kwh

        return delivered_kwh




    # Getter

    def get_soc(self) -> float:
        return self.soc

