"""Band counts must describe every ply; width metres must reconcile to fabric area."""
from io import BytesIO
from math import pi
from pathlib import Path

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from prowrap_v2.batch import process_workbook
from prowrap_v2.procurement import quantities
from prowrap_v2.reporting import report_json, report_pdf
from test_weighted_batch import weighted_workbook


@pytest.mark.parametrize('widths,length,n500,n300', [
    ('300 and 500', 750, 20, 20), ('500', 450, 20, 0), ('300', 250, 0, 20),
])
def test_band_counts_include_plies_and_quantity_once(widths, length, n500, n300):
    case = dict(cloth_widths=widths, quantity=2, od_mm=1000,
                mechanism='Corrosion', defect_length_mm=200)
    result = quantities(case, length, 10, 10)
    assert result['count_500'] == n500
    assert result['count_300'] == n300
    assert result['fabric_length_500_m'] == pytest.approx(n500 * 1.01 * pi)
    assert result['fabric_length_300_m'] == pytest.approx(n300 * 1.01 * pi)
    assert result['fabric_area_m2'] == pytest.approx((n500 * .5 + n300 * .3) * 1.01 * pi)
    assert result['laminate_epoxy_kg'] == pytest.approx(1.5 * result['fabric_area_m2'])
    assert result['repair_area_m2'] == pytest.approx(2 * pi * length / 1000)
    assert result['primer_kg'] == pytest.approx(pi * length / 1000)
    assert result['putty_kg'] == 4


def test_weighted_export_includes_all_plies_without_rounding_population_shares():
    output, results = process_workbook(weighted_workbook())
    book = load_workbook(BytesIO(output), data_only=True)
    # Three 12-ply repairs with one band of each width, plus two 12-ply repairs
    # with three 300 mm bands: 36 wide and 108 narrow single-ply bands.
    total = dict(zip((c.value for c in book['Tender Takeoff'][4]),
                     (c.value for c in book['Tender Takeoff'][5])))
    assert total['500 mm bands · all plies'] == 36
    assert total['300 mm bands · all plies'] == 108
    assert total['500 mm fabric [m]'] == pytest.approx(36 * .36556 * pi)
    assert total['300 mm fabric [m]'] == pytest.approx(108 * .36556 * pi)
    assert total['Fabric [m²]'] == pytest.approx(57.88140676649275)
    assert total['Offered putty [1 kg kits]'] == 16
    # Fractional equivalent counts are estimates, not rounded physical orders.
    fractional, _ = process_workbook(weighted_workbook(shares=(.61, .39)))
    f = load_workbook(BytesIO(fractional), data_only=True)['Tender Takeoff']
    assert f['H5'].value == pytest.approx(36.6)
    for result, row in zip(results, book['Unit Results'].iter_rows(min_row=5, values_only=True)):
        headers = [c.value for c in book['Unit Results'][4]]
        exported = dict(zip(headers, row))
        assert exported['500 mm bands · all plies'] == result['results']['count_500']
        assert exported['300 mm fabric [m]'] == pytest.approx(result['results']['fabric_length_300_m'])


def test_failed_weighted_export_does_not_publish_partial_band_totals():
    output, _ = process_workbook(weighted_workbook(failed=True))
    book = load_workbook(BytesIO(output), data_only=True)
    assert book['Tender Takeoff']['H5'].value is None
    assert book['Tender Takeoff']['J5'].value is None


def test_single_app_and_pdf_show_all_ply_counts_and_width_metres():
    app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py'), default_timeout=20).run()
    app.button(key='example').click().run()
    app.number_input(key='case_quantity').set_value(3.0).run()
    app.button(key='calculate').click().run()
    assert not app.exception
    result = app.session_state['calculation_results'][0]
    metrics = {m.label: m.value for m in app.metric}
    assert metrics['500 mm fabric length'] == f"{result['results']['fabric_length_500_m']:.2f} m"
    assert metrics['300 mm fabric length'] == f"{result['results']['fabric_length_300_m']:.2f} m"
    text = ' '.join(p.extract_text() for p in PdfReader(BytesIO(report_pdf(result))).pages)
    assert '500 mm fabric bands total (all plies)' in text
    assert '300 mm fabric length total [m]' in text


def test_batch_app_displays_weighted_width_metres_for_population():
    app = AppTest.from_file(str(Path(__file__).parents[1] / 'batch_app.py'), default_timeout=20).run()
    app.get('file_uploader')[0].upload('weighted.xlsx', weighted_workbook()).run()
    app.button[0].click().run()
    assert not app.exception
    tables = [item.value for item in app.dataframe]
    procurement = next(t for t in tables if '500 mm fabric [m]' in t.columns)
    total = procurement[procurement['Scope'] == 'All repairs'].iloc[0]
    assert total['Repairs'] == 5
    assert total['500 mm bands · all plies'] == 36
    assert total['500 mm fabric [m]'] == pytest.approx(36 * .36556 * pi)


def test_single_app_discards_results_from_previous_reporting_schema():
    app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py'), default_timeout=20).run()
    app.button(key='example').click().run()
    app.button(key='calculate').click().run()
    stale = app.session_state['calculation_results']
    for record in stale:
        for key in ('fabric_length_500_m', 'fabric_length_300_m'):
            record['results'].pop(key, None)
    app.session_state['calculation_results'] = stale
    app.session_state['result_standard'] = 'ISO 24817:2017'
    app.session_state['result_reporting'] = None
    app.run()
    assert not app.exception
    assert not app.metric


def test_batch_app_discards_previous_reporting_schema_export():
    from hashlib import sha256
    content = weighted_workbook()
    app = AppTest.from_file(str(Path(__file__).parents[1] / 'batch_app.py'), default_timeout=20).run()
    app.get('file_uploader')[0].upload('weighted.xlsx', content).run()
    app.button[0].click().run()
    session = app.session_state['batch_upload']
    session['key'] = ('ISO 24817:2017', sha256(content).hexdigest())
    app.session_state['batch_upload'] = session
    app.run()
    assert not app.exception
    assert [node.label for node in app.get('download_button')] == ['Download Excel template']


@pytest.mark.parametrize('entrypoint', ['app.py', 'batch_app.py'])
def test_entrypoints_accept_package_initializer_cached_before_reporting_release(monkeypatch, entrypoint):
    import prowrap_v2
    # Streamlit can retain the already imported package namespace on hot reload.
    monkeypatch.delattr(prowrap_v2, 'PROCUREMENT_REPORT_VERSION', raising=False)
    app = AppTest.from_file(str(Path(__file__).parents[1] / entrypoint), default_timeout=20).run()
    assert not app.exception
