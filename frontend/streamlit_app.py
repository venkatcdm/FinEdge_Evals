import streamlit as st
import tempfile
import sys
import os
from pathlib import Path
from collections import defaultdict

# ---------------------------------------------------
# ROOT PATH SETUP
# ---------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT_DIR))

# ---------------------------------------------------
# IMPORTS
# ---------------------------------------------------

from datetime import datetime

from app.evaluator.evaluation_report_html import (
    build_evaluation_report_html,
    build_field_scores_csv,
)
from app.main import evaluate
from app.main import evaluate as evaluate_func
from app.utils.loaders import (
    load_schema,
    load_thresholds
)
from app.utils.schema_parser import extract_fields

# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------

st.set_page_config(
    page_title="Invoice Evaluation System",
    layout="wide"
)

# ---------------------------------------------------
# TITLE
# ---------------------------------------------------

st.title("Invoice Evaluation System")

# ---------------------------------------------------
# SCHEMA SELECTION
# ---------------------------------------------------

schema = st.selectbox(
    "Select Schema",
    ["global", "germany", "uk"]
)

# ---------------------------------------------------
# LOAD SCHEMA + THRESHOLDS
# ---------------------------------------------------

schema_data = load_schema(schema)

saved_thresholds = load_thresholds(schema)

all_fields = extract_fields(schema_data)

# ---------------------------------------------------
# THRESHOLD CONFIGURATION
# ---------------------------------------------------

st.subheader("Threshold Configuration")

st.caption(
    "Adjust fuzzy matching thresholds for every field. "
    "Higher thresholds = stricter matching (lower tolerance). "
    "Lower thresholds = more lenient (higher tolerance)."
)

# Add threshold impact explanation
with st.expander("ℹ️ How Thresholds Affect Scoring"):
    st.markdown("""
    **Numeric Fields (amounts, quantities):**
    - Threshold 95-100: Requires 0.01% - 0.25% tolerance (near-exact match)
    - Threshold 90-95: Allows 0.5% tolerance
    - Threshold 80-90: Allows 1-2% tolerance  
    - Threshold 70-80: Allows 5-10% tolerance
    
    **Date Fields:**
    - Threshold 95-100: Same day or ±1 day
    - Threshold 85-95: ±2-3 days
    - Threshold 75-85: ±5-7 days
    - Threshold <75: ±14 days
    
    **Text Fields:**
    - Threshold 95-100: Near-exact or exact match
    - Threshold 85-95: High similarity required (85-90%+)
    - Threshold 75-85: Moderate similarity (75-85%+)
    - Threshold <75: More lenient matching
    """)

updated_thresholds = {}

# Group fields by section
grouped_fields = defaultdict(list)

for field in all_fields:

    if "." in field:
        section = field.split(".")[0]
    else:
        section = "top_level_fields"

    grouped_fields[section].append(field)

# Render grouped sliders
for section, fields in grouped_fields.items():

    st.markdown(f"### {section.replace('_', ' ').title()}")

    col1, col2 = st.columns(2)

    for idx, field in enumerate(sorted(fields)):

        # --------------------------------------------
        # DEFAULT THRESHOLD LOGIC
        # --------------------------------------------

        default_value = saved_thresholds.get(field)

        if default_value is None:

            if "description" in field:
                default_value = 70

            elif "invoice_id" in field:
                default_value = 100

            elif "currency" in field:
                default_value = 100

            elif "amount" in field:
                default_value = 95

            elif "date" in field:
                default_value = 90

            elif "tax" in field:
                default_value = 95

            else:
                default_value = 85

        # --------------------------------------------
        # TWO COLUMN LAYOUT
        # --------------------------------------------

        current_col = col1 if idx % 2 == 0 else col2

        with current_col:

            updated_thresholds[field] = st.slider(
                label=field,
                min_value=50,  # Changed from 0 to 50 for more practical range
                max_value=100,
                value=int(default_value),
                key=field,
                help=f"Lower = more liberal matching, Higher = stricter matching"
            )

# ---------------------------------------------------
# FILE UPLOADS
# ---------------------------------------------------

st.subheader("Upload Files")

col1, col2 = st.columns(2)

with col1:

    extracted_file = st.file_uploader(
        "Upload Extracted JSON",
        type=["json"]
    )

with col2:

    gt_file = st.file_uploader(
        "Upload Groundtruth JSON",
        type=["json"]
    )

# ---------------------------------------------------
# RUN EVALUATION
# ---------------------------------------------------

