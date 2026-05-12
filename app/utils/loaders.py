import json

def load_json(path):

    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_schema(schema_name):

    path = f"app/schemas/{schema_name}_schema.json"

    return load_json(path)


def load_thresholds(schema_name):

    data = load_json(
        "app/configs/fuzzy_thresholds.json"
    )

    merged = dict(data.get("global", {}))
    merged.update(data.get(schema_name, {}))
    return merged


def load_matching_weights():

    return load_json(
        "app/configs/matching_weights.json"
    )

def load_eval_config(schema_name):

    path = f"app/eval_configs/{schema_name}_eval.json"

    return load_json(path)