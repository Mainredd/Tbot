@echo off
echo Instalando dependencias...
pip install -r requirements.txt --upgrade
echo.
echo Iniciando bot de comidas...
python food_bot.py
pause
