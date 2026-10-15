"""Normalize Jolpica nested documents into typed, simple analytical tables."""

from __future__ import annotations

import pandas as pd

from .sources import Extracted


def _int(value, default=None):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _float(value, default=0.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _driver_name(driver: dict) -> str:
    return " ".join([driver.get("givenName", ""), driver.get("familyName", "")]).strip()


def normalize(source: Extracted, season: int) -> dict[str, pd.DataFrame]:
    race_rows = []
    for race in source.races:
        circuit = race.get("Circuit", {})
        loc = circuit.get("Location", {})
        race_rows.append({
            "season": season, "round": _int(race.get("round")),
            "race_name": race.get("raceName", ""), "race_date": race.get("date", ""),
            "circuit_id": circuit.get("circuitId", ""),
            "circuit": circuit.get("circuitName", ""), "country": loc.get("country", ""),
        })

    result_rows = []
    for race in source.result_races:
        for entry in race.get("Results", []):
            driver, team = entry.get("Driver", {}), entry.get("Constructor", {})
            result_rows.append({
                "season": season, "round": _int(race.get("round")),
                "race_name": race.get("raceName", ""), "race_date": race.get("date", ""),
                "driver_id": driver.get("driverId", ""), "driver": _driver_name(driver),
                "constructor_id": team.get("constructorId", ""), "constructor": team.get("name", ""),
                "grid": _int(entry.get("grid")), "position": _int(entry.get("position")),
                "points": _float(entry.get("points")), "status": entry.get("status", ""),
                "laps": _int(entry.get("laps")),
            })

    standing_rows = []
    last = source.standings[-1] if source.standings else {}
    for item in last.get("DriverStandings", []):
        driver = item.get("Driver", {})
        constructors = item.get("Constructors", [])
        standing_rows.append({
            "season": season, "position": _int(item.get("position")),
            "driver_id": driver.get("driverId", ""), "driver": _driver_name(driver),
            "team": ", ".join(c.get("name", "") for c in constructors),
            "points": _float(item.get("points")), "wins": _int(item.get("wins"), 0),
        })

    frames = {
        "races": pd.DataFrame(race_rows),
        "results": pd.DataFrame(result_rows),
        "standings": pd.DataFrame(standing_rows),
    }
    if frames["results"].empty:
        raise ValueError(f"No race results available for season {season}")
    if frames["results"].duplicated(subset=["season", "round", "driver_id"]).any():
        raise ValueError("Duplicate (season, round, driver_id) detected")
    if frames["races"].duplicated(subset=["season", "round"]).any():
        raise ValueError("Duplicate (season, round) detected in races")
    for name in frames:
        frames[name] = frames[name].sort_values(
            by=["round", "driver_id"] if name == "results" else
               ["round"] if name == "races" else ["position"],
            kind="stable", ignore_index=True,
        )
    return frames
