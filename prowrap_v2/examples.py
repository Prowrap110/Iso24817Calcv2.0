"""Synthetic example, visibly separate from a real inspection/design record."""
from .schema import default_case

def example_case():
    c=default_case()
    c.update(repair_id='EXAMPLE-001',customer='Example only',project='Replace with project data',asset_id='Demo line',report_no='DEMO',inspection_ref='Demonstration inputs',material_grade='API 5L X52',design_code='ASME B31.8',od_mm=323.9,wall_mm=10.0,smys_mpa=359.0,smts_mpa=455.0,pressure_bar=20.0,min_pressure_bar=0.0,temperature_c=40.0,min_temperature_c=20.0,install_pressure_bar=0.0,install_temperature_c=20.0,defect_length_mm=100.0,defect_width_mm=30.0,zone_length_mm=100.0,remaining_wall_mm=5.0,growth_basis='No growth confirmed',growth_ref='Demonstration no-growth case',load_basis='Pressure-only confirmed',loads_ref='Demonstration pressure-only case',landing_mode='Unrestricted confirmed',cure_ref='Report 20 C / 24 h schedule',procedure_ref='Demonstration only',feasibility_ref='Demonstration only',purpose='Estimate',notes='Synthetic example. Replace the inputs before using for a project.')
    return c
