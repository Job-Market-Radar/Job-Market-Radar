import extract
from schema import Extraction


def counters():
    return {extract.MODEL: extract.new_usage(), extract.FALLBACK_MODEL: extract.new_usage()}


def test_routing_uses_cheap_model_when_it_works(monkeypatch):
    calls = []

    def fake(client, prompt, model, usage):
        calls.append(model)
        return "answer"

    monkeypatch.setattr(extract, "extract_with_retry", fake)
    assert extract.extract_routed(None, "prompt", counters()) == ("answer", extract.MODEL)
    assert calls == [extract.MODEL]


def test_routing_falls_back_when_cheap_model_fails(monkeypatch):
    calls = []

    def fake(client, prompt, model, usage):
        calls.append(model)
        return None if model == extract.MODEL else "answer"

    monkeypatch.setattr(extract, "extract_with_retry", fake)
    assert extract.extract_routed(None, "prompt", counters()) == ("answer", extract.FALLBACK_MODEL)
    assert calls == [extract.MODEL, extract.FALLBACK_MODEL]


def test_reversed_salary_is_put_in_order():
    answer = Extraction(
        skills=[], seniority="unknown", remote="unknown",
        salary_min=180000, salary_max=160000, currency="USD", salary_period="year",
    )
    assert (answer.salary_min, answer.salary_max) == (160000, 180000)