if st.button("Run Evaluation", use_container_width=True):

    if not extracted_file or not gt_file:

        st.error("Please upload both JSON files")

    else:

        with st.spinner("Running evaluation..."):

            # ----------------------------------------
            # SAVE TEMP FILES
            # ----------------------------------------

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".json"
            ) as ext_temp:

                ext_temp.write(extracted_file.read())

                ext_path = ext_temp.name

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".json"
            ) as gt_temp:

                gt_temp.write(gt_file.read())

                gt_path = gt_temp.name

            # ----------------------------------------
            # RUN EVALUATION
            # ----------------------------------------

            result = evaluate(
                extracted_path=ext_path,
                groundtruth_path=gt_path,
                schema_name=schema,
                thresholds=updated_thresholds
            )

        # ------------------------------------------------
        # RESULTS
        # ------------------------------------------------
        
        st.success("Evaluation Completed")
        
        # ------------------------------------------------
        # DATA SUMMARY STATISTICS
        # ------------------------------------------------
        
        st.subheader("Data Summary")
        
        stats = result.get("stats", {})
        
        # Row 1: Invoice counts
        st.markdown("### Invoice Matching")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Extracted Invoices",
                stats.get("total_invoices_extracted", 0)
            )
        
        with col2:
            st.metric(
                "Ground Truth Records",
                stats.get("total_ground_truth_records", 0)
            )
        
        with col3:
            st.metric(
                "Matched Invoices",
                stats.get("total_invoices_matched", 0),
                delta=f"{stats.get('total_invoices_matched', 0) - stats.get('total_invoices_extracted', 0):+d}"
            )
        
        with col4:
            unmatched = stats.get("unmatched_extracted_count", 0)
            st.metric(
                "Unmatched Invoices",
                unmatched,
                delta=f"-{unmatched}",
                delta_color="inverse"
            )
        
        # Row 2: Field-level statistics
        st.markdown("### Field Evaluation")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Total Fields Evaluated",
                stats.get("total_fields", 0)
            )
        
        with col2:
            matched_fields = stats.get("matched_fields_strict_ge_80", 0)
            total_fields = stats.get("total_fields", 1)
            pass_rate = (matched_fields / total_fields * 100) if total_fields > 0 else 0
            st.metric(
                "Fields Passed (≥80%)",
                f"{matched_fields} ({pass_rate:.1f}%)"
            )
        
        with col3:
            st.metric(
                "Mean Field Score",
                f"{stats.get('mean_field_score', 0):.2f}%"
            )
        
        # Unmatched invoices details
        unmatched_ids = result.get("unmatched_extracted_ids", [])
        if unmatched_ids:
            st.markdown("### Unmatched Invoices")
            st.warning(f"{len(unmatched_ids)} invoice(s) could not be matched with ground truth")
            
            with st.expander(f"View Unmatched Invoice IDs ({len(unmatched_ids)})"):
                for inv_id in unmatched_ids[:50]:  # Show first 50
                    st.text(f"• {inv_id}")
                if len(unmatched_ids) > 50:
                    st.text(f"... and {len(unmatched_ids) - 50} more")
        
        st.divider()
        
        # ------------------------------------------------
        # WHAT CHANGED WITH YOUR THRESHOLDS
        # ------------------------------------------------
        
        st.subheader("Threshold Impact on Your Data")
        
        st.caption("This shows how YOUR threshold adjustments affected the scores")
        
        # Calculate what scores would be with default thresholds
        default_thresholds_only = {k: v for k, v in updated_thresholds.items() if k in ["default", "description", "invoice_id", "currency", "business_line", "tax_classification", "tax_regime", "vat_number"]}
        
        # Re-run with just defaults for comparison
        extracted_file.seek(0)
        gt_file.seek(0)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as ext_temp:
            ext_temp.write(extracted_file.read())
            default_ext_path = ext_temp.name
            
        extracted_file.seek(0)
        gt_file.seek(0)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as gt_temp:
            gt_temp.write(gt_file.read())
            default_gt_path = gt_temp.name
        
        default_result = evaluate_func(
            extracted_path=default_ext_path,
            groundtruth_path=default_gt_path,
            schema_name=schema,
            thresholds=None  # Use system defaults
        )
        
        os.unlink(default_ext_path)
        os.unlink(default_gt_path)
        
        # Show comparison
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "With Default Thresholds",
                f"{default_result['overall_accuracy']}%",
                help="System default threshold settings"
            )
        
        with col2:
            st.metric(
                "With Your Thresholds",
                f"{result['overall_accuracy']}%",
                help="Your custom threshold settings"
            )
        
        with col3:
            diff = result['overall_accuracy'] - default_result['overall_accuracy']
            st.metric(
                "Impact",
                f"{diff:+.2f}%",
                delta=f"{diff:+.2f}%",
                delta_color="normal" if diff >= 0 else "inverse"
            )
        
        # Section-level impact
        st.markdown("**Section-Level Impact:**")
        
        default_section_acc = default_result.get('section_accuracy', {})
        your_section_acc = result.get('section_accuracy', {})
        
        for section in sorted(set(list(default_section_acc.keys()) + list(your_section_acc.keys()))):
            default_acc = default_section_acc.get(section, 0)
            your_acc = your_section_acc.get(section, 0)
            impact = your_acc - default_acc
            
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.write(f"{section.replace('_', ' ').title()}")
            with col2:
                st.write(f"Default: {default_acc:.1f}%")
            with col3:
                if impact > 0.5:
                    st.success(f"+{impact:.1f}% ↑")
                elif impact < -0.5:
                    st.error(f"{impact:.1f}% ↓")
                else:
                    st.info(f"{impact:+.1f}%")
        
        st.caption(
            "💡 If impact is small, it means most fields in your data are either exact matches (100%) "
            "or complete mismatches (0%). Thresholds mainly affect fields with partial matches (40-90%)."
        )
        
        # ------------------------------------------------
        # THRESHOLD OPTIMIZATION SUGGESTIONS
        # ------------------------------------------------
        
        st.subheader("Threshold Optimization Insights")
        
        st.caption("Fields where adjusting thresholds would have the most impact")
        
        # Find fields that are close to threshold boundaries
        field_accuracy = result.get("field_accuracy", {})
        field_pass_rate = result.get("field_pass_rate", {})
        
        # Categorize fields by their improvement potential
        high_impact = []
        medium_impact = []
        
        for field, acc in field_accuracy.items():
            current_threshold = updated_thresholds.get(field, updated_thresholds.get("default", 85))
            
            # Fields within 10-20 points of threshold are most sensitive
            diff = abs(acc - current_threshold)
            
            if 5 <= diff <= 20 and acc < 95:
                # This field's score is close to threshold - adjusting will help
                impact = "high" if acc < 70 else "medium"
                
                # Calculate potential improvement
                if acc < current_threshold:
                    # Lowering threshold would boost this field
                    potential_boost = min(20, current_threshold - acc)
                    high_impact.append({
                        "field": field,
                        "current_acc": acc,
                        "threshold": current_threshold,
                        "suggestion": f"Lower threshold to {int(acc - 5)} to boost score",
                        "impact": impact
                    })
                else:
                    # Field is above threshold but could be stricter
                    high_impact.append({
                        "field": field,
                        "current_acc": acc,
                        "threshold": current_threshold,
                        "suggestion": f"Could increase threshold to {int(acc - 5)} for stricter matching",
                        "impact": "low"
                    })
        
        if high_impact:
            # Show top 5 most impactful fields
            st.markdown("**Fields where threshold adjustments would make a difference:**")
            
            for item in sorted(high_impact, key=lambda x: x["current_acc"])[:5]:
                col1, col2, col3 = st.columns([3, 1, 4])
                with col1:
                    st.write(f"**{item['field']}**")
                with col2:
                    st.write(f"Score: {item['current_acc']:.1f}%")
                with col3:
                    st.caption(item["suggestion"])
        else:
            st.info("Most fields are either well above or well below thresholds. Small adjustments won't significantly change scores. Focus on improving data extraction quality instead.")
        
        st.caption(
            "💡 **Key Insight**: Thresholds only affect fields where the score is NEAR the threshold value. "
            "Fields scoring 100% or 0% won't change with threshold adjustments. "
            "Focus on fields scoring 60-90% for maximum impact."
        )
        
        # ------------------------------------------------
        # THRESHOLD SENSITIVITY ANALYSIS
        # ------------------------------------------------
        
        st.subheader("Threshold Impact Analysis")
        
        st.caption("See how your current thresholds compare to stricter/lenient settings")
        
        # Run comparison with different threshold levels
        current_overall = result['overall_accuracy']
        
        # Strict version (+10 points to all thresholds)
        strict_thresholds_test = {k: min(100, v + 10) for k, v in updated_thresholds.items()}
        from app.main import evaluate as evaluate_func
        import tempfile
        import os
        
        # Reset file pointers and save temp files for re-evaluation
        extracted_file.seek(0)
        gt_file.seek(0)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as ext_temp:
            ext_temp.write(extracted_file.read())
            ext_path = ext_temp.name
            
        extracted_file.seek(0)
        gt_file.seek(0)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as gt_temp:
            gt_temp.write(gt_file.read())
            gt_path = gt_temp.name
        
        strict_result = evaluate_func(
            extracted_path=ext_path,
            groundtruth_path=gt_path,
            schema_name=schema,
            thresholds=strict_thresholds_test
        )
        
        # Reset file pointers again for lenient test
        extracted_file.seek(0)
        gt_file.seek(0)
        
        lenient_thresholds_test = {k: max(50, v - 10) for k, v in updated_thresholds.items()}
        lenient_result = evaluate_func(
            extracted_path=ext_path,
            groundtruth_path=gt_path,
            schema_name=schema,
            thresholds=lenient_thresholds_test
        )
        
        # Clean up temp files
        os.unlink(ext_path)
        os.unlink(gt_path)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Strict (+10 threshold)",
                f"{strict_result['overall_accuracy']}%",
                delta=f"{strict_result['overall_accuracy'] - current_overall:.2f}%"
            )
        
        with col2:
            st.metric(
                "Current Settings",
                f"{current_overall}%"
            )
        
        with col3:
            st.metric(
                "Lenient (-10 threshold)",
                f"{lenient_result['overall_accuracy']}%",
                delta=f"{lenient_result['overall_accuracy'] - current_overall:.2f}%"
            )
        
        st.caption(
            "This shows how much scores would change with stricter or more lenient thresholds. "
            "If the differences are small, your data has high accuracy. "
            "If large, thresholds significantly impact scoring."
        )

        # --------------------------------------------
        # OVERALL METRIC
        # --------------------------------------------

        c_ov, c_st = st.columns(2)

        with c_ov:

            st.metric(
                "Overall score (mean)",
                f"{result['overall_accuracy']}%",
            )

        with c_st:

            st.metric(
                "Strict pass (score ≥ 80)",
                f"{result.get('strict_pass_rate', 0)}%",
            )

        st.caption(
            "Overall score is the micro-average of per-field comparison scores. "
            "Strict pass is the share of comparisons that met the 80-point bar."
        )

        # --------------------------------------------
        # SECTION ACCURACY
        # --------------------------------------------

        st.subheader("Section Accuracy")

        section_accuracy = result.get(
            "section_accuracy",
            {}
        )

        if section_accuracy:

            cols = st.columns(
                min(len(section_accuracy), 4)
            )

            for idx, (section, acc) in enumerate(
                section_accuracy.items()
            ):

                with cols[idx % len(cols)]:

                    st.metric(
                        section.replace("_", " ").title(),
                        f"{round(acc, 2)}%"
                    )

        else:

            st.info("No section accuracy available")

        # --------------------------------------------
        # FIELD ACCURACY TABLE
        # --------------------------------------------

        st.subheader("Field scores (mean)")

        field_accuracy = result.get(
            "field_accuracy",
            {}
        )

        field_pass_rate = result.get(
            "field_pass_rate",
            {},
        )

        if field_accuracy:

            sorted_fields = sorted(
                field_accuracy.items(),
                key=lambda x: x[1]
            )

            for field, acc in sorted_fields:

                # ------------------------------------
                # STATUS COLORS
                # ------------------------------------

                if acc >= 95:
                    emoji = "🟢"

                elif acc >= 80:
                    emoji = "🟡"

                else:
                    emoji = "🔴"

                pass_pct = field_pass_rate.get(field)

                pass_note = (
                    f" · strict ≥80: {round(pass_pct, 1)}%"
                    if pass_pct is not None
                    else ""
                )

                st.write(
                    f"{emoji} "
                    f"**{field}** : "
                    f"{round(acc, 2)}%{pass_note}"
                )

                st.progress(min(acc / 100, 1.0))

        else:

            st.warning("No field accuracy found")

        # --------------------------------------------
        # DOWNLOAD REPORT
        # --------------------------------------------

        st.subheader("Download report")

        st.caption(
            "Export a print-ready HTML summary (open in a browser, or Print → Save as PDF) "
            "and a CSV of field-level scores for spreadsheets."
        )

        report_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_html = build_evaluation_report_html(
            result,
            schema_name=schema,
            default_result=default_result,
            strict_result=strict_result,
            lenient_result=lenient_result,
            thresholds_used=updated_thresholds,
        )
        report_bytes = report_html.encode("utf-8")
        field_csv = build_field_scores_csv(result).encode("utf-8")

        dl1, dl2 = st.columns(2)

        with dl1:

            st.download_button(
                label="Download evaluation report (HTML)",
                data=report_bytes,
                file_name=f"invoice_evaluation_report_{schema}_{report_ts}.html",
                mime="text/html; charset=utf-8",
                use_container_width=True,
            )

        with dl2:

            st.download_button(
                label="Download field scores (CSV)",
                data=field_csv,
                file_name=f"invoice_evaluation_field_scores_{schema}_{report_ts}.csv",
                mime="text/csv; charset=utf-8",
                use_container_width=True,
            )

        # --------------------------------------------
        # RAW JSON OUTPUT
        # --------------------------------------------

        with st.expander("Raw Evaluation Output"):

            st.json(result)