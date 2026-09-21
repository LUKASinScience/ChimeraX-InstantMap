from relion_export import history_rows, rows_to_csv, rows_to_markdown


def test_history_rows_shapes_one_dict_per_job():
    ordered = ["Import/job001", "Refine3D/job006"]
    job_artifacts = {"Refine3D/job006": {"state": "succeeded"}}
    job_parents = {"Refine3D/job006": {"Import/job001"}}
    job_stats = {"Refine3D/job006": {"resolution_angstrom": 22.996479, "n_particles": 2150}}

    rows = history_rows(ordered, job_artifacts, job_parents, job_stats)
    assert rows[0] == {
        "job": "Import/job001", "type": "Import", "state": "unknown",
        "parents": "", "resolution_angstrom": None, "n_particles": None,
    }
    assert rows[1] == {
        "job": "Refine3D/job006", "type": "Refine3D", "state": "succeeded",
        "parents": "Import/job001", "resolution_angstrom": 22.996479, "n_particles": 2150,
    }


def test_rows_to_csv_formats_numbers_and_header():
    rows = [{
        "job": "Refine3D/job006", "type": "Refine3D", "state": "succeeded",
        "parents": "Select/job004", "resolution_angstrom": 22.996479, "n_particles": 2150,
    }]
    csv_text = rows_to_csv(rows)
    lines = csv_text.strip().splitlines()
    assert lines[0] == "Job,Type,State,Parent(s),Resolution (Å),Particles"
    assert lines[1] == "Refine3D/job006,Refine3D,succeeded,Select/job004,23.0,2,150" \
        or lines[1] == 'Refine3D/job006,Refine3D,succeeded,Select/job004,23.0,"2,150"'


def test_rows_to_markdown_table_shape():
    rows = [{
        "job": "Import/job001", "type": "Import", "state": "unknown",
        "parents": "", "resolution_angstrom": None, "n_particles": None,
    }]
    md = rows_to_markdown(rows)
    lines = md.splitlines()
    assert lines[0] == "| Job | Type | State | Parent(s) | Resolution (Å) | Particles |"
    assert lines[1] == "|---|---|---|---|---|---|"
    assert lines[2] == "| Import/job001 | Import | unknown |  |  |  |"
