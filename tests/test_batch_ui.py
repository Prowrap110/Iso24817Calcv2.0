from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_batch_app_initial_download_and_upload_are_available():
    app = AppTest.from_file(str(Path(__file__).parents[1] / "batch_app.py")).run()
    assert not app.exception
    assert [node.label for node in app.get("download_button")] == ["Download Excel template"]
    assert len(app.get("file_uploader")) == 1
    assert not app.button


def test_upload_preview_calculate_and_replacement_clear_export():
    from io import BytesIO

    from openpyxl import load_workbook

    from prowrap_v2.batch import template_workbook

    workbook = load_workbook(BytesIO(template_workbook()))
    workbook["Repair Cases"]["A5"] = "NEEDS-DATA"
    content = BytesIO()
    workbook.save(content)

    app = AppTest.from_file(str(Path(__file__).parents[1] / "batch_app.py")).run()
    app.get("file_uploader")[0].upload("repairs.xlsx", content.getvalue()).run()
    assert not app.exception
    assert any("Preview and calculate" in item.value for item in app.subheader)
    assert len(app.get("download_button")) == 1

    app.button[0].click().run()
    assert not app.exception
    assert [node.label for node in app.get("download_button")] == [
        "Download Excel template", "Download results workbook",
    ]
    assert next(item.value for item in app.metric if item.label == "Require review") == "1"

    app.get("file_uploader")[0].upload("invalid.xlsx", b"not Excel").run()
    assert not app.exception
    assert app.error
    assert len(app.get("download_button")) == 1
