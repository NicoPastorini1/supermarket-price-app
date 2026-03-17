# Supermarket Price Scraper

Aplicación web para raspado y análisis de precios de supermercados. Construida con Python y Streamlit.

## Características

- **Price Scraper**: Scraping automatizado de precios de productos de supermercados
- **Navegador de Productos**: Buscar y filtrar productos por nombre, marca, categoría
- **Historial de Precios**: Seguimiento de cambios de precios a lo largo del tiempo
- **Dashboard**: Análisis estadístico de precios
- **Análisis de Inflación**: Seguimiento de variaciones de precios y métricas de inflación
- **Logs de Ejecución**: Monitoreo del rendimiento del scraper

## Instalación

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Uso

```bash
# Ejecutar la app Streamlit
streamlit run app.py
```

La aplicación se abrirá en `http://localhost:8501`

## Estructura del Proyecto

```
.
├── app.py                 # Aplicación principal de Streamlit
├── scraper/               # Módulos de scraping
│   ├── categorias.py      # Obtención de categorías
│   ├── productos.py       # Scraping de productos
│   ├── main.py            # Ejecución principal del scraper
│   ├── logs.py            # Registro de ejecuciones
│   └── analisis_inflacion.py  # Análisis de inflación
├── assets/                # Archivos estáticos
├── output/                # Datos extraídos
├── requirements.txt      # Dependencias de Python
└── .gitignore            # Reglas de Git ignore
```

## Tecnologías

- **Streamlit**: Framework de UI web
- **BeautifulSoup4**: Parsing de HTML
- **Pandas**: Manipulación de datos
- **Altair**: Visualización de datos
- **Requests**: Peticiones HTTP

## Licencia

MIT
