import json
from datetime import datetime

def generate_report(summary, output_path):

    report = {
        "generated_at": str(datetime.now()),
        "overall_accuracy": summary["overall_accuracy"],
        "section_accuracy": summary["section_accuracy"],
        "field_accuracy": summary["field_accuracy"]
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4)

    return report