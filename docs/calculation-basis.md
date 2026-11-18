# Calculation basis — v2.0.0

## Controlled sources

- ISO 24817:2017, supplied edition. SHA-256 `2d1e4d42bff3e4414fdbccd6f2782733e2e0a28e3a59abc7d1f9e3aec6aecc41`.
- PRW110+ Qualification Report, R5 Corrected, 66 pages. SHA-256 `586d89fdc36a52047ac482e7f6b0aad15ae859e4ec7b7f04dea852accfbb09d5`.
- PRW110 Final Report, 63 pages, used for the PRW110 Tg only. SHA-256 `085bf5b1c8735a6a8176ba5607b489529a3ad4842cb5e85be84dc84967d1fadb`.
- ASME B31G:2023, supplied copy, used only for the optional Modified B31G substrate-capacity calculation within its implemented limits.

The controlled source documents are held outside this repository.

## Material profile

| Property | Value |
| --- | ---: |
| Cured ply thickness | 0.83 mm |
| Circumferential tensile modulus | 45,460 MPa |
| Axial tensile modulus | 43,800 MPa |
| Poisson ratio | 0.066 |
| Circumferential thermal expansion | 10.34 × 10⁻⁶ /°C |
| Axial thermal expansion | 22.81 × 10⁻⁶ /°C |
| Short-term lap shear | 14.76 MPa |
| Long-term lap shear data | 9.63 MPa |
| PRW110+ Tg basis | 104.73°C, DMA storage-modulus onset |
| PRW110 Tg basis | 78.18°C, reported DSC second-heating value |
| Reference qualification / ambient temperature | 20°C / 20°C |
| Report cure schedule | 20°C minimum, 24 hours minimum |

PRW110 inherits the PRW110+ shared mechanical profile by the owner's explicit direction and uses its own recorded Tg.

## Thermal basis

The calculator treats the recorded product Tg as representative of the selected field cure for §7.5.3 temperature limits and factors. It uses Tg − 20°C except for Class 3 Type B with a design life over two years, which uses Tg − 30°C. The profile assumes a 20°C qualification and ambient test temperature and applies the maximum-temperature derating with the largest absolute thermal mismatch at the entered hot and cold service conditions. Equation (10) always deducts that mismatch from the allowable hoop and axial strains, including when installation is hotter than service. The separate signed interface-stress calculation in Equation (29) is unchanged.

The PRW110 value comes from DSC second-heating data, while the PRW110+ value uses DMA storage-modulus onset. Confirm that the reported Tg is applicable to the intended cure schedule and resulting laminate before issuing a repair design. An entered reference for a separately qualified cure schedule records the procedure and the calculation continues to use the profile Tg.

## Design inputs and qualification

The shared material profile uses the owner-selected 0.007 (0.7%) long-term strain, 250 J/m² (0.250 N/mm) sealing parameter, 2,450 MPa shear modulus in the required planes including G31, and a three-ply Type B floor. Use qualified data applicable to the repair system and case for an issued design.

The Table 9 default strain basis requires short-term strain to failure above 1%. The performance method in §7.5.6 uses an Annex E long-term strain basis. The 0.007 input supports conditional estimates. Its use for Design depends on verification of the qualifying Annex E test basis and value. Use the qualification reference field to record applicable Annex E evidence.

The Type A design floor in §7.5.14 is the greater of two layers and 2 mm. Type B estimates use the recorded system floor. Type B Design requires verified Annex D sealing and Annex F impact data for the repair system under §§7.5.7 and 7.5.9.1. The installed thickness is rounded up to whole plies and checked against the strict OD/12 limit of the implemented structural equations.

## Implementation map

| Calculation | Implementation |
| --- | --- |
| Classes, service, defect grouping, end-of-life condition and route gates | `engine.py` |
| Selected Design pressure / MAOP demand and pressure input validation | `pressure.py` |
| Load equivalents, strain, temperature and cyclic factors; structural equations | `physics.py` |
| Type B circular and slot sealing, finite-solution checks and governing capacities | `sealing.py` |
| Assessed substrate capacity and Modified B31G | `assessment.py` |
| Bond, fitting pressure cap, overlap, thickness and final acceptance | `physics.py`, `engine.py` |
| Fabric bands and material totals | `procurement.py` |
| Workbook parsing, inheritance, row isolation and results | `batch.py` |

