"""Batch dent records retain entered values and export effective assessed capacity."""
from io import BytesIO

import pytest
from openpyxl import load_workbook

from prowrap_v2.batch import template_workbook, prepare_workbook, calculate_batch
from test_engine import valid_case
from test_pressure_batch import pack, put_row, set_setup


def dent_workbook():
    book = load_workbook(BytesIO(template_workbook()))
    case = valid_case()
    case.pop('repair_id')
    case.update(mechanism='Dent no-crack', remaining_wall_mm=10, dent_depth_mm=10,
                dent_mawp_bar=30, dent_ffs_ref='Dent assessment', no_crack_confirmed=True,
                original_design_factor=.72, substrate_route='Full laminate',
                ffs_method='Modified B31G', b31g_safety_factor=2)
    set_setup(book, **case)
    put_row(book, 'Repair Cases', 5, repair_id='DENT')
    return book


def test_legacy_full_laminate_dent_exports_normalized_capacity_and_origins():
    batch = prepare_workbook(pack(dent_workbook()))
    output, results = calculate_batch(batch)
    assert results[0]['status'] == 'CALCULATED', results[0]['issues']
    book = load_workbook(BytesIO(output))
    rows = {(row[0], row[2]): (row[3], row[4])
            for row in book['Effective Inputs'].iter_rows(min_row=5, values_only=True)}
    assert rows['DENT', 'Substrate design route'][0] == 'Substrate stress limit'
    assert '9.10' in rows['DENT', 'Substrate design route'][1]
    assert rows['DENT', 'Remaining capacity assessment'][0] == 'External assessment'
    assert rows['DENT', 'Assessed impaired-pipe MAWP [bar]'][0] == 30
    assert rows['DENT', 'Allowable substrate stress [MPa]'] == (257.76, 'SMYS × original design factor')
    assert rows['DENT', 'Remaining-pipe Ps [bar]'] == (30, 'Assessed dent MAWP')
    assert rows['DENT', 'Entered Substrate design route'][0] == 'Full laminate'
    assert rows['DENT', 'Entered Remaining capacity assessment'][0] == 'Modified B31G'
    assert rows['DENT', 'Entered B31G assessment safety factor'][0] == 2
    assert ('DENT', 'B31G safety factor used') not in rows
    assert batch.repairs[0].case['substrate_route'] == 'Full laminate'
    assert batch.repairs[0].case['allowable_stress_mpa'] is None


def test_population_geometry_does_not_replace_capacity_provenance():
    book = dent_workbook()
    set_setup(book, purpose='Estimate', dent_mode='60/40 population', quantity=5,
              allowable_stress_mpa=250)
    output, results = calculate_batch(prepare_workbook(pack(book)))
    assert [row['status'] for row in results] == ['ESTIMATE', 'ESTIMATE']
    sheet = load_workbook(BytesIO(output))['Effective Inputs']
    rows = {(row[0], row[2]): (row[3], row[4])
            for row in sheet.iter_rows(min_row=5, values_only=True)}
    for result in results:
        repair_id = result['repair_id']
        assert '9.10' in rows[repair_id, 'Substrate design route'][1]
        assert rows[repair_id, 'Assessed impaired-pipe MAWP [bar]'] == (30, 'Assessed dent MAWP')
        assert rows[repair_id, 'Allowable substrate stress [MPa]'] == (250, 'Manual allowable stress')
        assert rows[repair_id, 'Dent depth [mm]'][1] == '60/40 dent population'


@pytest.mark.parametrize('geometry', ['Measured', '60/40 population'])
def test_batch_dents_without_assessment_never_issue_quantities(geometry):
    book = dent_workbook()
    set_setup(book, purpose='Estimate', dent_mode=geometry, quantity=5,
              dent_mawp_bar=None, dent_ffs_ref=None)
    output, results = calculate_batch(prepare_workbook(pack(book)))
    assert results and all(row['status'] == 'ENGINEERING_HOLD' for row in results)
    assert all(not row['results'] for row in results)
    sheet = load_workbook(BytesIO(output))['Results']
    assert all(all(value is None for value in row[7:])
               for row in sheet.iter_rows(min_row=5, values_only=True))

