"""Owner-selected PROWRAP design profiles; source provenance is retained as data."""
from copy import deepcopy

_SHARED = dict(
    ply_mm=.83, ec_mpa=45460., ea_mpa=43800., nu=.066, g_mpa=2450.,
    alpha_c=10.34e-6, alpha_a=22.81e-6,
    lap_shear_mpa=14.76, longterm_lap_shear_mpa=9.63,
    lts=.007, gamma_n_mm=.250, min_typeb_plies=3,
    t_qualified_c=20., t_ambient_c=20.,
    lts_test_route='Design-life data',
    source='PRW110+ qualification report R5 Corrected; owner-selected design inputs',
    cure_temperature_c=20., cure_hours=24.,
)


def get_material(product):
    """Return an independent profile; PRW110 differs only by its supplied Tg basis."""
    if product not in ('PRW110+', 'PRW110'):
        raise ValueError('Unknown repair system')
    result=deepcopy(_SHARED)
    result.update(product=product, tg_c=104.73 if product=='PRW110+' else 78.18)
    return result
