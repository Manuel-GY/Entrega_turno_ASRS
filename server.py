import os
import base64
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
import urllib3
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, send_from_directory

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("asrs")

app = Flask(__name__, static_folder=".", static_url_path="")

# ================= 1. CONFIGURACION =================
URL_DATOS = "http://10.107.194.62/sbs/reports/order_compliance.php"
DB_DIR = "./db_data"
DB_FILE = os.path.join(DB_DIR, "data.db")

TURNOS = {
    "T1_8H": ("06:00:00", "14:00:00"),
    "T2_8H": ("14:00:00", "22:00:00"),
    "T3_8H": ("22:00:00", "06:00:00"),
    "T_DIA_12H": ("06:00:00", "18:00:00"),
    "T_NOCHE_12H": ("18:00:00", "06:00:00"),
}


# ================= 2. EXCEPCIONES PERSONALIZADAS =================
class ASRSConsultError(Exception):
    pass


class ASRSAuthError(ASRSConsultError):
    pass


class ASRSNetworkError(ASRSConsultError):
    pass


# ================= 3. BASE DE DATOS =================
def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    with sqlite3.connect(DB_FILE) as conn:
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
        try:
            c.execute("ALTER TABLE registros_turno ADD COLUMN tiempo_detencion TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        c.execute("""
            CREATE TABLE IF NOT EXISTS resumen_turno (
                fecha               TEXT NOT NULL,
                turno               TEXT NOT NULL,
                comentario_general  TEXT DEFAULT '',
                PRIMARY KEY(fecha, turno)
            )
        """)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


init_db()


# ================= 4. FUNCIONES AUXILIARES =================
def img_to_base64(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def consultar_datos_directo(str_ts, end_ts, hora_inicio, hora_fin):
    payload = {"str_ts": str_ts, "end_ts": end_ts, "search": "Search"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    in_v, out_v = 0.0, 0.0
    status_error = None
    try:
        r = requests.post(URL_DATOS, data=payload, headers=headers, timeout=12, verify=False)
        if r.status_code == 200:
            if "login" in r.url.lower() or "auth" in r.url.lower():
                status_error = "auth_error"
            else:
                soup = BeautifulSoup(r.text, "html.parser")
                cells = soup.find_all("td", class_="data1")
                if len(cells) > 8:
                    in_v = float(cells[6].text.strip().replace(",", "."))
                    out_v = float(cells[8].text.strip().replace(",", "."))
        else:
            status_error = f"http_status_{r.status_code}"
    except requests.Timeout:
        log.warning("Timeout HTTP (%s - %s)", str_ts, end_ts)
        status_error = "network_timeout"
    except requests.RequestException as e:
        log.error("Error de red (%s - %s): %s", str_ts, end_ts, e)
        status_error = "network_timeout"

    return {
        "hora_inicio": hora_inicio,
        "hora_fin": hora_fin,
        "inbound": in_v,
        "outbound": out_v,
        "error_status": status_error,
    }


def calcular_kpis(res_tabla):
    df = pd.DataFrame(res_tabla)
    if df.empty:
        return {"inbound": 0, "outbound": 0}
    df_nonzero = df[(df["inbound"] > 0) | (df["outbound"] > 0)]
    if df_nonzero.empty:
        return {"inbound": 0, "outbound": 0}
    return {
        "inbound": round(df_nonzero["inbound"].mean(), 1),
        "outbound": round(df_nonzero["outbound"].mean(), 1),
    }


def guardar_registros_turno(fecha_oficial, turno, res_tabla):
    with get_db() as conn:
        c = conn.cursor()
        for fila in res_tabla:
            c.execute("""
                INSERT INTO registros_turno
                    (fecha, turno, hora_inicio, hora_fin, inbound, outbound,
                     comentario, cod_sap, tiempo_detencion, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, '', '', '', ?)
                ON CONFLICT(fecha, turno, hora_inicio)
                DO UPDATE SET
                    hora_fin = excluded.hora_fin,
                    inbound = excluded.inbound,
                    outbound = excluded.outbound,
                    raw_json = excluded.raw_json
            """, (fecha_oficial, turno, fila["hora_inicio"], fila["hora_fin"],
                  fila["inbound"], fila["outbound"], str(fila)))
        c.execute(
            "SELECT comentario_general FROM resumen_turno WHERE fecha = ? AND turno = ?",
            (fecha_oficial, turno),
        )
        row = c.fetchone()
        return row[0] if row else ""


# ================= 5. RUTAS DEL SERVIDOR =================
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/consultar", methods=["POST"])
def consultar():
    data = request.json
    fecha = data.get("fecha")
    turno = data.get("turno")

    if not fecha or not turno:
        return jsonify({"error": "Faltan parametros fecha o turno"}), 400

    fecha_oficial = fecha
    fecha_proceso = fecha
    if turno in ("T3_8H", "T_NOCHE_12H"):
        fecha_proceso = (
            datetime.strptime(fecha, "%Y-%m-%d") - timedelta(days=1)
        ).strftime("%Y-%m-%d")

    try:
        ini_s, fin_s = TURNOS[turno]
        inicio_turno_dt = datetime.strptime(f"{fecha_proceso} {ini_s}", "%Y-%m-%d %H:%M:%S")
        fin_dt = datetime.strptime(f"{fecha_proceso} {fin_s}", "%Y-%m-%d %H:%M:%S")
        if fin_dt <= inicio_turno_dt:
            fin_dt += timedelta(days=1)

        tareas_horas = []
        cur_h = inicio_turno_dt
        while cur_h < fin_dt:
            nxt_h = cur_h + timedelta(hours=1)
            tareas_horas.append((
                cur_h.strftime("%Y/%m/%d %H:%M:%S"),
                nxt_h.strftime("%Y/%m/%d %H:%M:%S"),
                cur_h.strftime("%H:%M"),
                nxt_h.strftime("%H:%M"),
            ))
            cur_h = nxt_h

        with ThreadPoolExecutor(max_workers=14) as executor:
            res_tabla = list(executor.map(
                lambda t: consultar_datos_directo(*t), tareas_horas
            ))

        timeout_count = sum(1 for f in res_tabla if f.get("error_status") == "network_timeout")
        auth_count = sum(1 for f in res_tabla if f.get("error_status") == "auth_error")
        total = len(res_tabla)

        if timeout_count == total:
            raise ASRSNetworkError(
                "Se requiere iniciar sesion en el portal MyPlant (Intranet) "
                "para consultar los datos del ASRS."
            )
        if auth_count == total:
            raise ASRSAuthError(
                "Se requiere iniciar sesion en el portal MyPlant (Intranet) "
                "para acceder al servidor ASRS."
            )

        kpis = calcular_kpis(res_tabla)
        com_gen = guardar_registros_turno(fecha_oficial, turno, res_tabla)

        log.info("Consulta OK: %s %s (%d filas)", fecha_oficial, turno, len(res_tabla))
        return jsonify({
            "tabla": res_tabla,
            "kpis": kpis,
            "comentario_general": com_gen,
            "saved": True,
        })

    except ASRSConsultError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        log.exception("Error inesperado en consultar")
        return jsonify({"error": str(e)}), 500


@app.route("/api/guardar", methods=["POST"])
def guardar():
    data = request.json
    fecha = data.get("fecha")
    turno = data.get("turno")
    filas = data.get("filas", [])
    com_gen = data.get("comentario_general", "")

    if not fecha or not turno:
        return jsonify({"error": "Parametros incompletos"}), 400

    try:
        with get_db() as conn:
            c = conn.cursor()
            for fila in filas:
                c.execute("""
                    UPDATE registros_turno
                    SET comentario = ?, cod_sap = ?, tiempo_detencion = ?
                    WHERE fecha = ? AND turno = ? AND hora_inicio = ?
                """, (
                    fila.get("comentario", ""),
                    fila.get("cod_sap", ""),
                    fila.get("tiempo_detencion", ""),
                    fecha, turno,
                    fila.get("hora_inicio", ""),
                ))
            c.execute("""
                INSERT INTO resumen_turno (fecha, turno, comentario_general)
                VALUES (?, ?, ?)
                ON CONFLICT(fecha, turno)
                DO UPDATE SET comentario_general = excluded.comentario_general
            """, (fecha, turno, com_gen))

        log.info("Guardado: %s %s (%d filas)", fecha, turno, len(filas))
        return jsonify({"ok": True, "guardados": len(filas)})
    except Exception as e:
        log.exception("Error al guardar")
        return jsonify({"error": str(e)}), 500


@app.route("/api/cargar", methods=["GET"])
def cargar():
    fecha = request.args.get("fecha")
    turno = request.args.get("turno")
    if not fecha or not turno:
        return jsonify({"error": "Parametros fecha y turno requeridos"}), 400

    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT hora_inicio, hora_fin, inbound, outbound,
                       comentario, cod_sap, tiempo_detencion
                FROM registros_turno
                WHERE fecha = ? AND turno = ?
                ORDER BY hora_inicio ASC
            """, (fecha, turno))

            filas = [
                {
                    "hora_inicio": row[0], "hora_fin": row[1],
                    "inbound": row[2], "outbound": row[3],
                    "comentario": row[4], "cod_sap": row[5],
                    "tiempo_detencion": row[6],
                }
                for row in c.fetchall()
            ]

            c.execute(
                "SELECT comentario_general FROM resumen_turno WHERE fecha = ? AND turno = ?",
                (fecha, turno),
            )
            row = c.fetchone()
            com_gen = row[0] if row else ""

        return jsonify({"tabla": filas, "total": len(filas), "comentario_general": com_gen})
    except Exception as e:
        log.exception("Error al cargar")
        return jsonify({"error": str(e)}), 500


