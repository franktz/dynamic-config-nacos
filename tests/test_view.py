from dynamic_config import Conf


def test_conf_supports_multiple_access_forms() -> None:
    conf = Conf({"a": {"b": [{"c": 123}]}})

    assert conf["a.b[0].c"] == 123
    assert conf.a.b[0].c == 123
    assert conf["a"]["b"][0]["c"] == 123
    assert conf.get("a.x", "fallback") == "fallback"
