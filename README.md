# ⚙️ Tabla de Turno ASRS — Standalone Python Edition

![Status](https://img.shields.io/badge/Status-Activo-success?style=for-the-badge)
![Tech](https://img.shields.io/badge/Stack-Python%20%7C%20Flask%20%7C%20SQLite-blue?style=for-the-badge)

Una solución profesional, ligera y 100% libre de PHP para la gestión y reporte de turnos en el sistema **ASRS**. Este proyecto permite extraer datos de producción en tiempo real, gestionar comentarios de turno, registrar tiempos de detención, códigos SAP y generar reportes visuales optimizados para ser compartidos en plataformas como **Microsoft Teams**.

Desarrollado por: **Manuel Rivera - ASRS**

---

## 🚀 Características Principales

- **📊 Extracción Automatizada**: Scraping concurrente y veloz de datos Inbound/Outbound mediante Python Flask.
- **📝 Gestión de Comentarios**: Interfaz intuitiva para agregar comentarios por hora, códigos SAP, tiempos de detención y comentarios generales de turno con soporte multilínea.
- **🖼️ Exportación Premium**: Generación de reportes en imagen de alta resolución, con fondos sólidos y diseño compacto horizontal, listos para copiar y pegar.
- **💾 Persistencia Local**: Almacenamiento eficiente en SQLite local para mantener un historial de turnos consultados.

---

## 🛠️ Stack Tecnológico

- **Frontend**: HTML5, Vanilla CSS, JavaScript.
- **Backend & API**: Python 3.x (Flask, Requests, ThreadPoolExecutor, Pandas).
- **Base de Datos**: SQLite3 (Nativa de Python).
- **Captura Visual**: html2canvas (con zoom transform optimizado para Teams).

---

## 📂 Estructura del Proyecto

- `index.html`: La interfaz principal del dashboard.
- `server.py`: El servidor Flask que aloja la API, procesa datos e interactúa con la base de datos local y el scraping.
- `db_data/data.db`: Base de datos local autogenerada.
- `logo-goodyear.png`: Branding corporativo.
- `iniciar_tabla_web.bat`: Script de inicio rápido en Windows.

---

## 🔧 Instalación y Uso

### 1. Requisitos Previos
- Tener instalado **Python 3.x** con las dependencias listadas en `requirements.txt`:
  ```bash
  pip install -r requirements.txt
  ```

### 2. Iniciar el Servidor
Ejecuta el servidor Flask utilizando el archivo batch o en una terminal:
```bash
python server.py
```
*El servidor iniciará en http://localhost:8081*

### 3. Acceso
Abre tu navegador en `http://localhost:8081` para comenzar a generar reportes.

---

## 💡 Notas de Desarrollo

- El sistema está optimizado para capturas de pantalla de alta densidad, permitiendo pegar directamente el reporte a tamaño completo en Microsoft Teams.
- Los comentarios generales soportan saltos de línea y el cuadro se ajusta automáticamente para una escritura cómoda.
- La base de datos guarda automáticamente cada consulta exitosa para evitar re-scrapear datos antiguos.
- **Asegúrate de haber iniciado sesión en el portal MyPlant (Intranet) para que la importación de datos funcione correctamente.**

---

Realizado para la optimización de reportes industriales.
