"""
Final 16-bit Arbiter-PUF behavioral dataset generator
Frozen experimental design:
    50 devices
    2,048 COMMON challenges shared by every device
    2 operating conditions:
        baseline: 25 C, 1.20 V
        stress:   85 C, 1.08 V
    fixed per-device manufacturing delays
    deterministic seed = 42

Important: the environmental model intentionally matches the executable
model used for the final revision. Temperature and voltage coefficients
are shared by upper/lower paths; they are simulation parameters, not
physical measurements.
"""
import numpy as np
import pandas as pd
from pathlib import Path

SEED = 42
N_BITS = 16
N_DEVICES = 50
N_CHALLENGES = 2048
BASELINE = (25.0, 1.20)
STRESS = (85.0, 1.08)

rng_global = np.random.RandomState(SEED)
challenge_rng = np.random.RandomState(2048)
common_challenges = np.sort(
    challenge_rng.choice(2**N_BITS, size=N_CHALLENGES, replace=False)
).astype(np.int32)

rows = []
device_params = []

for dev_id in range(1, N_DEVICES + 1):
    rng = np.random.RandomState(1000 + dev_id * 97)

    # Fixed manufacturing variation for this device.
    delay_u = rng.normal(1.0, 0.05, size=N_BITS)
    delay_l = rng.normal(1.0, 0.05, size=N_BITS)
    device_params.append(
        [dev_id] + delay_u.tolist() + delay_l.tolist()
    )

    for chal_idx in common_challenges:
        chal_bits = [(int(chal_idx) >> i) & 1 for i in range(N_BITS)]

        for temp, volt in (BASELINE, STRESS):
            # Shared environmental scaling model used by the final simulator.
            temp_coeff = 1.0 + (temp - 25.0) * 0.002
            volt_coeff = 1.0 - (volt - 1.20) * 0.15
            scale = temp_coeff * volt_coeff

            time_upper = 0.0
            time_lower = 0.0

            for i in range(N_BITS):
                jitter = rng_global.normal(0.0, 0.01)

                du = delay_u[i] * scale
                dl = delay_l[i] * scale

                if chal_bits[i] == 0:
                    time_upper += du + jitter
                    time_lower += dl - jitter
                else:
                    tmp = time_upper
                    time_upper = time_lower + du + jitter
                    time_lower = tmp + dl - jitter

            response = 1 if time_upper < time_lower else 0
            rows.append(
                [dev_id, int(chal_idx), temp, volt, int(response)]
            )

df = pd.DataFrame(
    rows,
    columns=["Device_ID", "Challenge_Dec", "Temperature", "Voltage", "Response"]
)

root = Path(__file__).resolve().parent
df.to_csv(root / "puf_sim_dataset_16bit_2048.csv", index=False)
pd.DataFrame(device_params).to_csv(
    root / "puf_device_parameters_2048.csv", index=False, header=False
)
pd.DataFrame({"Challenge_Dec": common_challenges}).to_csv(
    root / "puf_common_challenges_2048.csv", index=False
)

assert len(df) == N_DEVICES * N_CHALLENGES * 2
assert df.groupby("Device_ID")["Challenge_Dec"].nunique().eq(N_CHALLENGES).all()
assert df.groupby("Challenge_Dec")["Device_ID"].nunique().eq(N_DEVICES).all()

print(f"Rows: {len(df):,}")
print(f"Devices: {df.Device_ID.nunique()}")
print(f"Common challenges/device: {N_CHALLENGES}")
print(f"Unique challenges globally: {df.Challenge_Dec.nunique()}")
print(df.groupby(["Temperature", "Voltage"])["Response"].agg(["count", "mean"]))
