"""One-command runner for the complete 2,048-challenge experiment."""
import subprocess, sys
from pathlib import Path

root = Path(__file__).resolve().parent
scripts = [
    "01_generate_dataset_2048_final.py",
    "02_compute_metrics_2048_final.py",
    "03_ml_experiment_2048_final.py",
    "04_authentication_2048_final.py",
]
for s in scripts:
    print("\n" + "="*80)
    print("RUNNING", s)
    print("="*80)
    subprocess.run([sys.executable, str(root/s)], check=True)
print("\nALL EXPERIMENTS COMPLETED.")
