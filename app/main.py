from collections import defaultdict

from app.evaluator.comparator import compare_field
from app.evaluator.matcher import match_items
from app.evaluator.matcher import match_tax_rows
from app.evaluator.metrics import MetricsTracker
from app.evaluator.report_generator import generate_report
from app.utils.invoice_eval_io import build_groundtruth_map
from app.utils.invoice_eval_io import coerce_extracted_invoices
from app.utils.invoice_eval_io import find_gt_invoice
from app.utils.loaders import load_eval_config
from app.utils.loaders import load_json
from app.utils.loaders import load_matching_weights
from app.utils.loaders import load_thresholds
from app.utils.schema_shape_validate import validate_upload_against_schema


def _get_field_weight(field_name, eval_config):
    """
    Get importance weight for a field based on eval config or defaults.
    Critical fields (amounts, IDs) get higher weights.
    """
    field_lower = field_name.lower()
    
    # Check if config has explicit weights
    field_weights = eval_config.get("field_weights", {})
    if field_name in field_weights:
        return field_weights[field_name]
    
    # Extract base field name for dotted fields
    base_field = field_name.split(".")[-1] if "." in field_name else field_name
    if base_field in field_weights:
        return field_weights[base_field]
    
    # Default weight hierarchy
    if any(x in field_lower for x in ["invoice_id", "total_amount", "gross_amount"]):
        return 1.5  # Critical fields
    elif any(x in field_lower for x in ["net_amount", "tax_amount", "currency"]):
        return 1.3  # Important fields
    elif any(x in field_lower for x in ["date", "description"]):
        return 1.2  # Medium importance
    else:
        return 1.0  # Default weight


def _object_sections(eval_config):

    array_names = set(eval_config.get("array_sections", []))

    explicit = eval_config.get("object_sections")

    if explicit is not None:
        return explicit

    return [
        s
        for s in eval_config.get("sections", [])
        if s not in array_names
    ]


def _rate_field_for_section(section_name, match_rules):

    rule = match_rules.get(section_name, {})

    keys = rule.get("match_by", [])

    if keys:
        return keys[0]

    if section_name == "header_tax_details":
        return "header_tax_rate"

    return "tax_rate"


def _match_array_rows(section_name, ext_items, gt_items, weights, match_rules, thresholds=None):

    if section_name == "items":
        return match_items(ext_items, gt_items, weights, thresholds)

    rate_field = _rate_field_for_section(section_name, match_rules)

    return match_tax_rows(ext_items, gt_items, rate_field)


def _count_field_update(
    acc,
    metrics,
    qualified_field,
    total_fields,
    matched_fields,
    score_sum,
    section_totals,
    section_counts,
    section_weight_totals,
    section_key,
    weight=1.0,
):

    # Apply weight to the score for overall calculation
    weighted_acc = acc * weight

    metrics.update(qualified_field, acc)

    total_fields[0] += 1
    score_sum[0] += float(weighted_acc)
    
    # For section accuracy: track both weighted and unweighted scores
    # This allows us to calculate proper averages that don't exceed 100%
    section_totals[section_key] += acc  # Unweighted sum for section average
    section_weight_totals[section_key] += weight  # Track total weight
    section_counts[section_key] += 1

    if acc >= 80:
        matched_fields[0] += 1


