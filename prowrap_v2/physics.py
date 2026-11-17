"""Pure ISO 24817:2017 calculation functions, MPa/N/mm internally.

Clause and equation references refer to ISO printed pages, not PDF offsets.
Route qualification, defect assessment and installation acceptance belong to engine.
"""
import math


def _number(value, name, minimum=None, positive=False):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a finite number')
    try:
        value=float(value)
    except (ValueError, TypeError):
        raise ValueError(f'{name} must be a finite number') from None
    if not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    if positive and value <= 0:
        raise ValueError(f'{name} must be positive')
    if minimum is not None and value < minimum:
        raise ValueError(f'{name} must be at least {minimum}')
    return value


def _n(data, key, **kw):
    return _number(data.get(key), key, **kw)


def _cyclic(case):
    """Clause 7.5.9.2, equations (25)–(27)."""
    if case.get('reversing_loads'):
        raise ValueError('Reversing loads require a separate cyclic assessment')
    if not case.get('cyclic'):
        return 1.
    n=_n(case,'cycles',minimum=0)
    low=_n(case,'cycle_min_bar',minimum=0)
    high=_n(case,'cycle_max_bar',positive=True)
    if low > high:
        raise ValueError('Cycle minimum exceeds maximum')
    if n <= 7000:
        return 1.
    ratio=low/high
    log_n=math.log10(min(n,150e6))
    log_start=math.log10(7000)
    span=math.log10(150e6)-log_start
    if ratio <= .4:
        return 1-.75*(log_n-log_start)/span
    slope=1.25*(ratio-1)/span
    return min(1.,1+slope*log_n-math.tan(slope)*log_start)


def _strain_and_factors(case, material, repair_type):
    """Clauses 7.5.3, 7.5.5, 7.5.6 and Tables 5–10.

    Both thermal extremes are checked using the maximum-temperature derating;
    this conservatively envelopes cold mismatch without relaxing hot design strain.
    """
    life=_n(case,'design_life_years',minimum=2)
    initial=_n(case,'initial_service_life_years',positive=True)
    klass=_n(case,'repair_class')
    if klass not in (1,2,3):
        raise ValueError('Repair class must be 1, 2 or 3')
    if initial>life:
        raise ValueError('Initial service life cannot exceed the design life')
    basis=case.get('strain_basis')
    if basis not in ('Default','LTS'):
        raise ValueError('Unknown allowable strain basis')
    temp=_n(case,'temperature_c')
    cold=_n(case,'min_temperature_c')
    install=_n(case,'install_temperature_c')
    if cold>temp:
        raise ValueError('Minimum temperature exceeds maximum temperature')
    margin=30 if repair_type=='B' and klass==3 and life>2 else 20
    maximum=_n(material,'tg_c')-margin
    if temp>maximum:
        raise ValueError(f'Design temperature exceeds {maximum:g} °C maximum')
    cure=case.get('cure_basis')
    if cure not in ('Report schedule','Confirmed qualified schedule'):
        raise ValueError('Unknown cure basis')
    factor_tm=maximum
    ambient=_n(material,'t_ambient_c',minimum=15)
    qualified=_n(material,'t_qualified_c')
    def derate(delta):
        return min(1.,62.5e-6*delta*delta+1.25e-3*delta+.7)
    f1=derate(factor_tm-temp)
    f2=derate(factor_tm-temp-(qualified-ambient))
    fc=_cyclic(case)
    ec=_n(material,'ec_mpa',positive=True)
    ea=_n(material,'ea_mpa',positive=True)
    coeff,power={1:(.004214,.01135),2:(.003634,.00813),3:(.003061,.0044)}[klass]
    e0c=coeff*10**(-power*life)
    e0a=e0c if ea>=.5*ec else (.002768*10**(-.0221*life) if klass==1 else .001)
    alpha_s=_n(case,'steel_cte')
    delta_c=alpha_s-_n(material,'alpha_c')
    delta_a=alpha_s-_n(material,'alpha_a')
    thermal_c=max((temp-install)*delta_c,(cold-install)*delta_c)
    thermal_a=max((temp-install)*delta_a,(cold-install)*delta_a)
    if basis=='Default' and material['short_term_hoop_failure_strain']<=.01:
        raise ValueError('Table 9 requires a hoop strain to failure greater than 1%')
    epsilon_c=fc*(f1*e0c-thermal_c)
    epsilon_a=fc*(f1*e0a-thermal_a)
    if basis=='LTS':
        route=material.get('lts_test_route','Design-life data')
        if route=='Design-life data':
            coeff,power={1:(1.0455,.00965),2:(.873,.00575),3:(.760,.00273)}[klass]
        elif route=='1000 h data':
            coeff,power={1:(.878,.0122),2:(.692,.007),3:(.612,.0043)}[klass]
        else:
            raise ValueError('Unknown performance test route')
        epsilon_c=fc*(coeff*10**(-power*life)*f2*_n(material,'lts',positive=True)-thermal_c)
    if epsilon_c<=0 or epsilon_a<=0:
        raise ValueError('Nonpositive design strain at a service temperature extreme')
    return dict(fc=fc,fT1=f1,fT2=f2,epsilon_c=epsilon_c,epsilon_a=epsilon_a,
                tm_c=maximum,factor_tm_c=factor_tm)


