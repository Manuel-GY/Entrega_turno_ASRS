<?php
/**
 * api.php - Backend API para tabla_web
 * 
 * Endpoints:
 *   POST /api.php?action=consultar  -> Llama a la API Python y guarda en SQLite
 *   POST /api.php?action=guardar    -> Guarda comentarios / cód SAP editados por el usuario
 *   GET  /api.php?action=historial  -> Lista de fechas/turnos guardados
 *   GET  /api.php?action=cargar&fecha=YYYY-MM-DD&turno=T1_8H -> Carga registros guardados
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }

// ---- CONFIGURACIÓN ----
// Permite leer la URL del scraper desde el entorno (ej. en Docker) o usar localhost de forma predeterminada
define('PYTHON_API_URL', getenv('PYTHON_API_URL') ?: 'http://127.0.0.1:8081/api/consultar'); 
define('DB_DIR', __DIR__ . '/db_data');
define('DB_FILE', DB_DIR . '/data.db');

// ---- BASE DE DATOS ----
function getDB(): SQLite3 {
    if (!is_dir(DB_DIR)) {
        mkdir(DB_DIR, 0755, true);
    }
    $db = new SQLite3(DB_FILE);
    $db->exec("PRAGMA journal_mode=WAL;");
    $db->exec("
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
            creado_en        DATETIME DEFAULT (datetime('now','localtime')),
            UNIQUE(fecha, turno, hora_inicio)
        )
    ");
    // Migración automática en caso de base de datos existente
    @$db->exec("ALTER TABLE registros_turno ADD COLUMN tiempo_detencion TEXT DEFAULT ''");
    $db->exec("
        CREATE TABLE IF NOT EXISTS resumen_turno (
            fecha               TEXT NOT NULL,
            turno               TEXT NOT NULL,
            comentario_general  TEXT DEFAULT '',
            PRIMARY KEY(fecha, turno)
        )
    ");
    return $db;
}

// ---- ENRUTADOR ----
$action = $_GET['action'] ?? (json_decode(file_get_contents('php://input'), true)['action'] ?? '');
$body   = json_decode(file_get_contents('php://input'), true) ?? [];

switch ($action) {
    case 'consultar': handleConsultar($body); break;
    case 'guardar':   handleGuardar($body);   break;
    case 'cargar':    handleCargar();          break;
    case 'historial': handleHistorial();       break;
    default: jsonError('Acción no reconocida: ' . $action);
}

// ---- HANDLERS ----

/**
 * Consulta la API Python, muestra los datos y los guarda automáticamente en SQLite.
 */
function handleConsultar(array $body): void {
    $fecha = $body['fecha'] ?? '';
    $turno = $body['turno'] ?? '';

    if (!$fecha || !$turno) { jsonError('Faltan parámetros: fecha y turno son requeridos.'); }

    // AJUSTE TURNO NOCHE: Si es noche, la API Python espera la fecha de inicio (ayer),
    // pero el usuario prefiere poner la fecha del día que termina (hoy).
    $fecha_proceso = $fecha;
    if ($turno === 'T3_8H' || $turno === 'T_NOCHE_12H') {
        $d = new DateTime($fecha);
        $d->modify('-1 day');
        $fecha_proceso = $d->format('Y-m-d');
    }

    // 1. Llamar a la API Python
    $payload  = json_encode(['fecha' => $fecha_proceso, 'turno' => $turno]);
    $ch = curl_init(PYTHON_API_URL);
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $payload,
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json', 'Accept: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 120,
    ]);
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $curlErr  = curl_error($ch);
    curl_close($ch);

    if ($curlErr || $httpCode >= 400) {
        jsonError("No se pudo conectar con el servidor ASRS: " . ($curlErr ?: "HTTP $httpCode"));
    }

    $data = json_decode($response, true);
    if (!$data || isset($data['error'])) {
        jsonError($data['error'] ?? 'Respuesta inválida del servidor ASRS.');
    }

    // 2. Guardar cada fila en SQLite (upsert por fecha+turno+hora_inicio)
    $db = getDB();
    if (isset($data['tabla']) && is_array($data['tabla'])) {
        $stmt = $db->prepare("
            INSERT INTO registros_turno 
                (fecha, turno, hora_inicio, hora_fin, inbound, outbound, comentario, cod_sap, raw_json)
            VALUES 
                (:fecha, :turno, :hi, :hf, :ib, :ob, '', '', :raw)
            ON CONFLICT(fecha, turno, hora_inicio)
            DO UPDATE SET
                hora_fin  = excluded.hora_fin,
                inbound   = excluded.inbound,
                outbound  = excluded.outbound,
                raw_json  = excluded.raw_json
        ");
        foreach ($data['tabla'] as $fila) {
            $stmt->bindValue(':fecha',  $fecha,                       SQLITE3_TEXT);
            $stmt->bindValue(':turno',  $turno,                       SQLITE3_TEXT);
            $stmt->bindValue(':hi',     $fila['hora_inicio'] ?? '',   SQLITE3_TEXT);
            $stmt->bindValue(':hf',     $fila['hora_fin']    ?? '',   SQLITE3_TEXT);
            $stmt->bindValue(':ib',     $fila['inbound']     ?? 0,    SQLITE3_FLOAT);
            $stmt->bindValue(':ob',     $fila['outbound']    ?? 0,    SQLITE3_FLOAT);
            $stmt->bindValue(':raw',    json_encode($fila),           SQLITE3_TEXT);
            $stmt->execute();
            $stmt->reset();
        }
    }
    // 3. Obtener comentario general si existe
    $stmtG = $db->prepare("SELECT comentario_general FROM resumen_turno WHERE fecha = :fecha AND turno = :turno");
    $stmtG->bindValue(':fecha', $fecha, SQLITE3_TEXT);
    $stmtG->bindValue(':turno', $turno, SQLITE3_TEXT);
    $resG = $stmtG->execute()->fetchArray(SQLITE3_ASSOC);
    $com_gen = $resG ? $resG['comentario_general'] : '';
    
    $db->close();

    // 4. Devolver la respuesta original de la API Python enriquecida
    echo json_encode(array_merge($data, ['saved' => true, 'comentario_general' => $com_gen]));
}

