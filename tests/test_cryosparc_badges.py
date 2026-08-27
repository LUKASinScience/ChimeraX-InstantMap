import pytest

from cryosparc_badges import cryosparc_badge

CASES = [
    ("cryosparc_P1_J42_class_00_view_dist.bild", "[bild]"),
    ("cryosparc_P1_J42_volume_map_half_A.mrc", "[half-map]"),
    ("cryosparc_P1_J42_volume_map_half_B.mrc", "[half-map]"),
    ("cryosparc_P1_J42_volume_map_half1.mrc", "[half-map]"),
    ("cryosparc_P1_J42_mask_fsc.mrc", "[mask]"),
    ("cryosparc_P1_J42_volume_map_sharp.mrc", "[volume:sharp]"),
    ("cryosparc_P1_J42_volume_map_filtered.mrc", "[volume:filtered]"),
    ("cryosparc_P1_J42_volume_map_raw.mrc", "[volume:raw]"),
    ("cryosparc_P1_J42_volume_map.mrc", "[volume]"),
]


@pytest.mark.parametrize("filename,expected", CASES)
def test_badge_classification(filename, expected):
    assert cryosparc_badge("/some/path/" + filename) == expected


def test_case_insensitive():
    assert cryosparc_badge("/path/CRYOSPARC_P1_J42_MASK.MRC") == "[mask]"


def test_badge_is_only_a_label_never_none_for_unmatched_volume():
    # An unrecognized .mrc still gets a badge (the generic volume fallback),
    # it's never filtered out — badges are advisory only.
    assert cryosparc_badge("/path/some_unrelated_output.mrc") == "[volume]"
