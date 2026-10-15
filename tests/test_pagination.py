from f1lab.sources import JolpicaSource


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class FakeSession:
    def __init__(self):
        self.offsets = []

    def get(self, url, params, timeout):
        offset = params["offset"]
        self.offsets.append(offset)
        result_rows = [
            {"Results": [{"Driver": {"driverId": "a"}}, {"Driver": {"driverId": "b"}}]},
            {"Results": [{"Driver": {"driverId": "c"}}]},
        ]
        races = [result_rows[0]] if offset == 0 else [result_rows[1]]
        return FakeResponse({"MRData": {"total": "3", "RaceTable": {"Races": races}}})


def test_results_pagination_counts_driver_results_not_races(monkeypatch):
    import f1lab.sources as module
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    api = JolpicaSource()
    session = FakeSession()
    api.session = session
    entries, raw_pages = api._pages(2025, "results", "RaceTable", "Races")
    assert session.offsets == [0, 2]
    assert len(entries) == 2
    assert len(raw_pages) == 2
