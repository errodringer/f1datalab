from f1lab.sources import DemoSource
from f1lab.transform import normalize


def test_normalization_produces_deduplicated_results():
    frames = normalize(DemoSource().extract(2025), 2025)
    assert len(frames["races"]) == 3
    assert len(frames["results"]) == 15
    assert len(frames["standings"]) == 5
    assert frames["results"][["season", "round", "driver_id"]].duplicated().sum() == 0
    assert frames["results"]["points"].sum() == 240.0


def test_official_driver_standings_are_present():
    frames = normalize(DemoSource().extract(2025), 2025)
    assert frames["standings"].iloc[0]["position"] == 1
    assert frames["standings"].iloc[0]["points"] >= frames["standings"].iloc[1]["points"]
