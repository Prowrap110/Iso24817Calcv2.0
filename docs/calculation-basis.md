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
| Assessed substrate capacity and Modified B31G | `assessment.py` |
| Bond, fitting pressure cap, overlap, thickness and final acceptance | `physics.py`, `engine.py` |
| Fabric bands and material totals | `procurement.py` |
| Workbook parsing, inheritance, row isolation and results | `batch.py` |

Multiple load cases share the same geometry and material basis. All governing load cases participate in final thickness, overlap and bond checks. The effective Type B opening sets a minimum covered axial span. The installed thickness is checked after whole-ply rounding.

## B31G safety-factor selection — v2.0 revision, 11 November 2026

When the manual B31G assessment safety-factor input is blank after workbook inheritance, the calculator uses `max(1 / original_design_factor, 1.25)`. The original pipeline design factor must be a finite decimal greater than zero and no greater than one. The reciprocal uses full precision; 0.72 therefore gives 1.3888888889, not a rounded 1.39. The existing minimum of 1.25 is retained. This is the owner's selected automatic basis, not a universal requirement of ISO 24817 or ASME B31G.

An explicitly entered safety factor is a manual override and must be finite and at least 1.25. It does not require a design factor for safety-factor selection, although the selected substrate route still needs its other allowable-stress inputs. An entered design factor is validated even when a manual override is used. Missing or invalid applicable inputs stop the affected case.

Both apps show the selected factor and its automatic/manual basis. PDF/JSON calculation details and batch Excel effective inputs record the value actually used. Existing v2.0 workbook columns remain compatible: populated safety-factor cells retain their manual values. Blank repair cells inherit any line or batch override, so clear inherited overrides as well to return to automatic calculation. The application version remains v2.0 / 2.0.0.

## Optional fitness-for-service reference — v2.0 revision, 11 November 2026

The `ffs_ref` field is optional for Modified B31G and external assessed-capacity routes. It is retained for traceability when provided, but a blank reference is not an engineering hold. The Modified B31G material specification, original design code, straight-pipe corrosion restriction, strength/temperature limits, metal-loss limit and safety-factor validation remain unchanged. The external route still requires assessed MAWP; both substrate-credit routes retain their end-of-life wall, qualification-envelope and axial-capacity checks. Dent-assessment references remain separate required inputs. The substrate-credit qualification reference is also optional under the later revision below.

The single form labels the reference optional. Batch Setup notes and table-header comments explain its optional status while preserving the v2.0 workbook column contract.

## Pressure-based axial capacity — v2.0 revision, 11 November 2026

ISO 24817:2026 §4.1 defines impaired-component axial capacity Fs as A × ps, or from a relevant defect assessment. Equation (9) uses A = πD²/4. New calculations default to Modified B31G; automatic axial credit uses the final assessed Ps after the existing original-code pressure cap, not the raw failure pressure. Conversion is `Fs [kN] = πD² [mm²] × pressure [bar] / 40000`.

The owner selected a separate manual MAWP in bar for axial capacity only. `axial_mawp_bar` replaces the pressure used to calculate Fs but never replaces hoop Ps. Fs also enters the combined-stress hoop equation through Poisson coupling, so hoop thickness need not stay unchanged. When the remaining-capacity assessment is explicitly External assessment, blank axial overrides use that external Ps.

Existing `assessed_axial_capacity_kn` inputs are retained, including zero. Both override fields populated is an engineering hold. Blank fields mean automatic pressure-based axial capacity; an explicit zero pressure or force means zero axial credit. Manual positive axial credit cannot be reused in an additional hotter load case without a temperature-specific assessment. Full-laminate and Type B routes retain zero substrate credit.

The new template adds `axial_mawp_bar` to shared defaults and repair-level engineering inputs. A complete old v2.0 template without this field is accepted with its former External assessment default preserved before explicit overrides are resolved; mixed or otherwise changed column contracts remain rejected. The calculation record exports axial force, pressure basis and source for the base and every load case. Version remains 2.0.0.

## Optional inspection/grouping reference — v2.0 revision, 11 November 2026

At the owner's request, `grouping_ref` is optional for both Independent 10x10 and Measured individual modes. A blank or null reference no longer causes an engineering hold; a supplied reference remains in the calculation record. This changes a documentation requirement, not the independent-defect applicability criteria or equations.

The shared engine still requires explicit dimension/noninteraction confirmation, external-corrosion applicability and overall repair-zone span. Measured individual mode still requires linked defects, valid dimensions and remaining wall, and either measured clear separation greater than 3t or explicit per-defect noninteraction confirmation when no separation is entered. An entered separation at or below 3t continues to fail even if confirmation is supplied. The 10 × 10 mm pit assumption is unchanged. Existing workbook field keys and labels remain compatible; optional status is explained by template notes and comments. Version remains 2.0.0.

## Optional substrate-credit qualification reference — v2.0 revision, 11 November 2026

At the owner's request, `qualification_ref` is optional in both substrate-credit routes and for both Modified B31G and external capacity assessments. An entered reference remains in the calculation record; blank or null references do not cause a hold. The numerical `qualified_wall_loss_pct` remains mandatory, finite and within 0–100%. Assessed end-of-life wall loss must remain strictly below the selected limit, as required for substrate credit by ISO 24817:2026 §§9.7.2–9.7.3. The end-of-life wall, Modified B31G metal-loss scope and all other capacity checks are unchanged. Existing workbook keys and labels are unchanged; notes and comments explain optional status. Version remains 2.0.0.

## Default qualified wall-loss limit — v2.0 revision, 11 November 2026

The owner selected 81% as the default `qualified_wall_loss_pct` for PRW110+ and PRW110, using the PRW110+ report's stated limit and the instruction to share this limit between the products. This is an editable design input, not a new qualification test result. New/reset/example single cases and omitted engine fields use 81%; an explicit single-form value overrides it, including invalid values which still fail validation. Clearing that field does not silently substitute a different value.

Blank workbook cells inherit through repair/engineering inputs, line defaults and Batch Setup, finally falling back to the calculator's 81%. Explicit existing values are never replaced by the default; zero remains zero and fails the strict loss check. The applied value and its origin remain in batch Effective Inputs. The strict end-of-life loss check, range validation, minimum remaining wall and Modified B31G's separate 80% metal-loss limit are unchanged. No fields, workbook headers or version numbers changed.
