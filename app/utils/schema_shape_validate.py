"""
Validate invoice JSON instances against the JSON Schema *shape* for a region:
required keys must be present; when additionalProperties is false, no extra keys.
Primitive types are not enforced (extractors may use strings vs numbers).
"""

from __future__ import annotations

import unicodedata
from typing import Any, List, Mapping, MutableMapping, Sequence

from app.utils.invoice_eval_io import coerce_extracted_invoices
from app.utils.loaders import load_schema


class SchemaMismatchError(ValueError):
    """Raised when uploaded data does not match the selected schema shape."""

    def __init__(self, message: str, errors: List[str]):
        super().__init__(message)
        self.errors = errors


def _as_object_schema(subschema: Any) -> MutableMapping[str, Any] | None:
    if not isinstance(subschema, dict):
        return None
    if subschema.get("type") == "object" or "properties" in subschema:
        return subschema
    return None


def _validate_shape(instance: Any, subschema: Any, path: str) -> List[str]:
    errors: List[str] = []

    if not isinstance(subschema, dict):
        return errors

    if "anyOf" in subschema:
        branches = subschema["anyOf"]
        if not isinstance(branches, list) or not branches:
            return errors
        for branch in branches:
            if not _validate_shape(instance, branch, path):
                return []
        return [
            f"{path}: value does not match any allowed form (anyOf "
            f"{len(branches)} alternatives)"
        ]

    obj = _as_object_schema(subschema)
    if obj is not None:
        if not isinstance(instance, dict):
            return [f"{path}: expected object, got {type(instance).__name__}"]

        props = obj.get("properties")
        if not isinstance(props, dict):
            props = {}

        required = obj.get("required")
        if not isinstance(required, list):
            required = []

        addl = obj.get("additionalProperties", True)
        disallow_extra = addl is False

        for key in required:
            if key not in instance:
                errors.append(f"{path}.{key}: required by schema but missing")

        if disallow_extra:
            for key in instance:
                if key not in props:
                    errors.append(
                        f"{path}.{key}: not defined for this schema "
                        f"(selected region does not allow this field)"
                    )

        for key, val in instance.items():
            if key in props:
                errors.extend(_validate_shape(val, props[key], f"{path}.{key}"))
        return errors

    if subschema.get("type") == "array":
        if not isinstance(instance, list):
            return [f"{path}: expected array, got {type(instance).__name__}"]
        items = subschema.get("items", {})
        for i, item in enumerate(instance):
            errors.extend(_validate_shape(item, items, f"{path}[{i}]"))
        return errors

    return errors


def _groundtruth_invoice_dicts(raw: Any) -> List[Mapping[str, Any]]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        return [raw]
    return []


def _shape_errors_for_invoices(
    invoices: Sequence[Mapping[str, Any]],
    schema_name: str,
    path_prefix: str,
    *,
    max_errors: int,
) -> List[str]:
    schema = load_schema(schema_name)
    errors: List[str] = []
    for i, inv in enumerate(invoices):
        errors.extend(_validate_shape(inv, schema, f"{path_prefix}[{i}]"))
        if len(errors) >= max_errors:
            return errors[:max_errors]
    return errors[:max_errors]


def collect_schema_shape_errors(
    extracted_raw: Any,
    groundtruth_raw: Any,
    schema_name: str,
    *,
    max_errors: int = 80,
) -> List[str]:
    errors: List[str] = []

    extracted_invoices = coerce_extracted_invoices(extracted_raw)
    errors.extend(
        _shape_errors_for_invoices(
            extracted_invoices, schema_name, "extracted", max_errors=max_errors
        )
    )
    if len(errors) >= max_errors:
        return errors[:max_errors]

    gt_invoices = _groundtruth_invoice_dicts(groundtruth_raw)
    errors.extend(
        _shape_errors_for_invoices(
            gt_invoices,
            schema_name,
            "ground_truth",
            max_errors=max_errors - len(errors),
        )
    )

    return errors[:max_errors]


