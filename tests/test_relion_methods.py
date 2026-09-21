from relion_methods import job_sentence, draft_methods_paragraph


def test_job_sentence_includes_symmetry_classes_and_diameter():
    sentence = job_sentence(
        "Refine3D/job006",
        {"sym_name": "C6", "particle_diameter": "350"},
        {"resolution_angstrom": 22.996479, "n_particles": 2150},
    )
    assert sentence == "Refine3D/job006 (C6 symmetry, 350 Å particle diameter) — 23.0 Å / 2,150 particles"


def test_job_sentence_omits_c1_symmetry_and_single_class():
    sentence = job_sentence(
        "Class3D/job001",
        {"sym_name": "C1", "nr_classes": "1"},
        {},
    )
    assert sentence == "Class3D/job001"


def test_job_sentence_includes_class_count_when_not_one():
    sentence = job_sentence("Class3D/job001", {"nr_classes": "4"}, {})
    assert sentence == "Class3D/job001 (4 classes)"


def test_job_sentence_handles_missing_options_and_stats():
    assert job_sentence("Import/job001", None, None) == "Import/job001"


def test_draft_methods_paragraph_one_line_per_job_in_order():
    ordered = ["Import/job001", "Refine3D/job006"]
    options = {"Refine3D/job006": {"sym_name": "C6"}}
    stats = {"Refine3D/job006": {"resolution_angstrom": 22.996479}}

    draft = draft_methods_paragraph(ordered, options, stats)
    assert draft == "Import/job001\nRefine3D/job006 (C6 symmetry) — 23.0 Å"
