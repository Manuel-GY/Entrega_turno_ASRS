import os, time, base64, tempfile, requests, urllib3
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from concurrent.futures import ThreadPoolExecutor

# Desactivar advertencias de SSL inseguro
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ================= 1. CONFIGURACIÓN =================
URL_DATOS = "http://10.107.194.62/sbs/reports/order_compliance.php"
URL_ROBOTS = "http://10.107.194.70/ASRS/press_kpi_index.php"

# Permite anular el path usando variables de entorno para producción
FIREFOX_BINARY = os.getenv("FIREFOX_BINARY", r"C:/Program Files/Mozilla Firefox/firefox.exe")

TURNOS = {
    "T1_8H": ("06:00:00", "14:00:00"), 
    "T2_8H": ("14:00:00", "22:00:00"),
    "T3_8H": ("22:00:00", "06:00:00"), 
    "T_DIA_12H": ("06:00:00", "18:00:00"),
    "T_NOCHE_12H": ("18:00:00", "06:00:00"),
}

# ================= 2. FUNCIONES AUXILIARES =================
def get_driver():
    options = Options()
    options.add_argument("--headless")
    if os.path.exists(FIREFOX_BINARY):
        options.binary_location = FIREFOX_BINARY
    return webdriver.Firefox(options=options)

def img_to_base64(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def consultar_datos_directo(str_ts, end_ts, hora_inicio, hora_fin):
    """
    Realiza una petición HTTP POST directa para evitar Selenium.
    """
    payload = {
        'str_ts': str_ts,
        'end_ts': end_ts,
        'search': 'Search'
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    in_v, out_v = 0.0, 0.0
    try:
        r = requests.post(URL_DATOS, data=payload, headers=headers, timeout=12, verify=False)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            cells = soup.find_all('td', class_='data1')
            if len(cells) > 8:
                in_v = float(cells[6].text.strip().replace(",", "."))
                out_v = float(cells[8].text.strip().replace(",", "."))
    except Exception as e:
        print(f"Error en consulta HTTP directa ({str_ts} - {end_ts}): {e}")
    
    return {
        "hora_inicio": hora_inicio,
        "hora_fin": hora_fin,
        "inbound": in_v,
        "outbound": out_v
    }

def capturar_grafico_selenium():
    """
    Ejecuta en segundo plano la captura del gráfico Selenium.
    """
    img_grafico_b64 = None
    driver = None
    try:
        driver = get_driver()
        driver.set_window_size(1920, 1080)
        driver.get(URL_ROBOTS)
        time.sleep(1.8) # Reducido levemente para acelerar
        
        tmp_img = os.path.join(tempfile.gettempdir(), "asrs_kpi.png")
        # Quitar el zoom del 120% que hacía que se vea demasiado grande
        driver.execute_script("document.body.style.zoom='100%'")
        container = driver.find_element(By.CSS_SELECTOR, "div.col-5")
        container.screenshot(tmp_img)
        img_grafico_b64 = img_to_base64(tmp_img)
    except Exception as ex_selenium:
        print(f"Aviso: Fallo en captura de gráfico: {ex_selenium}")
    finally:
        if driver is not None:
            driver.quit()
    return img_grafico_b64

# ================= 3. RUTAS API (EJECUCIÓN EN PARALELO MULTI-HILO) =================
@app.route('/api/consultar', methods=['POST'])
def consultar():
    data = request.json
    fecha_str = data.get('fecha')
    turno_key = data.get('turno')
    
    if not fecha_str or not turno_key:
        return jsonify({"error": "Faltan parámetros fecha o turno"}), 400

    res_tabla, kpis = [], {"inbound": 0, "outbound": 0}
    
    try:
        # 1. Configurar rango de tiempo del turno
        ini_s, fin_s = TURNOS[turno_key]
        inicio_turno_dt = datetime.strptime(f"{fecha_str} {ini_s}", "%Y-%m-%d %H:%M:%S")
        fin_dt = datetime.strptime(f"{fecha_str} {fin_s}", "%Y-%m-%d %H:%M:%S")
        
        # Ajuste si el turno cruza la medianoche
        if fin_dt <= inicio_turno_dt:
            fin_dt += timedelta(days=1)
        
        # 2. Planificar las tareas a paralelizar
        tareas_horas = []
        cur_h = inicio_turno_dt
        while cur_h < fin_dt:
            nxt_h = cur_h + timedelta(hours=1)
            
            str_ts = cur_h.strftime('%Y/%m/%d %H:%M:%S')
            end_ts = nxt_h.strftime('%Y/%m/%d %H:%M:%S')
            h_ini = cur_h.strftime("%H:%M")
            h_fin = nxt_h.strftime("%H:%M")
            
            tareas_horas.append((str_ts, end_ts, h_ini, h_fin))
            cur_h = nxt_h
        
        # 3. Lanzar todo concurrente (Scraping de Horas + Captura del Gráfico en paralelo)
        with ThreadPoolExecutor(max_workers=14) as executor:
            # Lanzamos la tarea lenta de captura de gráfico
            futuro_grafico = executor.submit(capturar_grafico_selenium)
            
            # Lanzamos todas las peticiones horarias al mismo tiempo
            futuros_horas = [
                executor.submit(consultar_datos_directo, t[0], t[1], t[2], t[3])
                for t in tareas_horas
            ]
            
            # Recopilar resultados de la tabla (manteniendo el orden cronológico)
            res_tabla = [f.result() for f in futuros_horas]
            
            # Recopilar gráfico
            img_grafico_b64 = futuro_grafico.result()
            
        # Calcular promedios
        df = pd.DataFrame(res_tabla)
        if not df.empty:
            df_nonzero = df[(df["inbound"] > 0) | (df["outbound"] > 0)]
            if not df_nonzero.empty:
                kpis = {
                    "inbound": round(df_nonzero["inbound"].mean(), 1),
                    "outbound": round(df_nonzero["outbound"].mean(), 1)
                }
 
        return jsonify({
            "tabla": res_tabla, 
            "kpis": kpis, 
            "img_grafico": img_grafico_b64
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/proxy_kpi', methods=['POST'])
def proxy_kpi():
    """Proxy para evitar errores de CORS con otros servidores internos"""
    target_type = request.args.get('type', 'chart')
    if target_type == 'chart':
        url = "http://10.107.194.72/ingenieria/static/phpscripts/mysql/Eng_Dashboard/zfdata_db.php"
    else:
        url = "http://10.107.194.72/ingenieria/static/phpscripts/mysql/Eng_Dashboard/zf_downtime_db.php"
    
    try:
        resp = requests.post(url, data=request.form, timeout=10, verify=False)
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.headers.items()
                   if name.lower() not in excluded_headers]
        return (resp.content, resp.status_code, headers)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Servidor de Scraping ASRS iniciado en el puerto 8081")
    app.run(host='0.0.0.0', port=8081)