@app.route("/api/historial", methods=["GET"])
def historial():
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT fecha, turno, COUNT(*) as filas, MAX(creado_en) as ultima_vez
                FROM registros_turno
                GROUP BY fecha, turno
                ORDER BY fecha DESC, turno ASC
                LIMIT 60
            """)
            registros = [
                {"fecha": r[0], "turno": r[1], "filas": r[2], "ultima_vez": r[3]}
                for r in c.fetchall()
            ]
        return jsonify(registros)
    except Exception as e:
        log.exception("Error al obtener historial")
        return jsonify({"error": str(e)}), 500


@app.route("/api/proxy_kpi", methods=["POST"])
def proxy_kpi():
    target_type = request.args.get("type", "chart")
    if target_type == "chart":
        url = "http://10.107.194.72/ingenieria/static/phpscripts/mysql/Eng_Dashboard/zfdata_db.php"
    else:
        url = "http://10.107.194.72/ingenieria/static/phpscripts/mysql/Eng_Dashboard/zf_downtime_db.php"

    try:
        resp = requests.post(url, data=request.form, timeout=10, verify=False)
        excluded = {"content-encoding", "content-length", "transfer-encoding", "connection"}
        headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in excluded]
        return (resp.content, resp.status_code, headers)
    except Exception as e:
        log.exception("Error en proxy_kpi")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    log.info("Servidor ASRS iniciado en http://0.0.0.0:8081")
    app.run(host="0.0.0.0", port=8081)
