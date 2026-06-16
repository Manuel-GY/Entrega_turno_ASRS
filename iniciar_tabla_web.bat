@echo off
echo Iniciando Servidor Unificado Python ASRS...

:: 1. Iniciar el servidor Python (Flask + DB + Scraper)
start "Servidor Python ASRS" cmd /k "python server.py"

:: 2. Esperar un momento y abrir el navegador directo al puerto 8081 de Python
timeout /t 3
start http://localhost:8081/

echo Todo en marcha. No cierres la ventana de comando de Python mientras uses la tabla.
pause