/**
 * Actualiza comentarios y códigos SAP de los registros ya guardados.
 */
function handleGuardar(array $body): void {
    $fecha   = $body['fecha']  ?? '';
    $turno   = $body['turno']  ?? '';
    $filas   = $body['filas']  ?? [];
    $com_gen = $body['comentario_general'] ?? '';

    if (!$fecha || !$turno) { jsonError('Parámetros incompletos para guardar.'); }

    $db = getDB();
    $stmt = $db->prepare("
        UPDATE registros_turno
        SET comentario = :com, cod_sap = :sap, tiempo_detencion = :det
        WHERE fecha = :fecha AND turno = :turno AND hora_inicio = :hi
    ");
 
    $guardados = 0;
    foreach ($filas as $fila) {
        $stmt->bindValue(':fecha',  $fecha,                    SQLITE3_TEXT);
        $stmt->bindValue(':turno',  $turno,                    SQLITE3_TEXT);
        $stmt->bindValue(':hi',     $fila['hora_inicio'] ?? '', SQLITE3_TEXT);
        $stmt->bindValue(':com',    $fila['comentario']  ?? '', SQLITE3_TEXT);
        $stmt->bindValue(':sap',    $fila['cod_sap']     ?? '', SQLITE3_TEXT);
        $stmt->bindValue(':det',    $fila['tiempo_detencion'] ?? '', SQLITE3_TEXT);
        $stmt->execute();
        $stmt->reset();
        $guardados++;
    }
    // Guardar comentario general
    $stmtG = $db->prepare("
        INSERT INTO resumen_turno (fecha, turno, comentario_general)
        VALUES (:fecha, :turno, :com)
        ON CONFLICT(fecha, turno) DO UPDATE SET comentario_general = excluded.comentario_general
    ");
    $stmtG->bindValue(':fecha', $fecha, SQLITE3_TEXT);
    $stmtG->bindValue(':turno', $turno, SQLITE3_TEXT);
    $stmtG->bindValue(':com',   $com_gen, SQLITE3_TEXT);
    $stmtG->execute();
 
    $db->close();
 
    echo json_encode(['ok' => true, 'guardados' => $guardados]);
}
 
/**
 * Carga registros ya guardados para una fecha y turno específicos.
 */
function handleCargar(): void {
    $fecha = $_GET['fecha'] ?? '';
    $turno = $_GET['turno'] ?? '';
    if (!$fecha || !$turno) { jsonError('Parámetros fecha y turno requeridos.'); }
 
    $db   = getDB();
    $stmt = $db->prepare("
        SELECT hora_inicio, hora_fin, inbound, outbound, comentario, cod_sap, tiempo_detencion
        FROM registros_turno
        WHERE fecha = :fecha AND turno = :turno
        ORDER BY hora_inicio ASC
    ");
    $stmt->bindValue(':fecha', $fecha, SQLITE3_TEXT);
    $stmt->bindValue(':turno', $turno, SQLITE3_TEXT);
    $result = $stmt->execute();

    $filas = [];
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $filas[] = $row;
    }
    // Cargar comentario general
    $stmtG = $db->prepare("SELECT comentario_general FROM resumen_turno WHERE fecha = :fecha AND turno = :turno");
    $stmtG->bindValue(':fecha', $fecha, SQLITE3_TEXT);
    $stmtG->bindValue(':turno', $turno, SQLITE3_TEXT);
    $resG = $stmtG->execute()->fetchArray(SQLITE3_ASSOC);
    $com_gen = $resG ? $resG['comentario_general'] : '';

    $db->close();

    echo json_encode([
        'tabla' => $filas, 
        'total' => count($filas),
        'comentario_general' => $com_gen
    ]);
}

/**
 * Devuelve el listado de fechas y turnos que tienen datos guardados.
 */
function handleHistorial(): void {
    $db   = getDB();
    $result = $db->query("
        SELECT fecha, turno, COUNT(*) as filas, MAX(creado_en) as ultima_vez
        FROM registros_turno
        GROUP BY fecha, turno
        ORDER BY fecha DESC, turno ASC
        LIMIT 60
    ");
    $registros = [];
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $registros[] = $row;
    }
    $db->close();
    echo json_encode($registros);
}

// ---- HELPERS ----
function jsonError(string $msg, int $code = 400): void {
    http_response_code($code);
    echo json_encode(['error' => $msg]);
    exit;
}
