# PUF 2048 Final Experiment — Step-by-Step

## 0. Environment

Recommended:
- Python 3.10+
- numpy
- pandas
- scipy
- scikit-learn
- torch
- cryptography

Install if needed:

```bash
python -m pip install numpy pandas scipy scikit-learn torch cryptography
```

## 1. Put all files in one directory

Keep these files together:

- 01_generate_dataset_2048_final.py
- 02_compute_metrics_2048_final.py
- 03_ml_experiment_2048_final.py
- 04_authentication_2048_final.py
- 05_run_all_2048_final.py

## 2. Generate the final dataset

```bash
python 01_generate_dataset_2048_final.py
```

Expected:
- 50 devices
- 2,048 common challenges/device
- 2 conditions
- 204,800 rows

Check that the printed row count is exactly 204800.

## 3. Compute PUF metrics

```bash
python 02_compute_metrics_2048_final.py
```

The script writes:
- metrics_2048_final.csv

Record these values for Table I:
- uniqueness
- uniqueness SD
- 95% CI
- uniformity
- uniformity SD
- reliability
- BER
- monobit pass rate
- runs pass rate

## 4. Run ML experiments

```bash
python 03_ml_experiment_2048_final.py
```

The script writes:
- ml_results_2048_final.csv

Use the resulting six rows for Table II.

Important:
- Transformer: d_model=32, 4 heads, 2 encoder layers, FF=64
- MLP: 2 hidden layers of 64
- RF: 150 trees
- SVM: max 15,000 training rows
- seed=42
- neural batch size=4096 for the 204,800-row dataset

## 5. Run authentication

```bash
python 04_authentication_2048_final.py
```

The script writes:
- authentication_results_2048_final.csv

Record:
- reconstruction successes
- key matches
- public-key matches
- signature verification successes
- mean 128-bit reconstruction Hamming error

This result must replace any old 50/50 authentication result if the old result was based on the previous dataset.

## 6. One-command run

After confirming the individual scripts work:

```bash
python 05_run_all_2048_final.py
```

## 7. What is NOT established

These scripts do not establish:
- physical FPGA PUF uniqueness
- silicon-measured environmental coefficients
- formal fuzzy-extractor/helper-data leakage bounds
- side-channel resistance
- fault-injection resistance
- field IEC 61850/IEC 62351 deployment validation

Those remain limitations/future work.

## 8. Final frozen dataset definition

50 devices × 2,048 common challenges × 2 conditions = 204,800 records.

Baseline:
25 °C, 1.20 V

Stress:
85 °C, 1.08 V

Environmental model:
C_T(T) = 1 + 0.002(T - 25)
C_V(V) = 1 - 0.15(V - 1.20)
d' = d × C_T × C_V

The coefficients are simulation parameters, not physical measurements.


## 9. Recommended ML execution mode (one job at a time)

If the all-in-one ML run is slow or runs out of memory, run each split/encoding
as a separate process. This is recommended for the 204,800-row dataset because
it releases model memory between jobs.

Set single-threaded BLAS/OpenMP to reduce CPU oversubscription:

Windows PowerShell:
```powershell
$env:OMP_NUM_THREADS="1"
$env:MKL_NUM_THREADS="1"
$env:OPENBLAS_NUM_THREADS="1"
```

Then run these six commands:

```bash
python 03_ml_single_2048_final.py --split A --encoding binary
python 03_ml_single_2048_final.py --split A --encoding parity
python 03_ml_single_2048_final.py --split B --encoding binary
python 03_ml_single_2048_final.py --split B --encoding parity
python 03_ml_single_2048_final.py --split C --encoding binary
python 03_ml_single_2048_final.py --split C --encoding parity
```

Each command produces one CSV:
- ml_result_A_binary_2048_final.csv
- ml_result_A_parity_2048_final.csv
- ml_result_B_binary_2048_final.csv
- ml_result_B_parity_2048_final.csv
- ml_result_C_binary_2048_final.csv
- ml_result_C_parity_2048_final.csv

The six files can then be concatenated into Table II.

## 10. Hyperparameters

The paper-aligned configuration is:
- Transformer: d_model=32, 4 heads, 2 encoder layers, FF=64
- MLP: two hidden layers, 64 units each
- Random Forest: 50 trees
- Linear SVM: at most 15,000 training rows
- Adam learning rate: 0.008
- neural epochs: 6
- neural batch size: 4,096
- random seed: 42

Do not replace these with the earlier time-constrained preliminary run
(1 epoch / 10-tree RF / 3,000-row SVM). Those preliminary values must NOT
be used as final paper numbers.