def _equivalent_loads(case, diameter, pressure):
    """Clause 7.5.4.1, equations (3) and (4)."""
    loads = []
    for key, factor in [('axial_kn', 1000), ('shear_kn', 1000),
                        ('bending_knm', 1e6), ('torsion_knm', 1e6)]:
        value = case.get(key)
        if value is None and case.get('load_basis') == 'Pressure-only confirmed':
            value = 0
        loads.append(abs(_number(value, key)) * factor)
    axial, shear, bending, torsion = loads
    area = math.pi * diameter**2 / 4
    shear_pressure = (shear + 2 * torsion / diameter) / area
    if pressure == 0 or pressure < shear_pressure:
        peq = pressure + shear_pressure
    else:
        peq = pressure * (1 + (shear_pressure / pressure)**2)
    feq = (area * pressure + math.hypot(axial, 2 * shear)
           + 4 * math.hypot(bending, torsion) / diameter)
    return peq, feq


def _live_hoop_thickness(driving, live, steel_stiffness, modulus, strain):
    """Solve equation (5) for the positive thickness root."""
    if driving <= 0:
        return 0.
    linear = strain * steel_stiffness + live - driving
    root = math.hypot(linear, 2 * math.sqrt(strain * driving * steel_stiffness))
    if linear >= 0:
        return 2 * driving * steel_stiffness / (modulus * (root + linear))
    return (root - linear) / (2 * strain * modulus)


