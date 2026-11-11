"""PROWRAP CalcBatch v2.0 Streamlit entry point."""

from hashlib import sha256

import streamlit as st

from prowrap_v2.batch import (
    MAX_FILE_MB, STANDARD, WorkbookError, calculate_batch, prepare_workbook, template_workbook,
)
from prowrap_v2.schema import FIELD_DEFINITIONS
from prowrap_v2.assessment import b31g_factor_details
from prowrap_v2.pressure import pressure_basis_details

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PREVIEW_FIELDS = (
    "asset_id", "product", "mechanism", "od_mm", "wall_mm", "pressure_bar", "maop_bar", "min_pressure_bar", "temperature_c",
    "install_pressure_bar", "load_basis", "growth_basis", "landing_mode", "quantity",
)


@st.cache_data(show_spinner=False)
def _template():
    return template_workbook()


def _preview(batch):
    def pressure_columns(case):
        try:
            selected = pressure_basis_details(case)
            return {'Calculation pressure [bar]': selected['calculation_pressure_bar'], 'Pressure basis': selected['basis']}
        except ValueError as error:
            return {'Calculation pressure [bar]': None, 'Pressure basis': str(error)}

    def factor_columns(case):
        if case['substrate_route'] == 'Full laminate' or case['ffs_method'] != 'Modified B31G':
            return {'B31G safety factor used': None, 'B31G factor basis': 'Not applicable'}
        try:
            selected = b31g_factor_details(case)
            return {'B31G safety factor used': selected['safety_factor'], 'B31G factor basis': selected['source']}
        except ValueError as error:
            return {'B31G safety factor used': None, 'B31G factor basis': str(error)}
    overview, inherited = st.tabs(["Repair cases", "Effective inputs"])
    with overview:
        rows = [
            {
                "Row": repair.source.number, "Repair ID": repair.case["repair_id"],
                **{FIELD_DEFINITIONS[key]["label"]: repair.case[key] for key in PREVIEW_FIELDS},
                **pressure_columns(repair.case),
                **factor_columns(repair.case),
                "Defect records": len(repair.defects), "Load records": len(repair.loads),
                "Import check": "Correct inputs" if repair.issues else "Ready to assess",
            }
            for repair in batch.repairs
        ]
        st.dataframe(rows, hide_index=True, width="stretch")
    with inherited:
        index = st.selectbox(
            "Repair to inspect", range(len(batch.repairs)),
            format_func=lambda i: f"{batch.repairs[i].case['repair_id'] or 'Missing Repair ID'} · row {batch.repairs[i].source.number}",
        )
        repair = batch.repairs[index]
        st.dataframe(
            [
                {"Input": FIELD_DEFINITIONS[key]["label"], "Value": str(value), "Origin": repair.origins[key]}
                for key, value in repair.case.items() if key in repair.origins
            ],
            hide_index=True, width="stretch",
        )
    issues = [item[-1] for item in batch.warnings]
    issues.extend(
        f"Repair Cases row {repair.source.number} · {issue}"
        for repair in batch.repairs for issue in repair.issues
    )
    if issues:
        with st.expander(f"Workbook issues ({len(issues)})", expanded=True):
            st.dataframe([{"Issue": issue} for issue in issues], hide_index=True, width="stretch")


