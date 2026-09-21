from relion_tree_layout import layout_positions


def test_layout_positions_single_chain_left_aligned_top_to_bottom():
    layers = [["Import/job001"], ["CtfFind/job002"], ["Class3D/job003"]]
    sizes = {j: (100, 30) for layer in layers for j in layer}
    pos = layout_positions(layers, sizes, col_gap=10, row_gap=5)
    assert pos["Import/job001"] == (0, 0)
    assert pos["CtfFind/job002"] == (0, 35)   # row_h(30) + row_gap(5)
    assert pos["Class3D/job003"] == (0, 70)


def test_layout_positions_siblings_grow_rightward_from_zero():
    layers = [["A"], ["B1", "B2", "B3"]]
    sizes = {"A": (100, 30), "B1": (100, 30), "B2": (100, 30), "B3": (100, 30)}
    pos = layout_positions(layers, sizes, col_gap=10, row_gap=0)
    assert pos["A"] == (0, 0)
    assert pos["B1"][0] == 0
    assert pos["B2"][0] == 110   # 100 + col_gap
    assert pos["B3"][0] == 220
    assert pos["B1"][1] == pos["B2"][1] == pos["B3"][1] == 30


def test_layout_positions_row_height_uses_tallest_card_and_centers_shorter_ones():
    layers = [["Short", "Tall"]]
    sizes = {"Short": (100, 20), "Tall": (100, 60)}
    pos = layout_positions(layers, sizes, col_gap=0, row_gap=0)
    # row height = 60 (tallest); "Short" (h=20) is vertically centered within it
    assert pos["Tall"][1] == 0
    assert pos["Short"][1] == 20  # (60 - 20) / 2


def test_layout_positions_empty():
    assert layout_positions([], {}) == {}