def evaluate(
    extracted_path,
    groundtruth_path,
    schema_name,
    thresholds=None,
):

    extracted_raw = load_json(extracted_path)

    groundtruth_raw = load_json(groundtruth_path)

    validate_upload_against_schema(
        extracted_raw,
        groundtruth_raw,
        schema_name,
    )

    extracted = coerce_extracted_invoices(extracted_raw)

    gt_map = build_groundtruth_map(groundtruth_raw)

    if isinstance(groundtruth_raw, list):
        gt_record_count = len(groundtruth_raw)
    else:
        gt_record_count = 1

    base_thresholds = load_thresholds(schema_name)

    if thresholds is None:
        merged_thresholds = base_thresholds
    else:
        merged_thresholds = {**base_thresholds, **thresholds}

    eval_config = load_eval_config(schema_name)

    top_fields = eval_config.get("top_level_fields", [])

    array_sections = eval_config.get("array_sections", [])

    object_sections = _object_sections(eval_config)

    match_rules = eval_config.get("match_rules", {})

    weights = load_matching_weights()["items"]

    metrics = MetricsTracker()

    total_fields = [0]

    matched_fields = [0]

    score_sum = [0.0]

    section_totals = defaultdict(float)

    section_counts = defaultdict(int)
    
    section_weight_totals = defaultdict(float)

    invoice_accuracy = {}

    unmatched_invoices = []

    matched_invoice_count = 0

    for ext_inv in extracted:

        if not isinstance(ext_inv, dict):
            continue

        inv_id = str(ext_inv.get("invoice_id", "")).strip()

        if not inv_id:
            unmatched_invoices.append("<missing_invoice_id>")
            continue

        gt_inv = find_gt_invoice(inv_id, gt_map)

        if gt_inv is None:
            unmatched_invoices.append(inv_id)
            continue

        matched_invoice_count += 1

        invoice_total = 0

        invoice_score_sum = 0.0

        report_id = str(gt_inv.get("invoice_id", inv_id)).strip() or inv_id

        for field in top_fields:
            weight = _get_field_weight(field, eval_config)

            acc = compare_field(
                ext_inv.get(field),
                gt_inv.get(field),
                field,
                merged_thresholds,
            )

            invoice_score_sum += float(acc)

            _count_field_update(
                acc,
                metrics,
                field,
                total_fields,
                matched_fields,
                score_sum,
                section_totals,
                section_counts,
                section_weight_totals,
                "top_level_fields",
                weight,
            )

            invoice_total += 1

        for section in object_sections:

            ext_sec = ext_inv.get(section) or {}

            gt_sec = gt_inv.get(section) or {}

            if not isinstance(ext_sec, dict):
                ext_sec = {}

            if not isinstance(gt_sec, dict):
                gt_sec = {}

            all_keys = set(gt_sec.keys()) | set(ext_sec.keys())

            for key in all_keys:
                qualified_field = f"{section}.{key}"
                weight = _get_field_weight(qualified_field, eval_config)

                acc = compare_field(
                    ext_sec.get(key),
                    gt_sec.get(key),
                    qualified_field,
                    merged_thresholds,
                )

                invoice_score_sum += float(acc)

                _count_field_update(
                    acc,
                    metrics,
                    qualified_field,
                    total_fields,
                    matched_fields,
                    score_sum,
                    section_totals,
                    section_counts,
                    section_weight_totals,
                    section,
                    weight,
                )

                invoice_total += 1

        for section in array_sections:

            ext_items = ext_inv.get(section)

            gt_items = gt_inv.get(section)

            if ext_items is None:
                ext_items = []

            if gt_items is None:
                gt_items = []

            if not gt_items:
                continue

            if not isinstance(ext_items, list):
                ext_items = []

            if not isinstance(gt_items, list):
                gt_items = []

            row_matches = _match_array_rows(
                section,
                ext_items,
                gt_items,
                weights,
                match_rules,
                merged_thresholds,
            )

            for match in row_matches:

                gt_index = match.get("gt_index")

                ext_index = match.get("ext_index")

                if gt_index is None or gt_index >= len(gt_items):
                    continue

                gt_item = gt_items[gt_index]

                if ext_index is not None and ext_index < len(ext_items):
                    ext_item = ext_items[ext_index]
                else:
                    ext_item = {}

                if not isinstance(gt_item, dict):
                    continue

                if not isinstance(ext_item, dict):
                    ext_item = {}

                row_keys = set(gt_item.keys()) | set(ext_item.keys())

                for key in row_keys:
                    qualified_field = f"{section}.{key}"
                    weight = _get_field_weight(qualified_field, eval_config)

                    acc = compare_field(
                        ext_item.get(key),
                        gt_item.get(key),
                        qualified_field,
                        merged_thresholds,
                    )

                    invoice_score_sum += float(acc)

                    _count_field_update(
                        acc,
                        metrics,
                        qualified_field,
                        total_fields,
                        matched_fields,
                        score_sum,
                        section_totals,
                        section_counts,
                        section_weight_totals,
                        section,
                        weight,
                    )

                    invoice_total += 1

        if invoice_total > 0:
            invoice_accuracy[report_id] = round(
                invoice_score_sum / invoice_total,
                2,
            )
        else:
            invoice_accuracy[report_id] = 0.0

    if total_fields[0] > 0:
        overall_accuracy = score_sum[0] / total_fields[0]
        strict_pass_rate = (matched_fields[0] / total_fields[0]) * 100
    else:
        overall_accuracy = 0.0
        strict_pass_rate = 0.0

    section_accuracy = {}

    for section in section_totals:
        # Calculate section accuracy using unweighted average
        # This ensures scores stay within 0-100% range
        if section_counts[section] > 0:
            section_accuracy[section] = round(
                section_totals[section] / section_counts[section],
                2,
            )
        else:
            section_accuracy[section] = 0.0

    summary = {
        "overall_accuracy": round(overall_accuracy, 2),
        "strict_pass_rate": round(strict_pass_rate, 2),
        "invoice_accuracy": invoice_accuracy,
        "field_accuracy": metrics.generate(),
        "field_pass_rate": metrics.pass_rates(),
        "section_accuracy": section_accuracy,
        "stats": {
            "total_invoices_extracted": len(extracted),
            "total_invoices_matched": matched_invoice_count,
            "total_ground_truth_records": gt_record_count,
            "unmatched_extracted_count": len(unmatched_invoices),
            "total_fields": total_fields[0],
            "matched_fields_strict_ge_80": matched_fields[0],
            "mean_field_score": round(overall_accuracy, 2),
        },
        "unmatched_extracted_ids": unmatched_invoices[:200],
    }

    generate_report(
        summary,
        "app/reports/report.json",
    )

    return summary


if __name__ == "__main__":

    result = evaluate(
        "sample_data/extracted.json",
        "sample_data/groundtruth.json",
        "global",
    )

    print(result)
