from collections import defaultdict


class MetricsTracker:

    def __init__(self):

        self.field_stats = defaultdict(
            lambda: {
                "total": 0,
                "matched": 0,
                "score_sum": 0.0,
            }
        )

    def update(self, field, accuracy):

        self.field_stats[field]["total"] += 1
        self.field_stats[field]["score_sum"] += float(accuracy)

        if accuracy >= 80:
            self.field_stats[field]["matched"] += 1

    def generate(self):

        result = {}

        for field, stats in self.field_stats.items():

            total = stats["total"]
            if total <= 0:
                continue

            result[field] = round(stats["score_sum"] / total, 2)

        return result

    def pass_rates(self):

        out = {}
        for field, stats in self.field_stats.items():
            total = stats["total"]
            if total <= 0:
                continue
            out[field] = round(stats["matched"] / total * 100, 2)
        return out
