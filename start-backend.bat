@echo off
set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PYTHON%" (
  echo Python 3.12 nao encontrado em %LOCALAPPDATA%\Programs\Python\Python312\python.exe
  echo Ajuste o caminho ou instale o Python 3.12 nesse local.
  exit /b 1
)
set "REPO=%~dp0"
pushd "%REPO%"
if errorlevel 1 exit /b 1
start "API" cmd /k "%PYTHON% -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000"
start "Worker" cmd /k "%PYTHON% -m backend.worker.main"
popd
echo Backend e worker iniciados. Pressione qualquer tecla para fechar esta janela.
pause >nul
