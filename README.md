# ⚙️ Tabla de Turno ASRS — Standalone Edition

![Status](https://img.shields.io/badge/Status-Activo-success?style=for-the-badge)
![Tech](https://img.shields.io/badge/Stack-PHP%20%7C%20Python%20%7C%20SQLite-blue?style=for-the-badge)

Una solución profesional y ligera para la gestión y reporte de turnos en el sistema **ASRS**. Este proyecto permite extraer datos de producción en tiempo real, gestionar comentarios de turno y generar reportes visuales optimizados para ser compartidos en plataformas como **Microsoft Teams**.

---

## 🚀 Características Principales

- **📊 Extracción Automatizada**: Scraping inteligente de datos Inbound/Outbound mediante Python y Selenium.
- **📝 Gestión de Comentarios**: Interfaz intuitiva para agregar comentarios por hora y comentarios generales de turno con soporte multilínea.
- **🖼️ Exportación Premium**: Generación de reportes en imagen de alta resolución, con fondos sólidos y diseño compacto, listos para copiar y pegar.
- **💾 Persistencia Local**: Almacenamiento eficiente en SQLite para mantener un historial de turnos consultados.
- **🌙 Modo Oscuro/Claro**: Interfaz moderna con soporte para temas visuales.

---

## 🛠️ Stack Tecnológico

- **Frontend**: PHP 8.x, HTML5, Vanilla CSS, JavaScript.
- **Backend Scraping**: Python 3.x (Flask, Selenium, Pandas).
- **Base de Datos**: SQLite3.
- **Captura Visual**: html2canvas (con optimizaciones para Teams).

---

## 📂 Estructura del Proyecto

- `index.php`: La interfaz principal del dashboard.
- `api.php`: El motor que comunica la web con la base de datos y el scraper.
- `server.py`: El servidor de scraping que extrae los datos de producción.
- `data.db`: Base de datos local (generada automáticamente).
- `logo-goodyear.png`: Branding corporativo.

---

## 🔧 Instalación y Uso

### 1. Requisitos Previos
- Tener instalado **PHP 8.x** (por ejemplo, vía XAMPP).
- Tener instalado **Python 3.x** con las dependencias: `flask`, `selenium`, `pandas`, `requests`.

### 2. Iniciar el Servidor de Scraping
Ejecuta el scraper en una terminal:
```bash
python server.py
```
*El servidor iniciará en http://127.0.0.1:8081*

### 3. Iniciar el Servidor Web
Ejecuta el servidor PHP (o usa XAMPP/Apache):
```bash
php -S localhost:8083
```

### 4. Acceso
Abre tu navegador en `http://localhost:8083` para comenzar a generar reportes.

---

## 💡 Notas de Desarrollo

- El sistema está optimizado para capturas de pantalla de alta densidad.
- Los comentarios generales soportan saltos de línea y el cuadro se ajusta automáticamente para una escritura cómoda.
- La base de datos guarda automáticamente cada consulta exitosa para evitar re-scrapear datos antiguos.

---

Realizado para la optimización de reportes industriales.
