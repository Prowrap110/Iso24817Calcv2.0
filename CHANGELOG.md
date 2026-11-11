# Changelog

## Default qualified wall-loss limit — 2026-11-11 (version remains 2.0.0)

- Default the qualified wall-loss limit to 81% for PRW110 and PRW110+ in both calculators, with editable manual overrides.
- Preserve batch override precedence and existing explicit percentages; blank workbook inputs inherit the shared 81% default.
- Retain strict wall-loss, range and capacity checks, optional qualification references and workbook compatibility.

## Optional substrate-credit qualification reference — 2026-11-11 (version remains 2.0.0)

- Make the substrate-credit qualification reference optional in both calculators and retain any entered reference in the calculation record.
- Keep the confirmed qualified wall-loss limit mandatory for substrate credit, including range validation and strict end-of-life loss below the limit.
- Identify the missing numerical input clearly, mark the reference optional in the single form and batch guidance, and preserve workbook compatibility.

## Optional grouping reference — 2026-11-11 (version remains 2.0.0)

- Make the inspection/grouping assessment reference optional in both independent-defect modes and both calculators.
- Retain dimension/noninteraction confirmation, external-corrosion applicability, repair-zone extent, measured geometry and spacing checks.
- Clarify the single form, batch guidance and template comments while preserving existing workbook field keys and labels.

## Axial capacity from pressure — 2026-11-11 (version remains 2.0.0)

- Default new remaining-capacity assessments to Modified B31G and axial credit to `Fs = A × Ps`, using final credited Ps after existing limits.
- Add an optional axial-only MAWP override in bar. It does not replace hoop Ps; combined-stress thickness can still change.
- Preserve populated legacy axial-force inputs and previous assessment defaults in older v2.0 workbooks. Reject simultaneous force and pressure overrides.
- Show and export the actual axial pressure, force and source; retain applicability checks and require a temperature-specific assessment for hotter linked cases using positive manual axial credit.

## Optional assessment reference — 2026-11-11 (version remains 2.0.0)

- Made the fitness-for-service reference optional in both calculators, including Modified B31G and external assessed-capacity inputs.
- Kept all implemented B31G applicability checks and required numerical capacities; missing material and design-code messages now name the missing input.
- Clarified the single-app label and batch template guidance without changing existing workbook headers.

## v2.0 revision — 2026-11-11 (version remains 2.0.0)

- Calculate the B31G safety factor automatically from the original pipeline design factor, retaining the 1.25 minimum.
- Support an optional manual override in both calculators and preserve existing workbook overrides.
- Display and export the selected factor and its basis; update template guidance and regression checks.

## 2.0.0 — 2026-11-10

- Rebuilt single and batch applications around one ISO 24817:2026 calculation engine.
- Applied PRW110+ mechanical data and separate PRW110/PRW110+ Tg profiles.
- Added explicit load, temperature, future-condition, substrate assessment and cure inputs.
- Corrected pressure-end loads, temperature and cycle factors, Type B structural/sealing checks, rounding and final acceptance checks.
- Preserved independent-corrosion and dent-without-cracks workflows with applicability checks and separate population estimates.
- Added robust Excel import, line defaults, linked defects/load cases, effective-input audit and row-isolated failures.
- Added PDF/JSON single-calculation records and Excel batch results; failed cases do not issue installation schedules or contribute to material totals.
- Kept v1 repositories and deployments separate from this release.
