from app.services.storage import build_object_key


def test_build_object_key_removes_windows_path_segments():
    key = build_object_key("reference", 1, "..\\bad\\image.png")

    assert key == "reference/1/image.png"
