"""ISO 24817:2017, §7.5.7 and §7.5.9.2 Type B sealing calculations.

Geometry is in mm, pressure and moduli in MPa, and gamma in N/mm
(0.001 times the Annex D value in J/m²).
"""
import math


_SERVICE_FACTORS = {1: (.83, .02088), 2: (.75, .01856), 3: (.666, .01584)}


def _positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name} must be finite and positive.')
    return value


def leak_factor(repair_class, life):
    """Return the default service factor from Formula (16)."""
    if isinstance(repair_class, bool) or repair_class not in _SERVICE_FACTORS:
        raise ValueError('Repair class must be 1, 2 or 3.')
    if _positive(life, 'Repair design lifetime') < 2:
        raise ValueError('Repair design lifetime must be at least 2 years under ISO 24817:2017 §7.3.')
    coefficient, exponent = _SERVICE_FACTORS[repair_class]
    return coefficient * 10 ** (-exponent * (life - 1))


def _invert_seal(pressure, factor, gamma, bending, shear, constant):
    """Invert the pressure relation with denominator a/t³ + b/t + c."""
    asymptote = factor * math.sqrt(gamma / constant)
    if pressure >= asymptote:
        return math.inf, asymptote

    target = gamma * (factor / pressure) ** 2 - constant
    if target <= 0:
        return math.inf, asymptote

    bending_thickness = (bending / target) ** (1 / 3)
    shear_thickness = shear / target
    if shear == 0:
        return bending_thickness, asymptote

    # The maximum and sum of the individual thicknesses bracket the root.
    low = max(bending_thickness, shear_thickness)
    high = bending_thickness + shear_thickness
    for _ in range(52):
        middle = low + (high - low) / 2
        if (bending_thickness / middle) ** 3 + shear_thickness / middle > 1:
            low = middle
        else:
            high = middle
    return high, asymptote


def solve_seal(case, material, fc, ft2):
    """Calculate minimum thickness for the caller's adopted Type B opening.

    Geometry allowance and rounding beyond the 15 mm recommendation are the
    caller's responsibility. Optional dimensions of a noncircular footprint
    are checked before use with the enclosing-circle equation.
    """
    od = _positive(case.get('od_mm'), 'Pipe outside diameter')
    wall = _positive(case.get('wall_mm'), 'Substrate wall thickness')
    pressure = _positive(case.get('pressure_bar'), 'Design pressure') / 10
    ec = _positive(material.get('ec_mpa'), 'Hoop modulus')
    ea = _positive(material.get('ea_mpa'), 'Axial modulus')
    combined_modulus = math.sqrt(ea * ec)
    shear_modulus = _positive(material.get('g_mpa'), 'Shear modulus')
    gamma = _positive(material.get('gamma_n_mm'), 'Annex D energy release rate')
    poisson = material.get('nu')
    if isinstance(poisson, bool) or not isinstance(poisson, (int, float)) or not -1 < poisson < 1:
        raise ValueError('Sealing Poisson ratio must be between -1 and 1.')

    repair_class = case.get('repair_class')
    service_factor = leak_factor(repair_class, case.get('design_life_years'))
    service_equation = 16
    degradation = material.get('leak_degradation_factor')
    if case.get('cyclic') and case['cycles'] > 7000:
        service_factor = .333 * _positive(fc, 'Cyclic strain derating factor')
        service_equation = 28
    elif degradation is not None:
        service_factor = _SERVICE_FACTORS[repair_class][0] * _positive(
            degradation, 'Qualified Annex G degradation factor'
        )
        service_equation = 17
    factor = _positive(
        _positive(ft2, 'Temperature derating factor') * service_factor,
        'Combined sealing derating factor',
    )

    shape = case.get('seal_shape')
    compliance = (1 - poisson ** 2) / combined_modulus
    if shape == 'Circular':
        size = max(15, _positive(case.get('effective_diameter_mm'), 'Effective defect diameter'))
        if size > math.sqrt(6 * od * wall):
            raise ValueError('Circular effective-opening geometry exceeds the limit of Formula (12).')
        axial = case.get('effective_axial_mm')
        circumferential = case.get('effective_circ_mm')
        if axial is not None or circumferential is not None:
            axial = _positive(axial, 'Axial footprint')
            circumferential = _positive(circumferential, 'Circumferential footprint')
            if max(axial, circumferential) / min(axial, circumferential) >= 5 or size < math.hypot(axial, circumferential):
                raise ValueError('Circular geometry must enclose the full footprint with aspect ratio below 5.')
        thickness, asymptote = _invert_seal(
            pressure, factor, gamma, compliance * 3 * size ** 4 / 512,
            3 * size ** 2 / (64 * shear_modulus), compliance * size / math.pi,
        )
        equation = 12
    elif shape == 'Circumferential slot':
        size = max(15, _positive(case.get('effective_axial_mm'), 'Effective axial slot width'))
        thickness, asymptote = _invert_seal(
            pressure, factor, gamma, compliance * size ** 4 / 24,
            3 * size ** 2 / (16 * shear_modulus) * (.8 + poisson / 2) / (1 + poisson),
            compliance * math.pi * size / 4,
        )
        full_circumference = (pressure * od / factor) ** 2 / (8 * combined_modulus * gamma)
        equation = 13
        # Clause 7.5.7 selects the smaller thickness from (13) and (14).
        if full_circumference < thickness:
            thickness, asymptote, equation = full_circumference, None, 14
    elif shape == 'Axial slot':
        size = max(15, _positive(case.get('effective_circ_mm'), 'Effective circumferential slot width'))
        angle = 2 * size / od
        if angle >= 1:
            raise ValueError('Axial slot angle must be below one radian for Formula (15).')
        # Formula (15) as corrected in 2018-01 has D⁴ in both bending terms.
        bending = compliance * od ** 4 * (
            angle ** 4 / 384 + (combined_modulus / (4 * shear_modulus) + 2) * angle ** 6 / 11520
        )
        thickness, asymptote = _invert_seal(
            pressure, factor, gamma, bending, 0, compliance * math.pi * od * angle / 8,
        )
        equation = 15
    else:
        raise ValueError('Unknown effective opening shape.')

    if not math.isfinite(thickness):
        raise ValueError(f'No finite sealing solution under Formula ({equation}).')
    return dict(
        seal_mm=thickness,
        equation=equation,
        asymptote_mpa=asymptote,
        f_leak=service_factor,
        f_leak_equation=service_equation,
        effective_size_mm=size,
    )
