@echo off
echo Iniciando Servidores para Tabla Web ASRS...

:: 1. Iniciar el servidor de Scraping (Python) en una ventana nueva
start "Scraper Python" cmd /k "python server.py"

:: 2. Iniciar el servidor Web (PHP) usando la ruta de XAMPP
start "Web PHP" cmd /k "C:\xampp\php\php.exe -S localhost:8083"

:: 3. Esperar un momento y abrir el navegador
timeout /t 3
start http://localhost:8083/index.html

echo Todo en marcha. No cierres las ventanas de comandos mientras uses la tabla.
pause
