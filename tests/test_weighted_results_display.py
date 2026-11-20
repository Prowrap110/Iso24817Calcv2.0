"""Primary results must total the tender population, not one of each unit case."""
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

from prowrap_v2.batch import process_workbook
from test_weighted_batch import weighted_workbook


def test_primary_results_material_columns_sum_to_weighted_tender_total():
    output, raw = process_workbook(weighted_workbook())
    book = load_workbook(BytesIO(output), data_only=True)
    result = book['Results']
    assert sum(result.cell(r,15).value for r in (5,6)) == pytest.approx(57.88140676649275)
    assert sum(result.cell(r,19).value for r in (5,6)) == 5
    assert result['S4'].value == 'Equivalent repairs'
    assert result['M5'].value == 36
    assert result['M6'].value == 0
    assert result['N5'].value == 36
    assert result['N6'].value == 72
    # Per-repair engineering dimensions and unit putty stay unweighted.
    assert result['I5'].value == result['I6'].value == 12
    assert result['T5'].value == 2
    assert result['T6'].value == 3
    assert sum(result.cell(r,16).value for r in (5,6)) == pytest.approx(1.5*57.88140676649275)
    assert sum(result.cell(r,17).value for r in (5,6)) == 12
    # Raw evaluator records remain single repairs for single/batch comparison.
    assert [r['results']['quantity'] for r in raw] == [1,1]


def test_separate_unit_results_preserve_one_case_per_repair_without_weights():
    output, _ = process_workbook(weighted_workbook())
    book = load_workbook(BytesIO(output), data_only=True)
    unit = book['Unit Results']
    assert unit['O5'].value == pytest.approx(11.025029860284334)
    assert unit['O6'].value == pytest.approx(12.403158592819876)
    assert unit['S5'].value == unit['S6'].value == 1
    assert unit['M5'].value == 12
    assert unit['N6'].value == 36


def test_live_page_headline_reports_weighted_population_and_area():
    app = AppTest.from_file(str(Path(__file__).parents[1]/'batch_app.py'),default_timeout=20).run()
    app.get('file_uploader')[0].upload('weighted.xlsx',weighted_workbook()).run()
    app.button[0].click().run()
    assert not app.exception
    metrics = {m.label:m.value for m in app.metric}
    assert metrics['Weighted repairs'] == '5'
    assert metrics['Total fabric'] == '57.88 m²'
    assert metrics['Saturator'] == '86.82 kg'
