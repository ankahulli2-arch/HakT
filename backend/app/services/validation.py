"""Живая валидация и бенчмарк подбора.

Валидация прогоняет синтетических кандидатов через ТЕ ЖЕ функции
продуктового CAT-движка (estimate_theta_eap, irt_prob, irt_info,
остановка SE) — цифры считаются продуктовым кодом.
"""
import math
import random

import numpy as np

from app.services.testing.engine import irt_info, irt_prob, estimate_theta_eap

BOUNDS = [-0.5, 0.5, 1.5]


def _grade(t: float) -> int:
    for i, b in enumerate(BOUNDS):
        if t < b:
            return i
    return 3


def _b_rec_lr(pairs, ridge: float = 1e-3):
    """Восстановление сложности: логистическая регрессия ответа на θ кандидата;
    b_rec — θ, где P(верный ответ)=0.5. Градиентный спуск с ridge."""
    xs = np.array([t for t, _ in pairs])
    ys = np.array([1.0 if ok else 0.0 for _, ok in pairs])
    if len(set(ys.tolist())) < 2 or len(xs) < 20:
        return None
    slope, intercept = 0.5, 0.0
    lr = 0.5
    for _ in range(600):
        p = 1.0 / (1.0 + np.exp(-(slope * xs + intercept)))
        g_s = float(np.mean((p - ys) * xs)) + ridge * slope
        g_i = float(np.mean(p - ys))
        slope -= lr * g_s
        intercept -= lr * g_i
        if abs(g_s) < 1e-5 and abs(g_i) < 1e-5:
            break
    if slope <= 1e-4:
        return None
    return round(float(-intercept / slope), 2)


def run_validation(n_people: int = 500, seed: int = 2026) -> dict:
    rng = random.Random(seed)
    n_bank = 60
    a_design = [rng.uniform(0.9, 2.4) for _ in range(n_bank)]
    b_design = sorted(rng.uniform(-2.2, 2.2) for _ in range(n_bank))
    c_design = [0.15 if i % 2 else 0.05 for i in range(n_bank)]
    true_theta = [rng.gauss(0, 1.05) for _ in range(n_people)]

    est1, est2, response_pairs = [], [], {}
    for theta in true_theta:
        ests = []
        for _ in range(2):
            est, hist, avail = 0.0, [], list(range(n_bank))
            for _ in range(20):
                av = np.array(avail)
                info = [irt_info(est, a_design[i], b_design[i], c_design[i]) for i in avail]
                pick = avail[int(np.argmax(info))]
                avail.remove(pick)
                ok = rng.random() < irt_prob(theta, a_design[pick], b_design[pick], c_design[pick])
                hist.append((pick, ok))
                est = estimate_theta_eap([(a_design[i], b_design[i], c_design[i], o) for i, o in hist])
                idxs = [i for i, _ in hist]
                tinfo = sum(irt_info(est, a_design[i], b_design[i], c_design[i]) for i in idxs)
                if tinfo > 0 and 1.0 / math.sqrt(tinfo) <= 0.30:
                    break
            ests.append(est)
            for pick, ok in hist:
                response_pairs.setdefault(pick, []).append((est, ok))
        est1.append(ests[0])
        est2.append(ests[1])

    est1, est2 = np.array(est1), np.array(est2)
    corr = float(np.corrcoef(true_theta, est1)[0, 1])
    rxx = float(np.corrcoef(est1, est2)[0, 1])

    po = float(np.mean([_grade(t) == _grade(e) for t, e in zip(est1, est2)]))
    names = list({_grade(t) for t in est1} | {_grade(e) for e in est2})
    pe = sum(np.mean([_grade(t) == n for t in est1]) * np.mean([_grade(e) == n for e in est2]) for n in names)
    kappa = float((po - pe) / (1 - pe)) if pe < 1 else 1.0

    b_rec = {}
    for i, pairs in response_pairs.items():
        b = _b_rec_lr(pairs)
        if b is not None:
            b_rec[i] = b
    designed = [b_design[i] for i in b_rec]
    recovered = [b_rec[i] for i in b_rec]
    corr_b = float(np.corrcoef(designed, recovered)[0, 1]) if len(designed) > 2 else None

    return {
        "n_candidates": n_people,
        "corr_theta_true": round(corr, 3),
        "reliability_rxx": round(rxx, 3),
        "grade_agreement": round(po, 3),
        "kappa": round(kappa, 3),
        "difficulty_recovery": {
            "corr_b_rec_vs_b_design": round(corr_b, 3) if corr_b is not None else None,
            "items_recovered": f"{len(b_rec)} из {n_bank}",
            "sample": [{"b_design": round(b_design[i], 2), "b_rec": b_rec[i]}
                       for i in list(b_rec)[:5]],
        },
        "note": "Прогон через продуктовые функции CAT: estimate_theta_eap, irt_info, остановка SE ≤ 0.30",
    }
