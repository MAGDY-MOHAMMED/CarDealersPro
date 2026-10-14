@echo off
REM =========================================================
REM Find and initialize Visual Studio C++ Compiler Environment
REM =========================================================

set "VS_PATH=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VS_PATH%" (
    set "VS_PATH=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
)

if exist "%VS_PATH%" (
    echo [INFO] Loading Visual C++ environment...
    call "%VS_PATH%"
) else (
    echo [ERROR] Could not find vcvars64.bat. Make sure Desktop development with C++ is installed.
    exit /b 1
)

REM =========================================================
REM Run python script inside project virtual environment
REM =========================================================

echo [INFO] Running PriceRegressor self-test...
python app/services/ml/models/price_regressor.py

pause