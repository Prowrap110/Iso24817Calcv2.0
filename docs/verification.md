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

## B31G revision — 11 November 2026

`python3 -m pytest -q`: **113 passed** after the revision. Added numerical witnesses for factors 0.60, 0.72, 0.80 and 0.90; manual override and clearing; missing/invalid inputs; row/line/batch inheritance; matching single/batch results; PDF and Excel audit values; and interactive single/batch factor displays. Version remains 2.0.0.

## Independent engineering review

A separate reviewer checked the normative source pages and numerical witnesses. Six findings were corrected and independently rechecked: circumferential sealing selection, effective opening coverage, service-class limits, arbitrary load overrides, 5 mm opening rounding, and dent population gating. No unresolved material issue remained within that review scope. Equation (21)'s factor 3 was confirmed against the original-resolution page and retained.

## File and interface checks

- The Excel template was re-saved by LibreOffice Calc and successfully reimported.
- The single app was run in a browser and its example produced 5 plies, 4.15 mm installed thickness and 369.15 mm repair length.
- The PDF example was rendered and visually inspected; failure reports were checked to omit installation schedules.
- Source standards, test-report PDFs, local workflow notes, credentials and user project records are excluded from the release repository.

Both application entry points use `prowrap_v2.engine.evaluate_case`. Dependency versions are pinned in `requirements.txt`.

## Optional-reference revision — 11 November 2026

`python3 -m pytest -q`: **128 passed**. Verified blank/null references preserve B31G capacity and repair results; material, design-code, straight-pipe corrosion, strength, temperature, wall-loss and safety-factor checks still reject out-of-scope inputs. External assessed MAWP remains required. Single and batch app submissions with blank references produce matching results, and the invalid-factor batch row remains isolated without installation quantities. Version remains 2.0.0.

## Axial-capacity revision — 11 November 2026

`python3 -m pytest -q`: **151 passed**. Added numerical witnesses for automatic Fs from capped Ps and manual MAWP in bar; unchanged hoop Ps; explicit zero; legacy force preservation and clearing; invalid/conflicting overrides; hotter-case manual-capacity restrictions; inheritance and older workbook compatibility; matching single/batch calculations; and PDF/Excel capacity records. The original pre-revision workbook was also reimported successfully. An independent engineering/code review confirmed the ISO A × Ps basis, units, coupling, compatibility and validation scope. Version remains 2.0.0.

## Optional grouping-reference revision — 11 November 2026

`python3 -m pytest -q`: **167 passed**. Blank/null grouping references preserve calculated dimensions, materials and checks in both independent-defect modes. Regression checks retain mandatory confirmation, external-corrosion applicability, overall zone span, measured records, spacing and geometry checks. Single-app submission and batch upload calculate valid blank-reference cases while invalid cases retain holds and no installation quantities. Version remains 2.0.0.

## Optional substrate-credit qualification reference — 11 November 2026

`python3 -m pytest -q`: **185 passed**. The 18 new regression cases cover blank/null qualification references for both substrate-credit routes and both capacity methods, identical results/checks/capacity details with a supplied reference, reference retention in batch records, and missing/nonfinite/out-of-range/reached/exceeded qualification limits. Single-app submission and batch upload accept valid blank-reference cases while missing or reached limits retain holds without installation quantities. Independent code review found no blocking issues; numerical checks, workbook contracts and version 2.0.0 remain unchanged.

## Default qualified wall-loss limit — 11 November 2026

`python3 -m pytest -q`: **192 passed**. Seven additional regression cases verify the 81% default for both products, matching omitted/explicit limit results, manual overrides preserved across product changes, New calculation restoring 81%, batch default/line/repair/engineering precedence, zero/equality holds and recorded effective limits. Existing reference tests now use an explicit invalid batch limit because a blank workbook limit intentionally inherits 81%. Independent code review found no blocking issues. The optional reference, numerical engineering gates, workbook headers and version 2.0.0 remain unchanged.

## Design pressure / MAOP selection — 11 November 2026

`python3 -m pytest -q`: **228 passed**. The 36 new tests cover zero minimum-pressure defaults and manual bond-check effects; selected-MAOP equivalence for full laminate, both substrate-credit routes and Type B; raw-pressure preservation; required/invalid selected inputs; installation/minimum/class/dent/cycle checks; explicit and inherited load pressures, including a load named Base; PDF/JSON pressure records; single-app selection and cleared-input rejection; batch inheritance/export/preview/calculation and prior workbook contracts. Invalid cases continue to issue no installation quantities. Version remains 2.0.0.