_INVOICE_CORE_TOP_LEVEL_KEYS = ("merchant", "bill_to", "invoice_id", "items")


def _minimal_invoice_errors(
    invoices: Sequence[Mapping[str, Any]],
    path_prefix: str,
    *,
    max_errors: int,
) -> List[str]:
    """
    Lenient structural check used for every region: each invoice must be an
    object that has merchant + bill_to + invoice_id + items, but optional
    region-specific keys (mpa_*_date, electronic_uid, fiscal_regime, expanded
    tax breakdown fields, first_name/last_name, etc.) may or may not be
    present. Region selection is then enforced via dataset-level ``country``
    matching.
    """
    errors: List[str] = []
    for i, inv in enumerate(invoices):
        path = f"{path_prefix}[{i}]"
        if not isinstance(inv, dict):
            errors.append(f"{path}: expected object, got {type(inv).__name__}")
            if len(errors) >= max_errors:
                return errors[:max_errors]
            continue

        for key in _INVOICE_CORE_TOP_LEVEL_KEYS:
            if key not in inv:
                errors.append(
                    f"{path}.{key}: required basic invoice field is missing"
                )
                if len(errors) >= max_errors:
                    return errors[:max_errors]

        merchant = inv.get("merchant")
        if merchant is not None and not isinstance(merchant, dict):
            errors.append(
                f"{path}.merchant: expected object, got {type(merchant).__name__}"
            )
        bill_to = inv.get("bill_to")
        if bill_to is not None and not isinstance(bill_to, dict):
            errors.append(
                f"{path}.bill_to: expected object, got {type(bill_to).__name__}"
            )
        items = inv.get("items")
        if items is not None and not isinstance(items, list):
            errors.append(
                f"{path}.items: expected array, got {type(items).__name__}"
            )

        if len(errors) >= max_errors:
            return errors[:max_errors]

    return errors[:max_errors]


def _validate_upload_against_schema_shape_only(
    extracted_raw: Any,
    groundtruth_raw: Any,
    schema_name: str,
) -> None:
    """
    Raises SchemaMismatchError if either payload is not a list of invoice-
    shaped objects (must contain merchant, bill_to, invoice_id, items).

    Strict per-region property whitelisting via ``additionalProperties: false``
    is intentionally NOT enforced because the same upstream extractor emits
    extra optional fields (``first_name``, ``last_name``, ``mpa_*``,
    ``electronic_uid``, ``fiscal_regime``, ``province_code``, …) for every
    region. Region routing is enforced separately by ``_validate_region_country``
    for ``germany`` / ``uk``.
    """
    extracted_invoices = coerce_extracted_invoices(extracted_raw)
    gt_invoices = _groundtruth_invoice_dicts(groundtruth_raw)

    errors: List[str] = []
    errors.extend(
        _minimal_invoice_errors(extracted_invoices, "extracted", max_errors=80)
    )
    if len(errors) < 80:
        errors.extend(
            _minimal_invoice_errors(
                gt_invoices, "ground_truth", max_errors=80 - len(errors)
            )
        )

    if not extracted_invoices and not gt_invoices:
        errors.append(
            "extracted/ground_truth: no invoice objects found in the uploaded JSON"
        )

    if errors:
        raise SchemaMismatchError(
            f"Uploaded data does not have the basic invoice shape required for "
            f"'{schema_name}' (each record must include merchant, bill_to, "
            "invoice_id, and items).",
            errors,
        )


def _normalize_country(v: Any) -> str:
    if v is None:
        return ""
    raw = str(v).strip().lower()
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", raw)
        if not unicodedata.combining(ch)
    )


_GLOBAL_TOKENS = (
    "canada",
    "united states",
    "united states of america",
    "puerto rico",
    "mexico",
)
_GLOBAL_CODES = {"ca", "can", "us", "usa", "pr", "pri", "mx", "mex"}

_GERMANY_TOKENS = (
    "germany",
    "deutschland",
    "federal republic of germany",
    "bundesrepublik deutschland",
)
_GERMANY_CODES = {"de", "deu", "ger"}

