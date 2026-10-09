"""
Final PUF metrics for the frozen 2,048-common-challenge dataset.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
df = pd.read_csv(ROOT / "puf_sim_dataset_16bit_2048.csv")

base = (
    df[df["Temperature"] == 25.0]
    .pivot(index="Device_ID", columns="Challenge_Dec", values="Response")
    .sort_index(axis=1)
)
stress = (
    df[df["Temperature"] == 85.0]
    .pivot(index="Device_ID", columns="Challenge_Dec", values="Response")
    .sort_index(axis=1)
)

devs = base.index.to_list()
hd = []
for i in range(len(devs)):
    for j in range(i + 1, len(devs)):
        hd.append((base.loc[devs[i]].values != base.loc[devs[j]].values).mean() * 100)

uniqueness = float(np.mean(hd))
uniqueness_std = float(np.std(hd, ddof=0))
uni_ci_low, uni_ci_high = stats.t.interval(
    0.95, len(hd)-1, loc=uniqueness, scale=stats.sem(hd)
)

uniformity_per_device = base.mean(axis=1) * 100
uniformity = float(uniformity_per_device.mean())
uniformity_std = float(uniformity_per_device.std(ddof=1))

flip_rate = float(
    (base.values != stress.values).mean() * 100
)
reliability = 100.0 - flip_rate

def monobit_p(bits):
    bits = np.asarray(bits, dtype=int)
    n = len(bits)
    s = np.sum(2 * bits - 1)
    return float(stats.norm.sf(abs(s) / np.sqrt(n)) * 2)

def runs_p(bits):
    bits = np.asarray(bits, dtype=int)
    n = len(bits)
    pi = bits.mean()
    if abs(pi - 0.5) >= 2 / np.sqrt(n):
        return 0.0
    runs = 1 + np.sum(bits[1:] != bits[:-1])
    num = abs(runs - 2*n*pi*(1-pi))
    den = 2*np.sqrt(2*n)*pi*(1-pi)
    return 0.0 if den == 0 else float(2 * stats.norm.sf(num / den))

monobit_ps = []
runs_ps = []
for dev in devs:
    bits = base.loc[dev].values
    monobit_ps.append(monobit_p(bits))
    runs_ps.append(runs_p(bits))

alpha = 0.01
monobit_pass = int(np.sum(np.array(monobit_ps) > alpha))
runs_pass = int(np.sum(np.array(runs_ps) > alpha))

result = pd.DataFrame([{
    "devices": len(devs),
    "challenges_per_device": base.shape[1],
    "records": len(df),
    "uniqueness_mean_pct": uniqueness,
    "uniqueness_sd_pct": uniqueness_std,
    "uniqueness_ci95_low_pct": uni_ci_low,
    "uniqueness_ci95_high_pct": uni_ci_high,
    "uniformity_mean_pct": uniformity,
    "uniformity_sd_pct": uniformity_std,
    "reliability_pct": reliability,
    "ber_pct": flip_rate,
    "monobit_pass": monobit_pass,
    "monobit_pass_rate_pct": 100*monobit_pass/len(devs),
    "runs_pass": runs_pass,
    "runs_pass_rate_pct": 100*runs_pass/len(devs),
}])
result.to_csv(ROOT / "metrics_2048_final.csv", index=False)

print("="*70)
print("FINAL PUF METRICS")
print("="*70)
print(f"Dataset records        : {len(df):,}")
print(f"Devices                : {len(devs)}")
print(f"Common challenges      : {base.shape[1]}")
print(f"Uniqueness             : {uniqueness:.2f}%")
print(f"Uniqueness SD          : {uniqueness_std:.2f}%")
print(f"Uniqueness 95% CI      : {uni_ci_low:.2f}% - {uni_ci_high:.2f}%")
print(f"Uniformity             : {uniformity:.2f}%")
print(f"Uniformity SD          : {uniformity_std:.2f}%")
print(f"Reliability            : {reliability:.2f}%")
print(f"BER                    : {flip_rate:.2f}%")
print(f"Monobit pass           : {monobit_pass}/{len(devs)} ({100*monobit_pass/len(devs):.1f}%)")
print(f"Runs pass              : {runs_pass}/{len(devs)} ({100*runs_pass/len(devs):.1f}%)")
print("="*70)
