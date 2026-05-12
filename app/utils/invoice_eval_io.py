import re
from typing import Any, Dict, List

from app.utils.normalization import groundtruth_digit_key
from app.utils.normalization import invoice_digits_core
from app.utils.normalization import normalize_invoice_id


def coerce_extracted_invoices(raw: Any) -> List[Dict[str, Any]]:
    """Normalize extracted JSON: list of wrappers with extracted_data or flat invoices."""
    if not isinstance(raw, list):
        return []

    out: List[Dict[str, Any]] = []
    for item in raw:
        if not item or not isinstance(item, dict):
            continue
        if "extracted_data" in item and isinstance(item["extracted_data"], dict):
            inv = dict(item["extracted_data"])
            fn = item.get("file_name") or ""
            if fn and (not inv.get("invoice_id")):
                inv["invoice_id"] = re.sub(
                    r"\.pdf$", "", str(fn), flags=re.IGNORECASE
                )
            out.append(inv)
        elif "invoice_id" in item:
            out.append(item)
    return out


def _gt_alias_keys(invoice_id: str) -> List[str]:
    raw = str(invoice_id).strip()
    if not raw:
        return []
    keys = {raw, raw.replace("-CXP-AN", "").replace("-CXP", "")}
    norm = normalize_invoice_id(raw)
    if norm:
        keys.add(norm)
    keys.discard("")
    return list(keys)


def _is_internal_key(key: str) -> bool:
    return str(key).startswith("__dig__")


def _register_invoice_keys(gt_map: Dict[str, Dict[str, Any]], inv: Dict[str, Any]) -> None:

    iid = inv.get("invoice_id")
    if iid is not None and str(iid).strip() != "":
        raw = str(iid).strip()
        for key in _gt_alias_keys(raw):
            gt_map[key] = inv

        dc = invoice_digits_core(raw)
        dk = groundtruth_digit_key(dc)
        if dk:
            gt_map[dk] = inv

    euid = inv.get("electronic_uid")
    if euid is None or str(euid).strip() == "":
        return

    eraw = str(euid).strip()
    for key in _gt_alias_keys(eraw):
        gt_map[key] = inv

    edc = invoice_digits_core(eraw)
    edk = groundtruth_digit_key(edc)
    if edk:
        gt_map[edk] = inv


def build_groundtruth_map(groundtruth: Any) -> Dict[str, Dict[str, Any]]:
    """Map many possible id strings (and digit cores) to the same invoice dict."""
    gt_list: List[Dict[str, Any]] = []
    if isinstance(groundtruth, list):
        gt_list = [x for x in groundtruth if isinstance(x, dict)]
    elif isinstance(groundtruth, dict):
        gt_list = [groundtruth]

    gt_map: Dict[str, Dict[str, Any]] = {}
    for inv in gt_list:
        _register_invoice_keys(gt_map, inv)
    return gt_map


def find_gt_invoice(extracted_id: str, gt_map: Dict[str, Dict[str, Any]]):
    """Resolve ground-truth invoice for an extracted invoice_id."""
    if not extracted_id:
        return None

    e = str(extracted_id).strip()
    if e in gt_map and not _is_internal_key(e):
        return gt_map[e]

    en = normalize_invoice_id(e)
    if en and en in gt_map and not _is_internal_key(en):
        return gt_map[en]

    for k, inv in gt_map.items():
        if _is_internal_key(k):
            continue
        if normalize_invoice_id(k) == en:
            return inv

    cleaned_e = re.sub(r"[-_\s]", "", e)
    for k, inv in gt_map.items():
        if _is_internal_key(k):
            continue
        if re.sub(r"[-_\s]", "", str(k)) == cleaned_e:
            return inv

    dc = invoice_digits_core(e)
    dk = groundtruth_digit_key(dc)
    if dk and dk in gt_map:
        return gt_map[dk]

    return None
