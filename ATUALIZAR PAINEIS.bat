@echo off
cd /d "%~dp0"
echo Sincronizando com o repositorio...
git pull --ff-only 2>nul || echo   (sem git nesta pasta - seguindo com os arquivos locais)
echo.
python atualizar.py
