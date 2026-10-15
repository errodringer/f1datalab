"""Jolpica Ergast-compatible API, with pagination across RESULT rows."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import settings

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://api.jolpi.ca/ergast/f1"


@dataclass
class Extracted:
    races: list[dict]
    result_races: list[dict]
    standings: list[dict]
    raw_pages: dict[str, list[dict]]
    mode: str = "LIVE"


class JolpicaSource:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = settings.user_agent
        self.session.mount("https://", HTTPAdapter(max_retries=Retry(
            total=4, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"], respect_retry_after_header=True,
        )))

    def _pages(self, season: int, endpoint: str, table: str, field: str):
        path = f"{BASE_URL}/{season}/{endpoint}/"
        offset = 0
        raw_pages = []
        all_entries = []
        while True:
            resp = self.session.get(path, params={"limit": 100, "offset": offset}, timeout=35)
            resp.raise_for_status()
            document = resp.json()
            raw_pages.append(document)
            metadata = document["MRData"]
            entries = metadata[table].get(field, [])
            all_entries.extend(entries)
            # For the results endpoint, `total` counts driver results, NOT race objects.
            received = sum(len(race.get("Results", [])) for race in entries) if endpoint == "results" else len(entries)
            total = int(metadata.get("total", 0))
            if received == 0:
                if offset < total:
                    raise ValueError(f"Inconsistent pagination for {endpoint}: {offset=} {total=}")
                break
            offset += received
            LOGGER.info("Jolpica %s: %d/%d", endpoint, offset, total)
            if offset >= total:
                break
            time.sleep(0.35)  # avoid hammering public API
        return all_entries, raw_pages

    def extract(self, season: int) -> Extracted:
        races, raw_races = self._pages(season, "races", "RaceTable", "Races")
        results, raw_results = self._pages(season, "results", "RaceTable", "Races")
        standings, raw_standings = self._pages(season, "driverstandings", "StandingsTable", "StandingsLists")
        if not races:
            raise ValueError(f"Jolpica returned no races for season {season}")
        return Extracted(races, results, standings, {
            "races": raw_races,
            "results": raw_results,
            "driverstandings": raw_standings,
        })


class DemoSource:
    """Clearly labelled fictional results for offline exploration only."""

    def extract(self, season: int) -> Extracted:
        drivers = [
            ("alvarez", "Lucía", "Alvarez", "meridian", "Meridian Racing"),
            ("chen", "Kai", "Chen", "meridian", "Meridian Racing"),
            ("silva", "Rafa", "Silva", "orbit", "Orbit Motorsport"),
            ("novak", "Mara", "Novak", "orbit", "Orbit Motorsport"),
            ("khan", "Amir", "Khan", "apex", "Apex GP"),
        ]
        races = []
        result_races = []
        totals = {d[0]: {"points": 0.0, "wins": 0} for d in drivers}
        for rnd, (name, circuit, country, date) in enumerate([
            ("Demo Grand Prix Norte", "Circuito Boreal", "Noruega", f"{season}-03-01"),
            ("Demo Grand Prix Costa", "Circuito Mar", "Portugal", f"{season}-03-15"),
            ("Demo Grand Prix Sierra", "Circuito Alto", "España", f"{season}-03-29"),
        ], 1):
            race = {"season": str(season), "round": str(rnd), "raceName": name, "date": date,
                    "Circuit": {"circuitId": f"demo-{rnd}", "circuitName": circuit,
                                "Location": {"locality": circuit, "country": country}}}
            races.append(race)
            race_results = []
            for i, index in enumerate([(0, 2, 1, 3, 4), (1, 0, 3, 2, 4), (2, 3, 0, 4, 1)][rnd - 1]):
                driver_id, given, family, team_id, team_name = drivers[index]
                points = [25.0, 18.0, 15.0, 12.0, 10.0][i]
                totals[driver_id]["points"] += points
                totals[driver_id]["wins"] += int(i == 0)
                race_results.append({"number": str(index + 1), "position": str(i + 1),
                                    "positionText": str(i + 1), "grid": str(index + 1), "points": str(points),
                                    "status": "Finished", "laps": "55",
                                    "Driver": {"driverId": driver_id, "givenName": given, "familyName": family},
                                    "Constructor": {"constructorId": team_id, "name": team_name}})
            result_races.append({**race, "Results": race_results})
        driver_standings = []
        for driver_id, given, family, team_id, team_name in drivers:
            stats = totals[driver_id]
            driver_standings.append({"points": str(stats["points"]), "wins": str(stats["wins"]),
                                     "Driver": {"driverId": driver_id, "givenName": given, "familyName": family},
                                     "Constructors": [{"constructorId": team_id, "name": team_name}]})
        driver_standings.sort(key=lambda x: float(x["points"]), reverse=True)
        for rank, item in enumerate(driver_standings, 1):
            item["position"] = str(rank)
        standings = [{"season": str(season), "round": "3", "DriverStandings": driver_standings}]
        raw = {
            "races": [{"MRData": {"RaceTable": {"Races": races}}}],
            "results": [{"MRData": {"RaceTable": {"Races": result_races}}}],
            "driverstandings": [{"MRData": {"StandingsTable": {"StandingsLists": standings}}}],
        }
        return Extracted(races, result_races, standings, raw, mode="DEMO (datos ficticios)")