def calculate_structural(case, material, repair_type, ps_mpa=0, fs_n=None):
    """Calculate structural thicknesses under clauses 7.5.4 and 7.5.5.

    The legacy fs_n argument is accepted for caller compatibility. This
    edition uses equivalent load from equation (4) as the axial load input.
    """
    if repair_type not in ('A', 'B'):
        raise ValueError('Repair type must be A or B')
    out = _strain_and_factors(case, material, repair_type)
    d = _n(case, 'od_mm', positive=True)
    p = _n(case, 'pressure_bar', minimum=0) / 10
    ec = _n(material, 'ec_mpa', positive=True)
    ea = _n(material, 'ea_mpa', positive=True)
    nu = _n(material, 'nu', minimum=0)
    if nu * nu * ea / ec >= 1:
        raise ValueError('Invalid orthotropic Poisson ratio')
    peq, feq = _equivalent_loads(case, d, p)
    ps = _number(ps_mpa, 'Substrate pressure capacity', minimum=0)
    route = 'Full laminate' if repair_type == 'B' else case.get('substrate_route')
    hoop_load = peq*d/2 + nu*feq/(math.pi*d)
    axial_load = feq/(math.pi*d*ea) - peq*d*nu/(2*ec)
    epsc, epsa = out['epsilon_c'], out['epsilon_a']
    if route == 'Substrate stress limit':
        es = _n(case, 'steel_modulus_mpa', positive=True)
        allowable = _n(case, 'allowable_stress_mpa', positive=True)
        hoop = es / (allowable * ec) * (hoop_load - ps*d/2)
        axial_t = es / allowable * (axial_load - ps*d/(2*ea))
        equations = '1/2'
    elif route == 'Substrate sharing':
        if case.get('sharing_basis') != 'Known allowable stress':
            raise ValueError('Select Known allowable stress for ISO 24817:2017 substrate sharing')
        live = _n(case, 'install_pressure_bar', minimum=0) * d / 20
        es = _n(case, 'steel_modulus_mpa', positive=True)
        ts = _n(case, 'remaining_wall_mm', positive=True)
        hoop = _live_hoop_thickness(hoop_load - ps*d/2, live, es*ts, ec, epsc)
        axial_t = axial_load / epsa
        equations = '5/6'
    elif route == 'Full laminate':
        hoop = hoop_load/(ec*epsc)
        axial_t = axial_load/epsa
        equations = '8/9'
    else:
        raise ValueError('Unknown substrate design route')
    out.update(peq_mpa=peq, feq_c_n=feq, feq_a_n=feq, hoop_mm=max(0.,hoop),
               axial_mm=max(0.,axial_t), structural_mm=max(0.,hoop,axial_t),
               route=route, equations=equations)
    if any(not math.isfinite(v) for v in out.values() if isinstance(v,(int,float))):
        raise ValueError('Nonfinite structural calculation result')
    return out


def bond_stress(case, material, installed_mm):
    """Clause 7.5.9.3, equation (29), signed interface stress in MPa.

    Compressive (negative) q is retained; only positive tension threatens disbond.
    Substrate thickness is actual remaining wall at installation, not EOL wall.
    """
    td=_number(installed_mm,'Installed thickness',positive=True)
    ec=_n(material,'ec_mpa',positive=True)
    es=_n(case,'steel_modulus_mpa',positive=True)
    ts=_n(case,'remaining_wall_mm',minimum=0)
    d=_n(case,'od_mm',positive=True)
    pin=_n(case,'install_pressure_bar',minimum=0)/10
    pmin=_n(case,'min_pressure_bar',minimum=0)/10
    install=_n(case,'install_temperature_c')
    cold=_n(case,'min_temperature_c'); hot=_n(case,'temperature_c')
    if cold>hot:
        raise ValueError('Minimum temperature exceeds maximum temperature')
    da=_n(case,'steel_cte')-_n(material,'alpha_c')
    thermal=max(da*(install-cold),da*(install-hot))
    result=(pin-pmin)*ec*td/(es*ts+ec*td)+thermal*2*ec*td/d
    return _number(result,'Bond stress')


def component_factor(component):
    """Clause 7.5.13.1, Table 11 for piping component stress factors."""
    try:
        return {'Straight':1.,'Bend':1.2,'Tee':2.,'Reducer':1.1,'Flange':1.1}[component]
    except (KeyError,TypeError):
        raise ValueError('Unknown component') from None


def tee_pressure_limit(case, material, epsilon_c, ps_mpa=0, installed_mm=None):
    """Clause 7.5.13.1, equation (33), based on installed laminate thickness."""
    d=_n(case,'run_od_mm',positive=True)
    branch=_n(case,'branch_od_mm',positive=True)
    td=_number(case.get('installed_thickness_mm') if installed_mm is None else installed_mm,
               'Installed thickness',positive=True)
    ec=_n(material,'ec_mpa',positive=True)
    strain=_number(epsilon_c,'Hoop design strain',positive=True)
    return _number(2*ec*strain*td/(d+branch),'Tee pressure limit',minimum=0)
