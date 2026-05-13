"""
Validate invoice JSON instances against the JSON Schema *shape* for a region:
required keys must be present; when additionalProperties is false, no extra keys.
Primitive types are not enforced (extractors may use strings vs numbers).
"""

from __future__ import annotations

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


def collect_schema_shape_errors(
    extracted_raw: Any,
    groundtruth_raw: Any,
    schema_name: str,
    *,
    max_errors: int = 80,
) -> List[str]:
    schema = load_schema(schema_name)
    errors: List[str] = []

    extracted_invoices = coerce_extracted_invoices(extracted_raw)
    for i, inv in enumerate(extracted_invoices):
        errors.extend(_validate_shape(inv, schema, f"extracted[{i}]"))
        if len(errors) >= max_errors:
            return errors[:max_errors]

    gt_invoices = _groundtruth_invoice_dicts(groundtruth_raw)
    for i, inv in enumerate(gt_invoices):
        errors.extend(_validate_shape(inv, schema, f"ground_truth[{i}]"))
        if len(errors) >= max_errors:
            return errors[:max_errors]

    return errors[:max_errors]


def validate_upload_against_schema(
    extracted_raw: Any,
    groundtruth_raw: Any,
    schema_name: str,
) -> None:
    """
    Raises SchemaMismatchError if either payload violates the schema shape
    for ``schema_name`` (global / germany / uk).
    """
    errs = collect_schema_shape_errors(extracted_raw, groundtruth_raw, schema_name)
    if errs:
        cap_note = ""
        if len(errs) >= 80:
            cap_note = " (showing first 80 issues)"
        raise SchemaMismatchError(
            f"Data does not match the '{schema_name}' schema{cap_note}. "
            "Use the schema that matches your files, or fix the JSON structure.",
            errs,
        )
