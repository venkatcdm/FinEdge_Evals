import os
from datetime import datetime


def safe_divide(a, b, default=0):

    try:
        if b == 0:
            return default

        return a / b

    except:
        return default


def percentage(part, total):

    return round(
        safe_divide(part * 100, total),
        2
    )


def current_timestamp():

    return datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )


def ensure_directory(path):

    if not os.path.exists(path):
        os.makedirs(path)


def accuracy_bucket(score):

    if score >= 95:
        return "Excellent"

    elif score >= 85:
        return "Good"

    elif score >= 70:
        return "Average"

    elif score >= 50:
        return "Poor"

    return "Very Poor"


def flatten_dict(
    data,
    parent_key='',
    sep='.'
):

    items = []

    for key, value in data.items():

        new_key = (
            f"{parent_key}{sep}{key}"
            if parent_key
            else key
        )

        if isinstance(value, dict):

            items.extend(
                flatten_dict(
                    value,
                    new_key,
                    sep
                ).items()
            )

        else:
            items.append(
                (new_key, value)
            )

    return dict(items)


def remove_none_values(data):

    if isinstance(data, dict):

        return {
            k: remove_none_values(v)
            for k, v in data.items()
            if v is not None
        }

    elif isinstance(data, list):

        return [
            remove_none_values(item)
            for item in data
            if item is not None
        ]

    return data


def generate_report_filename(schema):

    timestamp = current_timestamp()

    return (
        f"report_{schema}_{timestamp}.json"
    )