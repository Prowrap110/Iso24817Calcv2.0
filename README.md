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

The **fitness-for-service reference is optional** in both apps. An entered reference remains in the calculation record. Modified B31G still requires pipe material and original design code, and retains its geometry, material-strength, temperature, wall-loss and safety-factor checks. External assessments still require the assessed impaired-pipe MAWP and applicable axial capacity.

## Substrate-credit qualification

The **substrate-credit qualification reference is optional** in both apps. An entered reference remains in the calculation record. **Confirmed qualified wall-loss limit [%] remains required** whenever remaining-steel capacity is credited. The assessed end-of-life wall loss must be strictly below that limit; equality still fails. The end-of-life minimum wall, Modified B31G applicability and other capacity checks remain unchanged. Template notes identify the optional reference without changing existing workbook headers.

## Independent defects

The **inspection/grouping assessment reference is optional** for Independent 10x10 and Measured individual defects. The dimensions/noninteraction confirmation and overall repair-zone span remain required. Independent treatment remains limited to external corrosion, and measured-defect dimensions, remaining wall and spacing/noninteraction checks remain active. The single form identifies the reference as optional; batch notes and header comments do the same without changing workbook headers.

## Axial capacity

New calculations default to Modified B31G. With no axial override, `Fs = A × Ps` uses the final credited remaining-pipe pressure (including existing allowable-pressure limits), where `A = π × OD² / 4`. Enter **Axial-capacity MAWP override [bar]** to change only the pressure used for axial capacity: `Fs [kN] = π × OD² [mm²] × MAWP [bar] / 40000`. Hoop Ps stays unchanged, although combined-stress thickness can change. An explicit zero gives zero axial credit. If External assessment is selected, automatic axial capacity follows that assessed Ps instead.

MAWP means the maximum allowable working pressure of the impaired pipe in the assessed condition, before composite-repair credit; it is not simply a pressure inferred from wall thickness alone. Use the applicable defect, material, temperature and assessment basis.

The updated batch template includes the optional axial MAWP field. Blank cells inherit line/batch values; clear inherited pressure and legacy force overrides to use automatic Ps. Older v2.0 workbooks remain accepted, retain their previous assessment default, and preserve explicit kN inputs including zero. Entering both manual pressure and force stops the calculation. The app and PDF/JSON/Excel records show the capacity and its source.

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
