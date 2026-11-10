import json
from io import BytesIO
from pypdf import PdfReader
from prowrap_v2.reporting import report_json, report_pdf

def test_failed_report_has_no_installation_schedule():
    value={'repair_id':'CASE-1','status':'NO_VALID_DESIGN','issues':['No finite sealing solution'], 'inputs':{'customer':'PROTAP','product':'PRW110+'},'results':{},'checks':[],'details':{'pressure_limit':float('inf')}}
    assert json.loads(report_json(value))['details']['pressure_limit'] is None
    pdf=report_pdf(value)
    text=' '.join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    assert 'No finite sealing solution' in text
    assert 'Installed plies' not in text
    assert 'Apply' not in text

def test_valid_report_preserves_results_and_escapes_unicode():
    value={'repair_id':'TEST-2','status':'CALCULATED','issues':[],'inputs':{'customer':'Müşteri','product':'PRW110+','temperature_c':60},'results':{'installed_plies':8,'installed_thickness_mm':6.64,'total_repair_length_mm':410},'checks':[{'name':'Thickness','passed':True,'value':6.64,'limit':25,'clause':'9.14.2'}],'details':{}}
    text=' '.join(p.extract_text() for p in PdfReader(BytesIO(report_pdf(value))).pages)
    assert 'Installed plies: 8' in text
    assert 'ISO 24817:2026' in text
    assert 'qualification' not in text.lower()


def test_single_app_and_batch_exports_use_quantity_scaled_materials_once():
    from pathlib import Path

    from openpyxl import load_workbook
    from streamlit.testing.v1 import AppTest

    from prowrap_v2.batch import process_workbook, template_workbook
    from prowrap_v2.examples import example_case

    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=20).run()
    app.button(key="example").click().run()
    app.number_input(key="case_quantity").set_value(3.0).run()
    app.button(key="calculate").click().run()
    assert not app.exception
    single = app.session_state["calculation_results"][0]
    assert single["status"] == "ESTIMATE"

    inputs = {**example_case(), "quantity": 3}
    workbook = load_workbook(BytesIO(template_workbook()))
    setup = workbook["Batch Setup"]
    for row in range(10, setup.max_row + 1):
        key = setup.cell(row, 3).value
        if key in inputs and inputs[key] not in (None, ""):
            setup.cell(row, 2, inputs[key])
    workbook["Repair Cases"]["A5"] = inputs["repair_id"]
    content = BytesIO()
    workbook.save(content)
    exported, [batch] = process_workbook(content.getvalue())

    assert single["results"] == batch["results"]
    assert single["checks"] == batch["checks"]
    assert json.loads(report_json(single))["results"]["quantity"] == 3
    pdf_text = " ".join(page.extract_text() for page in PdfReader(BytesIO(report_pdf(single))).pages)
    assert "Number of repairs: 3" in pdf_text
    area = single["results"]["fabric_area_m2"]
    assert f"Fabric area total [m2]: {area:.7g}" in pdf_text
    summary = load_workbook(BytesIO(exported), data_only=True)["Summary and Cost"]
    assert summary["C6"].value == 3
    assert abs(summary["D6"].value - area) < 1e-9
