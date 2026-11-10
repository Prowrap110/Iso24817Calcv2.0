# Changelog

## 2.0.0 — 2026-11-10

- Rebuilt single and batch applications around one ISO 24817:2026 calculation engine.
- Applied PRW110+ mechanical data and separate PRW110/PRW110+ Tg profiles.
- Added explicit load, temperature, future-condition, substrate assessment and cure inputs.
- Corrected pressure-end loads, temperature and cycle factors, Type B structural/sealing checks, rounding and final acceptance checks.
- Preserved independent-corrosion and dent-without-cracks workflows with applicability checks and separate population estimates.
- Added robust Excel import, line defaults, linked defects/load cases, effective-input audit and row-isolated failures.
- Added PDF/JSON single-calculation records and Excel batch results; failed cases do not issue installation schedules or contribute to material totals.
- Kept v1 repositories and deployments separate from this release.
