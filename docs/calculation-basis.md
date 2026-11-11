# Calculation basis — v2.0.0

## Controlled sources

- ISO 24817:2026, supplied complete 122-page PDF. SHA-256: `c00732247907d2ba3f01a3ae70de8d008578ce63a8dc8ed31c7a80c060e79742`.
- PRW110+ Qualification Report, R5 Corrected, 66 pages. SHA-256: `586d89fdc36a52047ac482e7f6b0aad15ae859e4ec7b7f04dea852accfbb09d5`.
- PRW110 Final Report, 63 pages, used for the PRW110 Tg only. SHA-256: `085bf5b1c8735a6a8176ba5607b489529a3ad4842cb5e85be84dc84967d1fadb`.
- ASME B31G:2023, supplied copy, used only for the optional Modified B31G substrate-capacity calculation within its implemented limits.

The source documents remain controlled externally. These references identify the implementation basis; they do not establish new product qualification or certification.

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

PRW110 inherits the PRW110+ shared mechanical profile by the owner's explicit direction; only Tg differs.

## Owner-selected design inputs

The owner explicitly selected 0.0055 strain for the performance/LTS option, 250 J/m² (0.250 N/mm) sealing parameter, 2,450 MPa shear modulus in the required planes including G31, and a three-ply Type B minimum. These are accepted calculator assumptions and are not presented as qualification issues in the apps. This record preserves the distinction between a design input and a new test result.

Default-strain and performance-strain routes retain the applicable temperature, cycle, design-life and service-class rules. The report cure route uses the conservative temperature factor basis implemented in the engine. A separately confirmed qualified cure schedule requires a procedure reference.

## Implementation map

| Calculation | Implementation |
| --- | --- |
| Classes, service, defect grouping, end-of-life condition and route gates | `engine.py` |
| Load equivalents, strain, temperature and cyclic factors; structural equations | `physics.py` |
| Type B circular and slot sealing, finite-solution checks and governing capacities | `sealing.py` |
| Referenced substrate capacity and Modified B31G | `assessment.py` |
| Bond, fitting pressure cap, overlap, thickness and final acceptance | `physics.py`, `engine.py` |
| Fabric bands and material totals | `procurement.py` |
| Workbook parsing, inheritance, row isolation and results | `batch.py` |

Multiple load cases share the same geometry and material basis. All governing load cases participate in final thickness, overlap and bond checks. The effective Type B opening sets a minimum covered axial span. The installed thickness is checked after whole-ply rounding.

## B31G safety-factor selection — v2.0 revision, 11 November 2026

When the manual B31G assessment safety-factor input is blank after workbook inheritance, the calculator uses `max(1 / original_design_factor, 1.25)`. The original pipeline design factor must be a finite decimal greater than zero and no greater than one. The reciprocal uses full precision; 0.72 therefore gives 1.3888888889, not a rounded 1.39. The existing minimum of 1.25 is retained. This is the owner's selected automatic basis, not a universal requirement of ISO 24817 or ASME B31G.

An explicitly entered safety factor is a manual override and must be finite and at least 1.25. It does not require a design factor for safety-factor selection, although the selected substrate route still needs its other allowable-stress inputs. An entered design factor is validated even when a manual override is used. Missing or invalid applicable inputs stop the affected case.

Both apps show the selected factor and its automatic/manual basis. PDF/JSON calculation details and batch Excel effective inputs record the value actually used. Existing v2.0 workbook columns remain compatible: populated safety-factor cells retain their manual values. Blank repair cells inherit any line or batch override, so clear inherited overrides as well to return to automatic calculation. The application version remains v2.0 / 2.0.0.