Multiple load cases share the same geometry and material basis. All governing load cases participate in final thickness, overlap and bond checks. The effective Type B opening sets a minimum covered axial span. The installed thickness is checked after whole-ply rounding.

## ISO 24817:2017 design references

| Design step | Reference |
| --- | --- |
| Temperature effects and derating | §7.5.3, Tables 7 and 8 |
| Equivalent pressure and axial load | §7.5.4.1, Equations (3) and (4) |
| Type A limited by allowable substrate stress | §7.5.4.1, Equations (1) and (2) |
| Type A load sharing limited by laminate strain | §7.5.4.2, Equations (5) and (6) |
| Full-laminate structural thickness | §7.5.5, Equations (8) and (9) |
| Default and performance strain | §§7.5.5 and 7.5.6, Tables 9 and 10 and Annex E |
| Type B structural and through-wall sealing checks | §7.5.7 |
| Overlap, taper and total axial extent | §7.5.8, Equations (18)–(21) |
| Impact, cyclic loading and interface pressure | §§7.5.9.1–7.5.9.3 |
| Plain dents assessed for residual MAWP | §7.5.10, with stress-limit sizing per §7.5.4.1 |
| Fittings | §7.5.13 |
| Minimum and installed laminate | §7.5.14 |

The selected Design pressure or pipeline MAOP supplies the demand. An explicitly entered additional load-case pressure overrides the base demand for that load case. The assessed impaired-pipe pressure `ps` supplies remaining-pipe capacity in the applicable Type A route. The laminate-strain load-sharing method uses equivalent axial load directly in Equation (6). Earlier axial MAWP and force overrides and thicker-repair overrides are retained as input history.

## Remaining-pipe capacity

Modified B31G is available within the implemented straight-pipe corrosion scope. The manual B31G safety factor must be at least 1.25. Automatic selection uses the greater of the reciprocal of the original pipeline design factor and 1.25. External corrosion under Estimate mode with confirmed independent 10 × 10 mm pits and Substrate sharing takes the safety-factored Modified B31G result directly as the remaining-pipe pressure in Equation (5). Confirm dimensions and greater-than-three-wall-thickness spacing. The axial size of each pit enters Modified B31G. The overall zone span enters the repair coverage and putty estimates. For other cases, including Design, credit is limited to the local remaining-wall allowable pressure, calculated as `2 × s × t_remaining / (OD − t_remaining)` and informed by worked example 1 of ISO 24817:2017 Annex K. The reported allowable-wall pressure uses the original pipe design factor or the entered allowable stress. Equation (6) continues to use the full equivalent axial force.

External assessments supply the measured or assessed impairing-defect MAWP. The narrow dent route takes its remaining capacity from the assessed dent MAWP with the referenced dent assessment. It uses the substrate stress-limit equations with the selected allowable substrate stress. A 60/40 population estimate uses the stated population geometry and assessment assumptions.

The qualified end-of-life wall-loss limit defaults to 81% for the two products by owner selection. End-of-life wall loss must be strictly below the applicable limit and the remaining wall must meet the substrate-credit minimum. B31G's metal-loss applicability is checked separately. Enter the applicable weld, material, inspection and assessment evidence in the project work pack.

## Batch input and output records

Earlier supported v2.0 templates import their inputs into the 2017 evaluator. Warnings identify the earlier edition marker when present. A compatible older template without the axial MAWP field retains its original default assessment selection, which is evaluated under the 2017 methods. Explicit inputs and precedence remain as recorded in Effective Inputs.

Defect grouping uses the entered repair-zone span and applicable spacing or confirmed independence. The batch calculation checks each case and load against the selected route and records the governing conditions. The PDF, JSON, and Excel outputs identify the 2017 edition. The workbook's Engineering Checks tab shows clause references and Calculation Details records the calculation trace.
