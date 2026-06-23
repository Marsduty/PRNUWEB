from app.services.prnu_service import decide_database_matches, decide_external_match


def test_database_no_hit_message():
    result = decide_database_matches([{"name": "设备A", "pce": 60.0}], threshold=60)

    assert result["decision"] == "库中未检索到匹配设备"
    assert result["hits"] == []


def test_external_hit_message():
    result = decide_external_match(60.1, threshold=60)

    assert result["is_hit"] is True
