# PROWRAP v2.0

Single-repair and batch composite-repair calculators for ISO 24817:2017. Both apps use the same calculation engine and the PRW110+ material profile.

## Weighted tender estimates

This paired build uses ISO 24817:2017 sizing and
direct, safety-factored Modified B31G hoop credit for Estimate cases with
confirmed independent 10 × 10 mm external pits and Substrate sharing.
The 200/400 mm spans set zone coverage and putty allowances. Plain dents use the substrate stress-limit route with the entered assessed
dent MAWP. Engineering design and installation require a separate project review.

In the single app, use the inputs for one Repair ID from the filled batch
template to reproduce its unit result. In CalcBatch, a filled **Estimate Weights**
tab adds the weighted **Tender Takeoff**, group breakdown and scenario audit to
the normal calculation export. Use quantity 1 and Estimate purpose for all
weighted rows. List every Repair ID once and make each group's shares total
100%. Enter the tender minimum in mixed litres and the verified mixed yield per
1 kg putty kit. CalcBatch applies the shares once, takes the greater of calculated
putty and the minimum equivalent, and rounds up once per pipe group. The
**Results** tab shows weighted material, band and equivalent-repair quantities,
while its engineering dimensions stay per repair. **Unit Results** preserves
the unweighted calculation record for single-case checking. An incomplete weighted
run reports individual cases and withholds procurement totals.

Band counts represent single-ply circumferential bands summed across all
installed plies and identical repairs. Fabric metres are reported separately
for 300 mm and 500 mm widths, using the same mean ply circumference as the
existing fabric area estimate. Thus 0.3 times the 300 mm metres plus 0.5 times
the 500 mm metres equals the fabric area. Weighted exports apply scenario
shares once to these counts and metres; equivalent band counts can be
fractional and do not represent rounded roll orders. This reporting update
does not change design dimensions, fabric area, epoxy or putty consumption.

## Applications

| Application | Entry point | Workflow |
| --- | --- | --- |
| PROWRAP Calculator v2.0 | `app.py` | Enter one repair, review checks, download a PDF or JSON calculation record |
| PROWRAP CalcBatch v2.0 | `batch_app.py` | Download the Excel template, enter line defaults and repairs, preview, calculate, download results |

The batch template contains Batch Setup, Line Defaults, Repair Cases, Defect Details, and Load and Engineering Details. Earlier v2.0 templates with the supported column layouts can also be uploaded. CalcBatch calculates every imported case using ISO 24817:2017 and records the earlier edition marker when present. Blank repair cells inherit line or batch values. Explicit zero and False remain valid overrides for applicable fields.

**Number of identical repairs** is visible in **Line Defaults column B**, next to Line ID. A linked repair with a blank quantity inherits that line's count; an entered repair quantity takes precedence. The exported **Identical repairs** column shows the applied count, and material totals include it exactly once. Existing v2.0 files with the quantity column in its previous position remain accepted.

## Calculation pressure

**Minimum design pressure defaults to 0 bar** in both calculators and remains editable. In the single form, **Design pressure [bar]** and **MAOP [bar]** appear side by side; select **Pressure used for calculations** to use either Design pressure (default) or MAOP. The selected positive pressure drives the base repair calculation and applicable pressure bounds. The unselected pressure may be blank; if entered, it must still be a valid positive number. The input record preserves both entered values, and the form, results and PDF/JSON/Excel records identify the pressure actually used.

MAOP is the pipeline's maximum allowable operating pressure. It supplies the pressure demand when selected. The assessed impaired-pipe MAWP supplies substrate capacity when applicable. Minimum and installation pressures must be between zero and the selected calculation pressure; cyclic bounds and all other checks remain active.

Additional named load cases retain their explicit pressure values, which override the selected base pressure for those cases. A blank additional load-case pressure inherits the selected base pressure. Every case is assessed and the governing result is used.

Batch settings follow the existing repair/engineering → line → batch → calculator-default precedence. Existing v2.0 workbooks without the new MAOP/selection fields remain accepted and use Design pressure; explicit minimum pressures and other overrides remain preserved. The current template adds the two fields while keeping version v2.0.

## B31G safety factor

Automatic selection uses **max(1 ÷ original pipeline design factor, 1.25)**. Enter the design factor as a decimal (for example, 0.72). Leave the B31G assessment safety factor blank to use automatic selection, or enter a manual override of at least 1.25. In batch workbooks, blank repair cells inherit any line/batch override; clear those too to use automatic selection. The preview and exported records show the factor actually used. Existing v2.0 workbooks remain compatible.

The **fitness-for-service reference is optional** in both apps. An entered reference remains in the calculation record. Modified B31G still requires pipe material and original design code, and retains its geometry, material-strength, temperature, wall-loss and safety-factor checks. External assessments require the assessed impaired-pipe MAWP. Estimate mode with external corrosion, confirmed independent 10 × 10 mm pits, and Substrate sharing credits the safety-factored Modified B31G pressure directly. The repair-zone span controls coverage and putty. The local remaining-wall pressure limit still applies to other routes, including Design. The calculator records the allowable-wall pressure for comparison. With a manual B31G factor, enter the applicable allowable stress or the original pipeline design factor.

## Substrate-credit qualification

The **substrate-credit qualification reference is optional with the Default strain basis**. For an LTS Design, the selected strain requires applicable Annex E performance qualification. An entered reference remains in the calculation record. **Confirmed qualified wall-loss limit [%] defaults to 81% for PRW110 and PRW110+**. Edit the percentage for a manual override. In batch files, repair/engineering inputs override line defaults, which override Batch Setup; blank cells inherit, with 81% used when no limit is entered. Existing explicit percentages, including zero, are preserved and validated. A cleared single-form field must be filled before substrate credit can be calculated; New calculation restores 81%.

