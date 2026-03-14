@echo off
echo Instalando dependencias...
pip install -r requirements.txt --upgrade
echo.
echo Iniciando dashboard web...
echo Abrilo en: http://localhost:5000
start http://localhost:5000
python app.py
pause
