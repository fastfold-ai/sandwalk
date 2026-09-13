from agent_server import offline_mode as om


def test_get_ui_status_exposes_camel_case(monkeypatch):
    monkeypatch.setenv("SANDWALK_FORCE_OFFLINE", "1")
    om._last_check_time = None
    status = om.get_ui_status()
    assert status["isOffline"] is True
    assert status["is_offline"] is True
    assert status["featuresAffected"]
    assert status["features_affected"] == status["featuresAffected"]
    assert status["message"]


def test_tcp_probe_marks_offline_when_connect_fails(monkeypatch):
    monkeypatch.delenv("SANDWALK_FORCE_OFFLINE", raising=False)
    monkeypatch.setattr(om, "_tcp_reachable", lambda host, port, timeout=1.5: False)
    om._last_check_time = None
    om._offline = False
    assert om.is_offline() is True
    assert om.get_ui_status()["isOffline"] is True


def test_tcp_probe_marks_online_when_connect_works(monkeypatch):
    monkeypatch.delenv("SANDWALK_FORCE_OFFLINE", raising=False)
    monkeypatch.setattr(om, "_tcp_reachable", lambda host, port, timeout=1.5: True)
    om._last_check_time = None
    om._offline = True
    assert om.is_offline() is False
    assert om.get_ui_status()["isOffline"] is False