The assessed end-of-life wall loss must be strictly below the selected limit; equality still fails. The end-of-life minimum wall, Modified B31G's separate 80% metal-loss scope and all other capacity checks remain unchanged. Template notes identify the default and optional reference without changing existing workbook headers. The 81% value is an owner-selected default using the PRW110+ report's stated limit, also applied to PRW110 by instruction.

## Independent defects

The **inspection/grouping assessment reference is optional** for Independent 10x10 and Measured individual defects. The dimensions/noninteraction confirmation and overall repair-zone span remain required. Independent treatment remains limited to external corrosion, and measured-defect dimensions, remaining wall and spacing/noninteraction checks remain active. The single form identifies the reference as optional; batch notes and header comments do the same without changing workbook headers.

## Structural and axial sizing

The 2017 substrate stress-limit route uses §7.5.4.1, Equations (1) and (2). The substrate-sharing route uses §7.5.4.2, Equations (5) and (6). Its axial thickness calculation uses the full equivalent axial load. Full-laminate structural sizing uses §7.5.5, Equations (8) and (9).

Earlier workbook fields for axial MAWP and axial force are retained for input history, along with the thicker-repair overrides. The installed laminate must be strictly thinner than OD/12 within the implemented structural equations.

## Calculation scope

Selecting **Dent no-crack** uses the assessed dent MAWP as the remaining-pipe pressure capacity with the substrate stress-limit method (§§7.5.10 and 7.5.4.1). Enter the allowable substrate stress or supply the original design factor to derive it from SMYS. Modified B31G applies to straight-pipe corrosion.

The dent route covers plain, non-cyclic straight-pipe dents without cracks or current or future wall loss. No-crack confirmation, inspection and dent-assessment references, and a positive assessed dent MAWP are required. Population estimates use explicitly stated assessment assumptions. Installation pressure must stay within the assessed capacity. The thickness calculation includes the equivalent loads and, for Type A, the minimum of two plies and 2 mm. At 0.83 mm per ply, this floor rounds up to three plies (2.49 mm).

- Type A structural sizing and Type B structural plus sealing estimates. Type B Design requires verified Annex D sealing and Annex F impact data for the repair system.
- Full-laminate, substrate-sharing and substrate-stress-limit routes, with route-specific applicability checks.
- Pressure, axial force, shear, bending, torsion, temperature and supported pressure-cycle corrections.
- Current and end-of-life wall conditions; independent external-corrosion defects with applicability checks.
- Dent-without-cracks workflow using a referenced dent assessment; separate 60/40 population estimates.
- Repair-class, service, geometry, temperature, design-life, bond, thickness and landing checks.
- Layer rounding, repair extent, fabric bands and material estimates.

The apps cover the ISO 24817:2017 calculation routes listed above. Cracks, dent fatigue life extension, external pressure, reversing loads and damage outside the implemented routes require separate assessment. The calculation record is for engineering review. The project work pack supplies approved installation and inspection procedures.

## Results and quantities

`CALCULATED` and `ESTIMATE` return dimensions and material quantities. `INPUT_ERROR`, `ENGINEERING_HOLD` and `NO_VALID_DESIGN` return diagnostic information without an installation schedule. Failed repairs are excluded from batch material totals. Estimates are totalled separately from calculated designs.

Thickness, ply count, repair length and **Putty per defect [kg]** are **per repair**. Fabric band counts, fabric area, **Putty total [kg]** and other epoxy totals are **already multiplied by the repair quantity exactly once**. Do not multiply those totals again. The procurement rules retain 50 mm fabric splices and 2 kg laminate epoxy per square metre; these are estimating conventions.

Automatic corrosion putty is **2 kg up to 200 mm**, **3 kg up to 400 mm**, then **+1 kg per further started 200 mm** of the entered repair-zone span (defect length if no zone span is entered). Dent putty uses **one-third of length × width × depth**, with dimensions in mm and an estimating density of **2 kg/L**: `L × W × depth × 0.000002 / 3` kg per defect. **Putty consumption per defect [kg]** is an optional override in section 9 of the single calculator and in Batch Setup, Line Defaults and Repair Cases. Blank uses the automatic allowance; explicit zero is preserved. In batch files, an entered repair override takes precedence over the line default, then batch setup. For grouped pits, the allowance applies to one repair zone, not separately to every pit inside it. Existing v2.0 workbooks without the new input remain accepted.

Downloaded batch results include editable pricing on **Summary and Cost**. Enter currency, fabric cost per m², epoxy and putty cost per litre, and a sales multiplier. Enter confirmed mixed-product densities for kg-to-litre conversion, or enter explicit litre totals in the group override cells. All commercial entry cells start blank; zero costs and zero-volume overrides are preserved. Excel calculates material cost, sale price and EXW/FOB/CFR totals, including optional additional supplies, packaging and freight sale amounts. Existing Batch Setup epoxy rates remain explicitly per kg and are never reused as per-litre prices. These are the quantities of the valid uploaded cases; tender population weights, component pack sizes and project-specific price schedules require a separate project take-off.

## Material basis

PRW110+ is the default. PRW110 uses the same shared mechanical inputs with its separate Tg value. Thermal sizing takes the recorded Tg as representative of the selected cure. The LTS estimate input is **0.007 (0.7%)** for both products before design derating. A design using this value requires evidence that applicable Annex E performance qualification supports it. The controlled material constants and owner-selected design assumptions are documented in [the calculation basis](docs/calculation-basis.md). Licensed standards and source laboratory reports are not distributed in this repository.

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
