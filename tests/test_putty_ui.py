from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from prowrap_v2.reporting import report_pdf


def test_single_putty_override_is_per_defect_and_clear_returns_to_default():
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=20).run()
    app.button(key="example").click().run()
    field = app.number_input(key="case_putty_kg_per_repair")
    assert field.value is None
    assert "optional" in field.label
    app.number_input(key="case_quantity").set_value(4.0).run()
    app.number_input(key="case_zone_length_mm").set_value(400.0).run()
    app.button(key="calculate").click().run()
    result = app.session_state["calculation_results"][0]
    assert result["results"]["putty_kg"] == 12
    assert any("3.000 kg per defect × 4" in c.value for c in app.caption)
    app.number_input(key="case_putty_kg_per_repair").set_value(5.5).run()
    assert not app.metric
    app.button(key="calculate").click().run()
    result = app.session_state["calculation_results"][0]
    assert result["results"]["putty_kg"] == 22
    text = " ".join(page.extract_text() for page in PdfReader(BytesIO(report_pdf(result))).pages)
    assert "Putty per defect [kg]: 5.5" in text
    assert "Putty total [kg]: 22" in text
    app.number_input(key="case_putty_kg_per_repair").set_value(0.0).run()
    app.button(key="calculate").click().run()
    assert app.session_state["calculation_results"][0]["results"]["putty_kg"] == 0
    app.number_input(key="case_putty_kg_per_repair").set_value(None).run()
    app.button(key="calculate").click().run()
    assert app.session_state["calculation_results"][0]["results"]["putty_kg"] == 12
    assert not app.exception
