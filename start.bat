@echo off
echo Instalando dependencias...
pip install -r requirements.txt --upgrade
echo.
echo Iniciando bot de gym...
python bot.py
pause
