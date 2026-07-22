# Tabla de Turno ASRS

![Status](https://img.shields.io/badge/Status-Activo-success?style=for-the-badge)
![Tech](https://img.shields.io/badge/Stack-Python%20%7C%20Flask%20%7C%20SQLite-blue?style=for-the-badge)

Solucion ligera para la gestion y reporte de turnos en el sistema **ASRS**. Permite extraer datos de produccion en tiempo real, gestionar comentarios de turno, registrar tiempos de detencion, codigos SAP y generar reportes visuales optimizados para compartir en **Microsoft Teams**.

Desarrollado por: **Manuel Rivera - ASRS**

---

## Caracteristicas Principales

- **Extraccion Automatizada**: Scraping concurrente de datos Inbound/Outbound mediante Flask + ThreadPoolExecutor.
- **Gestion de Comentarios**: Interfaz para agregar comentarios por hora, codigos SAP, tiempos de detencion y comentarios generales de turno.
- **Exportacion Visual**: Generacion de reportes en imagen de alta resolucion (html2canvas) optimizada para Teams.
- **Persistencia Local**: Almacenamiento en SQLite con historial de turnos consultados.
- **Branding Corporativo**: Tema visual industrial Goodyear (navy + amarillo), tipografia bold, barras de progreso de alto contraste.

---

## Captura Optimizada para Teams

Al hacer clic en **Copiar Reporte**, se genera una imagen de 3600px (1200 x scale 3) con:

- Header con logo Goodyear + titulo + fecha
- KPI cards: Inbound Avg (meta 11.0 tires/hr) y Outbound Avg (meta 7.5 tires/hr)
- Tabla Detalle Horario con barras de progreso de alta legibilidad
- Comentarios OT + Observaciones al pie de la imagen
- Sidebar ocultada durante la captura
- Fondo blanco solido para compatibilidad con Teams

---

## Stack Tecnologico

- **Frontend**: HTML5, CSS (variables, grid, flexbox), JavaScript vanilla.
- **Backend**: Python 3.x (Flask, Requests, ThreadPoolExecutor, Pandas, BeautifulSoup).
- **Base de Datos**: SQLite3 nativa de Python.
- **Captura Visual**: html2canvas v1.4.1.

---

## Estructura del Proyecto

```
.
├── index.html           # Interfaz principal + CSS (tema industrial)
├── app.js               # Logica del frontend (JS)
├── server.py            # Servidor Flask: API, scraping, SQLite
├── requirements.txt     # Dependencias de Python
├── iniciar_tabla_web.bat# Script de inicio rapido (Windows)
├── logo-goodyear.png    # Branding corporativo
├── db_data/             # Directorio de la base de datos (autogenerado)
│   └── data.db
└── README.md
```

---

## Instalacion y Uso

### 1. Requisitos Previos
- Python 3.x instalado.

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Iniciar el servidor
Opcion A - Ejecutar el archivo batch:
```
iniciar_tabla_web.bat
```

Opcion B - Terminal:
```bash
python server.py
```

### 4. Acceder
Abrir http://localhost:8081 en el navegador.

---

## API Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/` | Interfaz principal |
| POST | `/api/consultar` | Consulta datos de un turno (scraping) |
| POST | `/api/guardar` | Guarda comentarios y codigos SAP |
| GET | `/api/cargar` | Carga datos guardados de un turno |
| GET | `/api/historial` | Lista los ultimos turnos guardados |
| POST | `/api/proxy_kpi` | Proxy para KPIs externos |

---

## Notas

- **Sesion requerida**: Asegurate de haber iniciado sesion en el portal **MyPlant** (Intranet) para que la importacion de datos funcione correctamente.
- La base de datos se crea automaticamente en `db_data/data.db` al primer inicio.
- Cada consulta exitosa se guarda automaticamente para evitar re-scrapear datos antiguos.
- El reporte visual esta optimizado para pegar directamente en Microsoft Teams a ancho completo.

---

Desarrollado para la optimizacion de reportes industriales.
