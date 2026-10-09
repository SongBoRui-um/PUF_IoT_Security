@echo off
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1

echo === A Binary ===
python 03_ml_single_2048_final.py --split A --encoding binary
if errorlevel 1 goto :error

echo === A Parity ===
python 03_ml_single_2048_final.py --split A --encoding parity
if errorlevel 1 goto :error

echo === B Binary ===
python 03_ml_single_2048_final.py --split B --encoding binary
if errorlevel 1 goto :error

echo === B Parity ===
python 03_ml_single_2048_final.py --split B --encoding parity
if errorlevel 1 goto :error

echo === C Binary ===
python 03_ml_single_2048_final.py --split C --encoding binary
if errorlevel 1 goto :error

echo === C Parity ===
python 03_ml_single_2048_final.py --split C --encoding parity
if errorlevel 1 goto :error

echo.
echo ALL SIX ML JOBS COMPLETED.
pause
exit /b 0

:error
echo.
echo ML JOB FAILED. Check the message above.
pause
exit /b 1