def main():
    st.set_page_config(page_title="PROWRAP CalcBatch v2.0", layout="wide")
    st.markdown(
        """
        <style>
        .st-key-batch_heading {
            border-left: 4px solid #204b72;
            padding-left: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="batch_heading"):
        st.caption(f"PROWRAP  /  ENGINEERING TOOLS  /  {STANDARD}")
        st.title("CalcBatch v2.0")
        st.markdown("Prepare and assess multiple pipeline repair zones in one Excel workbook.")
    template_col, upload_col = st.columns([1, 2], gap="large")
    with template_col:
        st.subheader("1. Get the template")
        st.download_button(
            "Download Excel template", data=_template(), mime=MIME_XLSX,
            file_name="PROWRAP_CalcBatch_v2_Template.xlsx", on_click="ignore",
        )
        st.caption("Enter shared values on Batch Setup or Line Defaults. Add one row per repair zone.")
        st.caption("The results workbook includes blank pricing cells for fabric per m², epoxy per litre and a sales multiplier, with automatic sale totals.")
        st.caption('Choose Design pressure (default) or MAOP for calculations. Minimum design pressure defaults to 0 bar and can be overridden. Blank cells inherit line/batch settings; explicitly entered load-case pressures still apply.')
        st.caption('Fitness-for-service reference is optional. Include an available reference for the calculation record.')
        st.caption('Substrate-credit qualification reference is optional. Qualified wall-loss limit defaults to 81% for PRW110 and PRW110+. Enter a percentage in Batch Setup, Line Defaults or repair inputs to override; end-of-life wall loss must remain strictly below the selected limit.')
        st.caption('Inspection / grouping assessment reference is optional. Independent defects still require confirmed dimensions/noninteraction, the overall zone span and applicable spacing checks.')
        st.caption('B31G: automatic safety factor = max(1 ÷ original pipeline design factor, 1.25). Enter a B31G assessment safety factor only for a manual override. Blank repair cells inherit any line or batch override; clear those too to use automatic calculation.')
        st.caption('Axial capacity defaults to A × assessed Ps (Modified B31G by default). Enter Axial-capacity MAWP override [bar] for the axial basis only. Clear any legacy kN override before using it; explicit zero means no axial credit.')
    with upload_col:
        st.subheader("2. Upload your workbook")
        uploaded = st.file_uploader(
            f"Completed Excel workbook · up to {MAX_FILE_MB} MB",
            type=["xlsx"], label_visibility="collapsed",
        )
        st.caption("Use the same Repair ID for linked defect and load records.")
    if uploaded is None:
        st.session_state.pop("batch_upload", None)
        return
    content = uploaded.getvalue()
    digest = sha256(content).hexdigest()
    session = st.session_state.get("batch_upload")
    if session is None or session["digest"] != digest:
        try:
            batch = prepare_workbook(content)
        except WorkbookError as error:
            st.session_state.pop("batch_upload", None)
            st.error(str(error))
            return
        session = {"digest": digest, "batch": batch, "output": None}
        st.session_state["batch_upload"] = session

    batch = session["batch"]
    st.divider()
    st.subheader("3. Preview and calculate")
    if not batch.repairs:
        st.info("Add at least one repair row on Repair Cases, then upload the completed workbook.")
        return
    flagged = sum(bool(repair.issues) for repair in batch.repairs)
    st.caption(
        f"{len(batch.repairs)} repair rows · {flagged} rows with import issues. "
        "Calculation checks engineering inputs and applicability."
    )
    _preview(batch)
    if st.button("Calculate batch", type="primary"):
        with st.spinner("Assessing repair cases…"):
            session["output"] = calculate_batch(batch)
    if session["output"] is None:
        return

    workbook, results = session["output"]
    st.divider()
    st.subheader("4. Download results")
    calculated = sum(record["status"] == "CALCULATED" for record in results)
    estimated = sum(record["status"] == "ESTIMATE" for record in results)
    other = len(results) - calculated - estimated
    a, b, c = st.columns(3)
    a.metric("Calculated", calculated)
    b.metric("Estimates", estimated)
    c.metric("Require review", other)
    st.caption("Results are for engineering review. The export keeps estimate quantities separate.")
    pressure_rows = [
        {'Repair ID': record['repair_id'],
         'Pressure basis': record['details']['pressure_basis']['basis'],
         'Calculation pressure [bar]': record['details']['pressure_basis']['calculation_pressure_bar']}
        for record in results if record['status'] in ('CALCULATED','ESTIMATE')
    ]
    if pressure_rows:
        st.dataframe(pressure_rows, hide_index=True, width='stretch')
    capacity_rows = [
        {"Repair ID": record['repair_id'],
         "Remaining-pipe Ps [bar]": record['details']['substrate_pressure_mpa']*10,
         "Axial capacity used [kN]": record['details']['axial_capacity']['force_kn'],
         "Axial pressure basis [bar]": record['details']['axial_capacity']['pressure_bar'],
         "Axial capacity basis": record['details']['axial_capacity']['source']}
        for record in results if record['status'] in ('CALCULATED','ESTIMATE')
        and record['inputs']['substrate_route'] != 'Full laminate'
    ]
    if capacity_rows:
        st.dataframe(capacity_rows, hide_index=True, width='stretch')
    st.download_button(
        "Download results workbook", data=workbook, mime=MIME_XLSX, type="primary",
        file_name="PROWRAP_CalcBatch_v2_Results.xlsx", on_click="ignore",
    )
    st.caption("Open Summary and Cost in Excel to enter prices, densities or litre quantities, and the sales multiplier. Prices and EXW/FOB/CFR totals calculate automatically.")


if __name__ == "__main__":
    main()