_UK_TOKENS = (
    "united kingdom",
    "great britain",
    "england",
    "scotland",
    "wales",
    "northern ireland",
)
_UK_CODES = {"uk", "gb", "gbr", "uk-eng", "uk-sct", "uk-wls", "uk-nir"}


def _country_matches_schema(country_value: str, schema_name: str) -> bool:
    cv = _normalize_country(country_value)
    if not cv:
        return False

    if schema_name == "global":
        if cv in _GLOBAL_CODES:
            return True
        return any(tok in cv for tok in _GLOBAL_TOKENS)

    if schema_name == "germany":
        if cv in _GERMANY_CODES:
            return True
        return any(tok in cv for tok in _GERMANY_TOKENS)

    if schema_name == "uk":
        if cv in _UK_CODES:
            return True
        return any(tok in cv for tok in _UK_TOKENS)

    return True


def _read_path(obj: Any, parts: Sequence[str]) -> Any:
    cur: Any = obj
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur.get(p)
    return cur


def _dataset_region_match(
    invoices: Sequence[Mapping[str, Any]], schema_name: str
) -> tuple[int, int]:
    """
    Returns ``(matches, with_country)`` across all invoices' merchant/bill_to
    country fields. An invoice contributes to ``matches`` if either of its
    countries clearly maps to the selected region.
    """
    matches = 0
    with_country = 0
    for inv in invoices:
        mc = _read_path(inv, ["merchant", "country"])
        bc = _read_path(inv, ["bill_to", "country"])
        if _normalize_country(mc) or _normalize_country(bc):
            with_country += 1
        if _country_matches_schema(mc, schema_name) or _country_matches_schema(
            bc, schema_name
        ):
            matches += 1
    return matches, with_country


def _validate_region_country(
    extracted_raw: Any,
    groundtruth_raw: Any,
    schema_name: str,
    *,
    max_errors: int = 40,
) -> List[str]:
    """
    Region routing is only enforced for ``global``. In this app, ``global`` is
    the Americas bucket (Canada / NA / Mexico), not a catch-all for Germany or
    UK. Germany and UK uploads often contain city names or cross-border vendor
    countries in ``merchant.country`` / ``bill_to.country``, so those schemas
    trust the user's schema selection after the basic invoice shape check.
    """
    if schema_name != "global":
        return []

    extracted_invoices = coerce_extracted_invoices(extracted_raw)
    gt_invoices = _groundtruth_invoice_dicts(groundtruth_raw)

    ext_matches, ext_with_country = _dataset_region_match(
        extracted_invoices, schema_name
    )
    gt_matches, gt_with_country = _dataset_region_match(gt_invoices, schema_name)

    errors: List[str] = []

    if ext_with_country > 0 and ext_matches == 0:
        errors.append(
            f"extracted file: none of the {ext_with_country} invoice(s) with a "
            f"populated country field map to '{schema_name}'."
        )
    if gt_with_country > 0 and gt_matches == 0:
        errors.append(
            f"ground_truth file: none of the {gt_with_country} invoice(s) with a "
            f"populated country field map to '{schema_name}'."
        )

    return errors[:max_errors]


def validate_upload_against_schema(
    extracted_raw: Any,
    groundtruth_raw: Any,
    schema_name: str,
) -> None:
    """
    Raises SchemaMismatchError if either payload violates:
    1) the basic invoice shape constraints, and
    2) dataset-level region country requirements.
    """
    # 1) shape validation (basic invoice object / array requirements)
    _validate_upload_against_schema_shape_only(
        extracted_raw,
        groundtruth_raw,
        schema_name,
    )

    # 2) dataset-level region country validation
    country_errs = _validate_region_country(
        extracted_raw,
        groundtruth_raw,
        schema_name,
    )
    if country_errs:
        raise SchemaMismatchError(
            f"Uploaded data matches the '{schema_name}' structure but not the region country requirement.",
            country_errs,
        )
