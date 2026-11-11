# PROWRAP v2.0

Single-repair and batch composite-repair calculators for ISO 24817:2026. Both apps use the same calculation engine and the PRW110+ material profile.

## Applications

| Application | Entry point | Workflow |
| --- | --- | --- |
| PROWRAP Calculator v2.0 | `app.py` | Enter one repair, review checks, download a PDF or JSON calculation record |
| PROWRAP CalcBatch v2.0 | `batch_app.py` | Download the Excel template, enter line defaults and repairs, preview, calculate, download results |

The batch template contains Batch Setup, Line Defaults, Repair Cases, Defect Details, and Load and Engineering Details. Use the template from v2.0; older workbooks have a different input contract. Blank repair cells inherit line or batch values. Explicit zero and False remain valid overrides.

## B31G safety factor

Automatic selection uses **max(1 ÷ original pipeline design factor, 1.25)**. Enter the design factor as a decimal (for example, 0.72). Leave the B31G assessment safety factor blank to use automatic selection, or enter a manual override of at least 1.25. In batch workbooks, blank repair cells inherit any line/batch override; clear those too to use automatic selection. The preview and exported records show the factor actually used. Existing v2.0 workbooks remain compatible.

## Calculation scope

- Type A structural sizing and Type B structural plus sealing sizing.
- Full-laminate, substrate-sharing and substrate-stress-limit routes, with route-specific applicability checks.
- Pressure, axial force, shear, bending, torsion, temperature and supported pressure-cycle corrections.
- Current and end-of-life wall conditions; independent external-corrosion defects with applicability checks.
- Dent-without-cracks workflow using a referenced dent assessment; separate 60/40 population estimates.
- Repair-class, service, geometry, temperature, design-life, bond, thickness and landing checks.
- Layer rounding, repair extent, fabric bands and material estimates.

This version implements the stated ISO 24817:2026 calculation scope. It does not present itself as an ASME PCC-2 calculator or as a complete fitness-for-service assessment. Cracks, dent fatigue life extension, external pressure, reversing loads and damage outside the implemented routes require separate assessment. A numerical result is a calculation record for engineering review, not an issued installation procedure.

## Results and quantities

`CALCULATED` and `ESTIMATE` return dimensions and material quantities. `INPUT_ERROR`, `ENGINEERING_HOLD` and `NO_VALID_DESIGN` return diagnostic information without an installation schedule. Failed repairs are excluded from batch material totals. Estimates are totalled separately from calculated designs.

Thickness, ply count and repair length are **per repair**. Fabric band counts, fabric area and epoxy quantities are **already multiplied by the repair quantity**. Do not multiply those totals again. The procurement rules retain 50 mm fabric splices, 2 kg laminate epoxy per square metre, the corrosion putty allowance and the geometric dent putty estimate; these are estimating conventions.

## Material basis

PRW110+ is the default. PRW110 uses the same shared mechanical inputs with its separate Tg value. The controlled material constants and owner-selected design assumptions are documented in [the calculation basis](docs/calculation-basis.md). Licensed standards and source laboratory reports are not distributed in this repository.

## Run locally

Use Python 3.11 or later:

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Run the second app in a separate terminal:

```sh
python -m streamlit run batch_app.py --server.port 8502
```

For verification:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Dependencies are pinned to the release verification environment. Deploy the two entry points as separate Streamlit Community Cloud apps from the same repository revision. No secrets or external data services are required.
