
import asyncio
import csv
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import websockets
from dotenv import load_dotenv

load_dotenv()

HA_URL = os.environ["HA_URL"]
HA_TOKEN = os.environ["HA_TOKEN"]

START = datetime(2026, 1, 1, 0, 0, tzinfo=ZoneInfo("Europe/Zurich"))
END = datetime(2026, 8, 1, 0, 0, tzinfo=ZoneInfo("Europe/Zurich"))

SENSORS = {
    "WR1_kWh": "sensor.sma_st_80_pv_gen_meter",
    "WR2_kWh": "sensor.sungrow_sg12rt_total_yield",
    "Netzbezug_kWh": "sensor.netznutzung_kwh",
    "Netzeinspeisung_kWh": "sensor.netzeinspeisung_kwh",
}


async def main():
    async with websockets.connect(
        HA_URL,
        max_size=None,
    ) as ws:
        # Authentifizierung
        greeting = json.loads(await ws.recv())
        if greeting.get("type") != "auth_required":
            raise RuntimeError(f"Unerwartete Antwort: {greeting}")

        await ws.send(json.dumps({
            "type": "auth",
            "access_token": HA_TOKEN,
        }))

        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            raise RuntimeError("Home-Assistant-Authentifizierung fehlgeschlagen.")

        print("Mit Home Assistant verbunden.")

        # Langzeitstatistiken abfragen
        await ws.send(json.dumps({
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": START.isoformat(),
            "end_time": END.isoformat(),
            "period": "hour",
            "statistic_ids": list(SENSORS.values()),
            "types": ["change", "state", "sum"],
        }))

        while True:
            response = json.loads(await ws.recv())

            if response.get("id") != 1:
                continue

            if not response.get("success"):
                raise RuntimeError(
                    f"Statistikabfrage fehlgeschlagen: "
                    f"{response.get('error')}"
                )

            statistics = response["result"]
            break

    # Daten nach Stunde zusammenführen
    rows = {}

    for column, entity_id in SENSORS.items():
        entries = statistics.get(entity_id, [])
        print(f"{column}: {len(entries)} Statistikwerte")

        for entry in entries:
            # Statistik-Zeitstempel sind Unix-Zeitstempel in Millisekunden
            timestamp = datetime.fromtimestamp(
                entry["start"] / 1000,
                tz=ZoneInfo("UTC"),
            ).astimezone(ZoneInfo("Europe/Zurich"))

            if not (START <= timestamp < END):
                continue

            # Zeit mit UTC-Offset, damit die doppelte Stunde bei der
            # Zeitumstellung im Oktober nicht überschrieben wird
            # (Schlüssel in UTC: lokale Zeiten der doppelten Stunde gelten
            # in Python als gleich)
            row = rows.setdefault(
                entry["start"],
                {"Zeit": timestamp.isoformat(sep=" ")},
            )

            # Energieänderung während der Stunde, in kWh
            row[column] = entry.get("change")

    # CSV mit allen Stunden schreiben
    output_dir = Path(__file__).resolve().parent.parent / "data"
    output_dir.mkdir(exist_ok=True)
    output_file = (
        output_dir
        / f"energiedaten_{START:%Y-%m-%d}_bis_{END:%Y-%m-%d}.csv"
    )
    columns = ["Zeit", *SENSORS.keys()]

    with open(output_file, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()

        for key in sorted(rows):
            writer.writerow(rows[key])

    print(f"\nExport abgeschlossen: {output_file}")
    print(f"Stunden mit mindestens einem Datenpunkt: {len(rows)}")


if __name__ == "__main__":
    asyncio.run(main())
