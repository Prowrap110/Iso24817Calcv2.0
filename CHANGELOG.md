# Changelog

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
