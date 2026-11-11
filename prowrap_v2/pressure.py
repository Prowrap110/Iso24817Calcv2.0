"""Select the repair pressure demand without changing remaining-pipe capacity inputs."""
import math


def pressure_basis_details(case):
    basis = case.get('pressure_basis', 'Design pressure')
    if basis not in ('Design pressure', 'MAOP'):
        raise ValueError('Select Design pressure or MAOP as the calculation pressure basis.')
    for key,label in (('pressure_bar','Design pressure'), ('maop_bar','MAOP')):
        value = case.get(key)
        if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float))
                                  or not math.isfinite(value) or value <= 0):
            raise ValueError(f'{label} [bar] must be a finite positive number when entered.')
    selected = case.get('pressure_bar' if basis == 'Design pressure' else 'maop_bar')
    if selected is None:
        raise ValueError(f'Enter {basis} [bar] for the selected calculation pressure basis.')
    return dict(basis=basis, design_pressure_bar=case.get('pressure_bar'),
                maop_bar=case.get('maop_bar'), calculation_pressure_bar=selected)
