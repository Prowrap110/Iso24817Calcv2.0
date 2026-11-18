"""Weighted procurement from one evaluated repair per estimate scenario."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from math import ceil, fsum, isclose, isfinite

WEIGHTS = 'Estimate Weights'
HEADERS = (
    'Repair ID', 'Pipe group', 'Diameter [in]', 'Group repair quantity',
    'Scenario share', 'Group minimum putty [L]', 'Yield [L per 1 kg kit]',
    'Zone width basis', 'Zone width [mm]',
)

# Appended reporting fields preserve the existing material columns and calculations.
FABRIC_KEYS = ('count_500', 'count_300', 'fabric_length_500_m', 'fabric_length_300_m')
FABRIC_HEADERS = ('500 mm bands · all plies', '300 mm bands · all plies',
                  '500 mm fabric [m]', '300 mm fabric [m]')


@dataclass(frozen=True)
class Scenario:
    repair_id: str
    group: str
    diameter: float
    count: int
    share: float
    minimum_l: float
    yield_l: float
    width_basis: str | None
    width_mm: float | None

    @property
    def equivalent_repairs(self):
        return self.count * self.share


def read_weights(sheet, max_cases):
    if (sheet.max_row > max_cases + 4 or sheet.max_column != len(HEADERS)
            or tuple(cell.value for cell in sheet[4]) != HEADERS):
        raise ValueError('Estimate Weights headers or row count differ from the CalcBatch template.')
    scenarios = {}
    grouped = defaultdict(list)
    for index, cells in enumerate(sheet.iter_rows(min_row=5), 5):
        row = tuple(cell.value for cell in cells)
        if all(value is None for value in row):
            continue
        if any(cell.data_type == 'f' for cell in cells):
            raise ValueError(f'Estimate Weights row {index} requires values. Paste formulas as values.')
        repair, group, diameter, count, share, minimum, kit_yield, width_basis, width = row
        numbers = (diameter, count, share, minimum, kit_yield)
        if (not all(isinstance(x, str) and x.strip() for x in (repair, group))
                or not all(type(x) in (int, float) and isfinite(x) for x in numbers)
                or diameter <= 0 or not 1 <= count <= 1e9 or count != int(count)
                or not 0 < share <= 1 or minimum < 0 or kit_yield <= 0
                or (width_basis is not None and not isinstance(width_basis, str))
                or (width is not None and (type(width) not in (int, float) or not isfinite(width) or width <= 0))):
            raise ValueError(f'Check the estimate distribution and kit data at Estimate Weights row {index}.')
        key = repair.strip().casefold()
        if key in scenarios:
            raise ValueError(f'Duplicate weighted Repair ID at Estimate Weights row {index}.')
        scenario = Scenario(repair.strip(), group.strip(), diameter, int(count), share, minimum, kit_yield,
                            width_basis, width)
        scenarios[key] = scenario
        grouped[scenario.group].append(scenario)
    for group, cases in grouped.items():
        specs = {(case.diameter, case.count, case.minimum_l, case.yield_l) for case in cases}
        if len(specs) != 1 or not isclose(fsum(case.share for case in cases), 1, rel_tol=0, abs_tol=1e-9):
            raise ValueError(f'Estimate Weights needs consistent group data and shares totalling 100% for {group}.')
    return scenarios


def validate_repairs(weights, repairs):
    if not weights:
        return
    cases = {str(repair.case['repair_id']).strip().casefold(): repair.case for repair in repairs}
    if len(cases) != len(repairs) or cases.keys() != weights.keys():
        raise ValueError('Estimate Weights must list every Repair Cases ID exactly once.')
    groups = defaultdict(set)
    for key, case in cases.items():
        if case['purpose'] != 'Estimate' or case['quantity'] != 1 or (
            case['mechanism'] == 'Dent no-crack' and case['dent_mode'] == '60/40 population'
        ):
            raise ValueError('Weighted cases must be individual Estimate rows with Identical repairs = 1.')
        groups[weights[key].group].add((case['mechanism'], case['od_mm'], case['wall_mm'], case['material_grade']))
    if any(len(pipe_types) != 1 for pipe_types in groups.values()):
        raise ValueError('Each weighted pipe group must use the same mechanism, diameter, wall and grade.')


def takeoff(weights, results):
    grouped = defaultdict(list)
    scenarios = []
    for result in results:
        weight = weights[result['repair_id'].strip().casefold()]
        valid = result['status'] == 'ESTIMATE'
        values = tuple(weight.equivalent_repairs * result['results'][key] if valid else None for key in (
            'fabric_area_m2', 'laminate_epoxy_kg', 'putty_kg', *FABRIC_KEYS,
        ))
        grouped[weight.group].append((result['inputs']['mechanism'], weight, values))
        scenarios.append((weight.repair_id, weight.group, result['status'], weight.count, weight.share,
                          weight.equivalent_repairs, weight.width_basis, weight.width_mm, *values))
    if any(record[2] != 'ESTIMATE' for record in scenarios):
        return [], [], scenarios

    groups = []
    for group, rows in grouped.items():
        mechanism, weight, _ = rows[0]
        fabric, epoxy, putty = (fsum(values[i] for _, _, values in rows) for i in range(3))
        minimum_kits = ceil(Decimal(str(weight.minimum_l)) / Decimal(str(weight.yield_l)))
        # Apply one rounding step to the group's unrounded calculated mass.
        kits = max(ceil(round(putty, 10)), minimum_kits)
        band_totals = tuple(fsum(values[i] for _, _, values in rows) for i in range(3, 7))
        groups.append((group, mechanism, weight.diameter, weight.count, fabric, epoxy, putty,
                       weight.minimum_l, weight.yield_l, kits, kits * weight.yield_l,
                       fsum((epoxy, kits)), *band_totals))
    totals = []
    for label, entries in (
        ('All repairs', groups),
        *((name, [row for row in groups if row[1] == name]) for name in sorted({row[1] for row in groups})),
        *((f'{diameter:g} in', [row for row in groups if row[2] == diameter])
          for diameter in sorted({row[2] for row in groups})),
    ):
        repairs = sum(row[3] for row in entries)
        fabric, epoxy, putty, combined = (fsum(row[index] for row in entries) for index in (4, 5, 6, 11))
        kits = sum(row[9] for row in entries)
        band_totals = tuple(fsum(row[i] for row in entries) for i in range(12, 16))
        totals.append((label, repairs, fabric, epoxy, putty, kits, combined, *band_totals))
    return totals, groups, scenarios
