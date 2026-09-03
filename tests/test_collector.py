import pytest

from app.collector import CollectionBlocked, detect_access_block, fetch_offer_html, parse_offer_html, write_diagnostic


URL = "https://detail.1688.com/offer/605518859055.html?_t=1788338308253"


def test_detects_x5_challenge():
    assert detect_access_block("<script>var url='/_____tmd_____/punish?x5secdata=x'</script>") == "x5 anti-bot challenge"


def test_detects_login_wall():
    assert detect_access_block("<div>\u767b\u5f55\u67e5\u770b\u5168\u90e8\u89c4\u683c</div>") == "login required for full product data"


def test_incomplete_payload_is_never_exported_as_complete_product():
    with pytest.raises(CollectionBlocked, match="incomplete product payload"):
        parse_offer_html("<title>test - \u963f\u91cc\u5df4\u5df4</title>", URL)


def test_fetch_falls_back_to_mobile(monkeypatch):
    class Response:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    responses = iter([Response("/_____tmd_____/punish?x5secdata=x"), Response("<html>normal</html>")])

    class Session:
        def get(self, *args, **kwargs):
            return next(responses)

    monkeypatch.setattr("app.collector.requests.Session", Session)
    assert fetch_offer_html(URL) == "<html>normal</html>"


def test_diagnostic_preserves_observed_public_data(tmp_path):
    output = tmp_path / "605518859055.json"
    write_diagnostic(URL, output, "first", {"title": "observed"})
    data = write_diagnostic(URL, output, "second")
    assert data["observed_public_data"]["title"] == "observed"
    assert data["scheme_a_batch_suitable"] is False
