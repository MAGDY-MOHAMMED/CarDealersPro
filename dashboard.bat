@echo off 
:menu  # ":" means label (like a function)
cls #clear the screen
title Car Dealers Pro - Master 
echo ========================================
echo    Car Dealers Pro - Master Control
echo ========================================
echo.
echo  1. Run Backend (FastAPI)
echo  2. Run Frontend (Future)
echo  3. Run Database Migrations (Alembic)
echo  4. Clean Python Cache (__pycache__)
echo  5. Exit
echo ==========================================
set /p choice="Enter your choice [1-5]: " # /p means prompt for user input

if "%choice%"=="1" goto backend
if "%choice%"=="2" goto frontend
if "%choice%"=="3" goto migrations
if "%choice%"=="4" goto clean
if "%choice%"=="5" goto exit

:backend
cls
echo starting Backend with uv
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
goto menu

:frontend
cls
echo starting Frontend (placeholder) # TODO: Add frontend startup command
echo Frontend is not configured yet! # TODO: Add frontend startup command
pause
goto menu

:migrations 
cls
echo running Database Migrations (Alembic)
call venv\Scripts\activate # activate virtual environment
alembic upgrade head # run migrations
echo Migrations completed successfully!
pause
goto menu


:clean
cls
echo cleaning Python Cache (__pycache__)
del /q /s __pycache__
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
echo Python Cache cleaned successfully!
pause
goto menu



