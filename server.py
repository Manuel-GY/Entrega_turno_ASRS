import os, time, base64, tempfile, requests, urllib3, sqlite3
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from concurrent.futures import ThreadPoolExecutor

# Desactivar advertencias de SSL inseguro
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configurar Flask para que sirva archivos estáticos de la raíz
app = Flask(__name__, static_folder='.', static_url_path='')

# ================= 1. CONFIGURACIÓN =================
URL_DATOS = "http://10.107.194.62/sbs/reports/order_compliance.php"
URL_ROBOTS = "http://10.107.194.70/ASRS/press_kpi_index.php"
DB_DIR = "./db_data"
DB_FILE = os.path.join(DB_DIR, "data.db")

# Permite anular el path usando variables de entorno para producción
FIREFOX_BINARY = os.getenv("FIREFOX_BINARY", r"C:/Program Files/Mozilla Firefox/firefox.exe")

TURNOS = {
    "T1_8H": ("06:00:00", "14:00:00"), 
    "T2_8H": ("14:00:00", "22:00:00"),
    "T3_8H": ("22:00:00", "06:00:00"), 
    "T_DIA_12H": ("06:00:00", "18:00:00"),
    "T_NOCHE_12H": ("18:00:00", "06:00:00"),
}

# ================= 2. BASE DE DATOS SQLITE (NATIVA PYTHON) =================
def init_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS registros_turno (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha            TEXT    NOT NULL,
            turno            TEXT    NOT NULL,
            hora_inicio      TEXT    NOT NULL,
            hora_fin         TEXT    NOT NULL,
            inbound          REAL    DEFAULT 0,
            outbound         REAL    DEFAULT 0,
            comentario       TEXT    DEFAULT '',
            cod_sap          TEXT    DEFAULT '',
            tiempo_detencion TEXT    DEFAULT '',
            raw_json         TEXT    DEFAULT '',
            creado_en        DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(fecha, turno, hora_inicio)
        )
    """)
    # Migración/Verificación de columnas
    try:
        c.execute("ALTER TABLE registros_turno ADD COLUMN tiempo_detencion TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass # La columna ya existe
        
    c.execute("""
        CREATE TABLE IF NOT EXISTS resumen_turno (
            fecha               TEXT NOT NULL,
            turno               TEXT NOT NULL,
            comentario_general  TEXT DEFAULT '',
            PRIMARY KEY(fecha, turno)
        )
    """)
    conn.commit()
    conn.close()

# Inicializar BD al arrancar el script
init_db()

# ================= 3. FUNCIONES AUXILIARES =================
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

# ================= 4. RUTAS DEL SERVIDOR =================

@app.route('/')
def index():
    """Sirve la interfaz HTML principal"""
    return send_from_directory('.', 'index.html')

@app.route('/api/consultar', methods=['POST'])
def consultar():
    data = request.json
    fecha = data.get('fecha')
    turno = data.get('turno')
    
    if not fecha or not turno:
        return jsonify({"error": "Faltan parámetros fecha o turno"}), 400

    # Usar la fecha tal cual es enviada por el frontend
    fecha_proceso = fecha

    res_tabla, kpis = [], {"inbound": 0, "outbound": 0}
    
    try:
        # 1. Configurar rango de tiempo del turno
        ini_s, fin_s = TURNOS[turno]
        inicio_turno_dt = datetime.strptime(f"{fecha_proceso} {ini_s}", "%Y-%m-%d %H:%M:%S")
        fin_dt = datetime.strptime(f"{fecha_proceso} {fin_s}", "%Y-%m-%d %H:%M:%S")
        
        # Ajuste si el turno cruza la medianoche
        if fin_dt <= inicio_turno_dt:
            fin_dt += timedelta(days=1)
        
        # 2. Planificar
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
        
        # 3. Lanzar concurrente
        with ThreadPoolExecutor(max_workers=14) as executor:
            futuros_horas = [
                executor.submit(consultar_datos_directo, t[0], t[1], t[2], t[3])
                for t in tareas_horas
            ]
            res_tabla = [f.result() for f in futuros_horas]
            
        # Calcular promedios
        df = pd.DataFrame(res_tabla)
        if not df.empty:
            df_nonzero = df[(df["inbound"] > 0) | (df["outbound"] > 0)]
            if not df_nonzero.empty:
                kpis = {
                    "inbound": round(df_nonzero["inbound"].mean(), 1),
                    "outbound": round(df_nonzero["outbound"].mean(), 1)
                }

        # 4. Guardar automáticamente en la base de datos (Upsert)
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        for fila in res_tabla:
            c.execute("""
                INSERT INTO registros_turno 
                    (fecha, turno, hora_inicio, hora_fin, inbound, outbound, comentario, cod_sap, tiempo_detencion, raw_json)
                VALUES 
                    (?, ?, ?, ?, ?, ?, '', '', '', ?)
                ON CONFLICT(fecha, turno, hora_inicio)
                DO UPDATE SET
                    hora_fin = excluded.hora_fin,
                    inbound = excluded.inbound,
                    outbound = excluded.outbound,
                    raw_json = excluded.raw_json
            """, (fecha, turno, fila['hora_inicio'], fila['hora_fin'], fila['inbound'], fila['outbound'], str(fila)))
        
        # Obtener comentario general si existe
        c.execute("SELECT comentario_general FROM resumen_turno WHERE fecha = ? AND turno = ?", (fecha, turno))
        res_g = c.fetchone()
        com_gen = res_g[0] if res_g else ""
        conn.commit()
        conn.close()
 
        return jsonify({
            "tabla": res_tabla, 
            "kpis": kpis, 
            "comentario_general": com_gen,
            "saved": True
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/guardar', methods=['POST'])
def guardar():
    data = request.json
    fecha = data.get('fecha')
    turno = data.get('turno')
    filas = data.get('filas', [])
    com_gen = data.get('comentario_general', '')
    
    if not fecha or not turno:
        return jsonify({"error": "Parámetros incompletos"}), 400
        
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Guardar comentarios y códigos SAP de cada fila
        for fila in filas:
            c.execute("""
                UPDATE registros_turno
                SET comentario = ?, cod_sap = ?, tiempo_detencion = ?
                WHERE fecha = ? AND turno = ? AND hora_inicio = ?
            """, (
                fila.get('comentario', ''),
                fila.get('cod_sap', ''),
                fila.get('tiempo_detencion', ''),
                fecha, turno,
                fila.get('hora_inicio', '')
            ))
            
        # Guardar comentario general
        c.execute("""
            INSERT INTO resumen_turno (fecha, turno, comentario_general)
            VALUES (?, ?, ?)
            ON CONFLICT(fecha, turno) 
            DO UPDATE SET comentario_general = excluded.comentario_general
        """, (fecha, turno, com_gen))
        
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "guardados": len(filas)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/cargar', methods=['GET'])
def cargar():
    fecha = request.args.get('fecha')
    turno = request.args.get('turno')
    if not fecha or not turno:
        return jsonify({"error": "Parámetros fecha y turno requeridos"}), 400
        
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            SELECT hora_inicio, hora_fin, inbound, outbound, comentario, cod_sap, tiempo_detencion
            FROM registros_turno
            WHERE fecha = ? AND turno = ?
            ORDER BY hora_inicio ASC
        """, (fecha, turno))
        
        filas = []
        for row in c.fetchall():
            filas.append({
                "hora_inicio": row[0],
                "hora_fin": row[1],
                "inbound": row[2],
                "outbound": row[3],
                "comentario": row[4],
                "cod_sap": row[5],
                "tiempo_detencion": row[6]
            })
            
        c.execute("SELECT comentario_general FROM resumen_turno WHERE fecha = ? AND turno = ?", (fecha, turno))
        res_g = c.fetchone()
        com_gen = res_g[0] if res_g else ""
        conn.close()
        
        return jsonify({
            "tabla": filas,
            "total": len(filas),
            "comentario_general": com_gen
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/historial', methods=['GET'])
def historial():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            SELECT fecha, turno, COUNT(*) as filas, MAX(creado_en) as ultima_vez
            FROM registros_turno
            GROUP BY fecha, turno
            ORDER BY fecha DESC, turno ASC
            LIMIT 60
        """)
        registros = []
        for row in c.fetchall():
            registros.append({
                "fecha": row[0],
                "turno": row[1],
                "filas": row[2],
                "ultima_vez": row[3]
            })
        conn.close()
        return jsonify(registros)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/proxy_kpi', methods=['POST'])
def proxy_kpi():
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
    print("Servidor ASRS (Python) iniciado en el puerto 8081")
    app.run(host='0.0.0.0', port=8081)
