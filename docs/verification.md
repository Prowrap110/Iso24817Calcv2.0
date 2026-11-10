# Release verification — 2.0.0

Verified on 10 November 2026 against the supplied ISO 24817:2026 and PRW110+ sources. This is software verification of the implemented scope, not product qualification or an independent engineering certification.

## Automated verification

`python3 -m pytest -q`: **95 passed**.

- Independent numerical checks for load equivalents, structural thickness, temperature and pressure-cycle factors, design-life and strain routes.
- Circular and slot sealing witnesses; both circumferential pressure-capacity conditions must pass. No finite solution remains a failure.
- Effective opening rounding, axial coverage, whole-ply thickness, sound landing, bond and fitting checks.
- Service/class boundaries, crack/dent route gates, linked-load restrictions and population-estimate isolation.
- Workbook inheritance and explicit-zero/False overrides, invalid booleans, formulas, duplicate IDs, changed headers, generated-ID collisions and row-level failure isolation.
- A 150-repair workbook with 300 linked defects.
- Streamlit form submission and actual upload/preview/calculate/export workflows; stale results are removed after edits or replacement uploads.
- Single/batch result parity, including a three-repair case, and PDF/JSON/XLSX quantity checks to prevent double counting.

## Independent engineering review

A separate reviewer checked the normative source pages and numerical witnesses. Six findings were corrected and independently rechecked: circumferential sealing selection, effective opening coverage, service-class limits, arbitrary load overrides, 5 mm opening rounding, and dent population gating. No unresolved material issue remained within that review scope. Equation (21)'s factor 3 was confirmed against the original-resolution page and retained.

## File and interface checks

- The Excel template was re-saved by LibreOffice Calc and successfully reimported.
- The single app was run in a browser and its example produced 5 plies, 4.15 mm installed thickness and 369.15 mm repair length.
- The PDF example was rendered and visually inspected; failure reports were checked to omit installation schedules.
- Source standards, test-report PDFs, local workflow notes, credentials and user project records are excluded from the release repository.

Both application entry points use `prowrap_v2.engine.evaluate_case`. Dependency versions are pinned in `requirements.txt`.
