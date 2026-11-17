from streamlit.testing.v1 import AppTest
from pathlib import Path
APP = str(Path(__file__).resolve().parents[1] / 'app.py')

def test_single_app_initial_and_invalid_submit():
    at=AppTest.from_file(APP,default_timeout=20).run()
    assert not at.exception
    assert 'PROWRAP' in at.title[0].value
    at.button(key='calculate').click().run()
    assert not at.exception
    assert any('INPUT_ERROR' in x.value or 'input' in x.value.lower() for x in at.error)
    assert not at.metric

def test_example_submits_and_changes_clear_result():
    at=AppTest.from_file(APP,default_timeout=20).run()
    at.button(key='example').click().run()
    at.button(key='calculate').click().run()
    assert not at.exception
    assert at.metric
    at.number_input(key='case_pressure_bar').set_value(30.0).run()
    assert not at.metric


def test_switching_to_pressure_only_excludes_hidden_scalar_loads():
    at = AppTest.from_file(APP, default_timeout=20).run()
    at.button(key="example").click().run()
    at.selectbox(key="case_load_basis").set_value("Additional loads").run()
    at.number_input(key="case_axial_kn").set_value(10.0).run()
    at.selectbox(key="case_load_basis").set_value("Pressure-only confirmed").run()
    at.button(key="calculate").click().run()
    assert not at.exception
    assert at.metric
    result = at.session_state["calculation_results"][0]
    assert result["status"] == "ESTIMATE"
    assert result["inputs"]["axial_kn"] == 0


def test_linked_defect_displays_sealing_fields_and_keeps_one_row_across_reruns():
    at = AppTest.from_file(APP, default_timeout=20).run()
    at.button(key="example").click().run()
    at.selectbox(key="case_defect_mode").set_value("Measured individual").run()
    edit = {
        "edited_rows": {},
        "added_rows": [{
            "defect_id": "D-1", "length_mm": 10, "width_mm": 10,
            "remaining_wall_mm": 0.7, "separation_mm": 55,
        }],
        "deleted_rows": [],
    }
    at.session_state["defect_editor"] = edit
    at.run()
    assert not at.exception
    assert at.number_input(key="case_effective_diameter_mm")
    at.session_state["defect_editor"] = edit
    at.run()
    assert not at.exception
    assert [item["defect_id"] for item in at.session_state["defect_records"]] == ["D-1"]


def test_switching_from_measured_external_to_internal_corrosion_changes_defect_route():
    at = AppTest.from_file(APP, default_timeout=20).run()
    at.button(key="example").click().run()
    at.selectbox(key="case_defect_mode").set_value("Measured individual").run()
    at.selectbox(key="case_defect_location").set_value("Internal").run()
    at.button(key="calculate").click().run()
    assert not at.exception
    assert at.metric
    assert at.session_state["calculation_results"][0]["inputs"]["defect_mode"] == "Actual / combined"
