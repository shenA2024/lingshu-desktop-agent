"""Summarize observed verification without changing upstream predictions."""
from collections import defaultdict

MODE_LABELS = {
    "exact": "点位置外推（仍有容差）",
    "bounded_noisy": "方向外推与扰动容差",
    "bounded_stochastic": "随机运动可达域覆盖",
    "chase_stochastic": "追逐随机目标的可达域覆盖",
}


def summarize(verifications):
    groups = defaultdict(lambda: {"hits": 0, "verified": 0, "pending": 0, "distance_sum": 0.0, "distance_max": None, "bound_sum": 0.0, "bound_max": None})
    for verification in verifications:
        for detail in (verification or {}).get("details", []):
            group = groups[detail["mode"]]
            if detail.get("status") == "pending" or detail.get("actual") is None:
                group["pending"] += 1
                continue
            group["verified"] += 1
            group["hits"] += int(detail["hit"] is True)
            group["distance_sum"] += detail["distance"]
            group["bound_sum"] += detail["bound"]
            group["distance_max"] = max(group["distance_max"] or 0, detail["distance"])
            group["bound_max"] = max(group["bound_max"] or 0, detail["bound"])
    output = []
    for mode, group in sorted(groups.items()):
        count = group["verified"]
        output.append({"mode": mode, "label": MODE_LABELS.get(mode, mode),
            "hits": group["hits"], "verified": count, "pending": group["pending"],
            "hit_rate": round(group["hits"] / count, 4) if count else None,
            "mean_distance": round(group["distance_sum"] / count, 4) if count else None,
            "max_distance": group["distance_max"],
            "mean_bound": round(group["bound_sum"] / count, 4) if count else None,
            "max_bound": group["bound_max"]})
    hits = sum(g["hits"] for g in output)
    verified = sum(g["verified"] for g in output)
    return {"hits": hits, "verified": verified, "pending": sum(g["pending"] for g in output),
            "hit_rate": round(hits / verified, 4) if verified else None,
            "unit": "scene_unit", "groups": output}


def refresh(run):
    # Supports old stored runs; graph state is never treated as observation.
    run["statistics"] = summarize(f.get("verification") for f in run["frames"])
