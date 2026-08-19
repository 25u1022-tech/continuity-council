@echo off
setlocal
set "ROOT=%~dp0"

if not exist "%ROOT%backend\.venv\Scripts\python.exe" (
  echo Backend virtual environment not found.
  echo Run: cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)

if not exist "%ROOT%frontend\node_modules" (
  echo Frontend dependencies not found.
  echo Run: cd frontend ^&^& yarn install
  exit /b 1
)

start "Continuity Council Backend" cmd /k "cd /d "%ROOT%backend" ^&^& .venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload"
start "Continuity Council Frontend" cmd /k "cd /d "%ROOT%frontend" ^&^& corepack yarn start"

echo Backend: http://localhost:8000
 echo Frontend: http://localhost:3000
endlocal
