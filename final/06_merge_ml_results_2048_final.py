from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
files = [
    "ml_result_A_binary_2048_final.csv",
    "ml_result_A_parity_2048_final.csv",
    "ml_result_B_binary_2048_final.csv",
    "ml_result_B_parity_2048_final.csv",
    "ml_result_C_binary_2048_final.csv",
    "ml_result_C_parity_2048_final.csv",
]
missing=[f for f in files if not (ROOT/f).exists()]
if missing:
    raise SystemExit("Missing result files:\n" + "\n".join(missing))
df=pd.concat([pd.read_csv(ROOT/f) for f in files], ignore_index=True)
df.to_csv(ROOT/"ml_results_2048_final_merged.csv",index=False)
print(df.to_string(index=False))
