"""
logs.py
Sistema de logs para el scraper.
"""

import os
import pandas as pd
from datetime import datetime

import os
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
LOGS_FILE = os.path.join(OUTPUT_DIR, "logs.csv")


def guardar_log(tipo_ejecucion, cantidad_productos, duracion, estado, error="", productos_unicos=0, categorias=0, paginas_procesadas=0):
    """Guarda un registro de ejecución en el archivo de logs."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    log = {
        "fecha": datetime.now().strftime("%Y-%m-%d"),
        "hora": datetime.now().strftime("%H:%M:%S"),
        "tipo_ejecucion": tipo_ejecucion,
        "cantidad_productos": cantidad_productos,
        "productos_unicos": productos_unicos,
        "categorias_procesadas": categorias,
        "paginas_procesadas": paginas_procesadas,
        "duracion_segundos": round(duracion, 1),
        "duracion_minutos": round(duracion / 60, 2),
        "velocidad_productos_x_seg": round(cantidad_productos / duracion, 2) if duracion > 0 else 0,
        "estado": estado,
        "error": error
    }
    
    df_log = pd.DataFrame([log])
    
    if os.path.exists(LOGS_FILE):
        df_existing = pd.read_csv(LOGS_FILE)
        df_log = pd.concat([df_existing, df_log], ignore_index=True)
    
    df_log.to_csv(LOGS_FILE, index=False)
    return log


def cargar_logs():
    """Carga todos los logs desde el archivo CSV."""
    default_cols = ["fecha", "hora", "tipo_ejecucion", "cantidad_productos", "productos_unicos", 
                   "categorias_procesadas", "paginas_procesadas", "duracion_segundos", 
                   "duracion_minutos", "velocidad_productos_x_seg", "estado", "error"]
    if os.path.exists(LOGS_FILE):
        df = pd.read_csv(LOGS_FILE)
        for col in default_cols:
            if col not in df.columns:
                df[col] = 0 if "cantidad" in col or "categorias" in col or "paginas" in col or "duracion" in col or "velocidad" in col else ""
        return df
    return pd.DataFrame(columns=default_cols)
