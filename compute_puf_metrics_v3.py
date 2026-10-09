"""PUF quality metrics for the v3 common-challenge dataset."""
from __future__ import annotations
import itertools
import math
import pandas as pd
import numpy as np
from scipy import stats

DATA = "puf_sim_dataset_16bit_v3.csv"
df = pd.read_csv(DATA)
base = df[df.Condition == "baseline"].copy()
stress = df[df.Condition == "stress"].copy()

# Exact inter-device comparison because every device uses the same common challenge pool.
pivot = base.pivot(index="Device_ID", columns="Challenge_Dec", values="Response")
pairs = []
for a, b in itertools.combinations(pivot.index, 2):
    pairs.append(float((pivot.loc[a].to_numpy() != pivot.loc[b].to_numpy()).mean() * 100))
uniqueness = np.mean(pairs)
uniq_std = np.std(pairs, ddof=1)
uniq_ci = stats.t.interval(0.95, len(pairs)-1, loc=uniqueness, scale=stats.sem(pairs))

uniformity = base.groupby("Device_ID").Response.mean().to_numpy() * 100
uniformity_mean = uniformity.mean()
uniformity_std = uniformity.std(ddof=1)

b = base.set_index(["Device_ID", "Challenge_Dec"]).Response
s = stress.set_index(["Device_ID", "Challenge_Dec"]).Response
common = b.index.intersection(s.index)
flip_rate = float((b.loc[common].to_numpy() != s.loc[common].to_numpy()).mean() * 100)
reliability = 100 - flip_rate

# Exploratory per-device frequency/runs tests. These are not claimed as a cryptographic proof.
def monobit_p(bits):
    n = len(bits)
    s_abs = abs(np.sum(np.where(bits == 1, 1, -1)))
    return 2 * (1 - stats.norm.cdf(s_abs / math.sqrt(n)))

def runs_p(bits):
    n = len(bits)
    pi = bits.mean()
    if abs(pi - 0.5) >= 2 / math.sqrt(n):
        return 0.0
    runs = 1 + np.count_nonzero(bits[1:] != bits[:-1])
    numerator = abs(runs - 2*n*pi*(1-pi))
    denominator = 2*math.sqrt(2*n)*pi*(1-pi)
    return 0.0 if denominator == 0 else 2*(1-stats.norm.cdf(numerator/denominator))

mono = []
runs = []
for dev, g in base.groupby("Device_ID"):
    bits = g.sort_values("Challenge_Dec").Response.to_numpy(dtype=int)
    mono.append(monobit_p(bits))
    runs.append(runs_p(bits))

mono_pass = 100 * np.mean(np.array(mono) > 0.01)
runs_pass = 100 * np.mean(np.array(runs) > 0.01)

# Save a machine-readable metrics file.
metrics = {
    "N_devices": len(pivot),
    "N_common_challenges": pivot.shape[1],
    "Uniqueness_mean_pct": uniqueness,
    "Uniqueness_sd_pct": uniq_std,
    "Uniqueness_95CI_low_pct": uniq_ci[0],
    "Uniqueness_95CI_high_pct": uniq_ci[1],
    "Uniformity_mean_pct": uniformity_mean,
    "Uniformity_sd_pct": uniformity_std,
    "Reliability_pct": reliability,
    "BER_pct": flip_rate,
    "Monobit_pass_rate_pct": mono_pass,
    "Runs_pass_rate_pct": runs_pass,
}
pd.DataFrame([metrics]).to_csv("puf_metrics_v3.csv", index=False)

print("="*78)
for k, v in metrics.items():
    print(f"{k:32s}: {v:.4f}" if isinstance(v, float) else f"{k:32s}: {v}")
print("="*78)
