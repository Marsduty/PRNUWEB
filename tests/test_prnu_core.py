import numpy as np
import pytest

from prnu_core.enhancers import dc
from prnu_core.fingerprint import get_fingerprint


def test_dc_processes_all_columns_for_non_square_reference():
    rng = np.random.default_rng(11)
    reference = rng.normal(size=(64, 80))

    result = dc(reference, patch_size=8)

    assert result.shape == reference.shape
    assert np.isfinite(result).all()
    assert not np.all(result[:, 64:] == 0)


def test_get_fingerprint_rejects_mismatched_image_shapes():
    rng = np.random.default_rng(12)
    first = rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8)
    second = rng.integers(0, 256, size=(80, 64, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match="same shape"):
        get_fingerprint([first, second])


def test_get_fingerprint_rejects_non_rgb_images():
    rng = np.random.default_rng(13)
    grayscale = rng.integers(0, 256, size=(64, 64), dtype=np.uint8)

    with pytest.raises(ValueError, match="RGB"):
        get_fingerprint([grayscale])


def test_matching_core_ncc_pce_and_ranking():
    from prnu_core.matching_core import ncc_score, pce_score, rank_references

    query = np.array([[1.0, 2.0], [3.0, 4.0]])
    same = query.copy()
    different = np.array([[4.0, 3.0], [2.0, 1.0]])

    assert ncc_score(query, same) == pytest.approx(1.0)
    assert ncc_score(query, different) < 0

    pce = pce_score(query, same)
    assert pce["pce"] > 0
    assert pce["peak"] > 0
    assert pce["peak_pos"] == [0, 0]
    assert all(type(value) is int for value in pce["peak_pos"])

    ranked = rank_references(query, {"same": same, "different": different}, top_k=2)
    assert ranked[0]["name"] == "same"
    assert ranked[0]["ncc"] == pytest.approx(1.0)


def test_prnu_core_package_exports_main_functions():
    from prnu_core import get_fingerprint, ncc_score, pce_score

    assert callable(get_fingerprint)
    assert callable(ncc_score)
    assert callable(pce_score)
