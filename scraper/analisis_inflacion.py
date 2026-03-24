"""
analisis_inflacion.py
Módulo de análisis de inflación para datos históricos de precios de supermercado.
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

try:
    from scraper.supabase_client import obtener_productos_desde_supabase
    SUPABASE_DISPONIBLE = True
except:
    SUPABASE_DISPONIBLE = False


def cargar_todos_los_datos() -> Tuple[pd.DataFrame, List[str]]:
    all_records = []
    fechas = []
    
    if SUPABASE_DISPONIBLE and os.getenv("SUPABASE_URL"):
        try:
            productos = obtener_productos_desde_supabase()
            if productos:
                for p in productos:
                    p["productId"] = p.get("product_id")
                    fecha = p.get("fecha_extraccion", "")[:10] if p.get("fecha_extraccion") else ""
                    p["fecha_extraccion"] = fecha
                    all_records.append(p)
                    if fecha and fecha not in fechas:
                        fechas.append(fecha)
                
                fechas.sort()
                if all_records:
                    return pd.DataFrame(all_records), fechas
        except Exception:
            pass
    
    search_dirs = [OUTPUT_DIR, "."]
    
    json_files = []
    for d in search_dirs:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.startswith("productos_") and f.endswith(".json"):
                    filepath = os.path.join(d, f)
                    fecha = f.replace("productos_", "").replace(".json", "")
                    json_files.append((filepath, fecha))
    
    json_files.sort(key=lambda x: x[1])
    
    for filepath, fecha in json_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if isinstance(data, list):
                data = {"productos": data, "tienda": "dia"}
            
            productos = data.get("productos", [])
            
            for p in productos:
                p["fecha_extraccion"] = fecha
                all_records.append(p)
            
            if productos:
                fechas.append(fecha)
        except Exception:
            continue
    
    if not all_records:
        return pd.DataFrame(), []
    
    df = pd.DataFrame(all_records)
    return df, fechas


def calcular_indice_precios(df: pd.DataFrame, fechas: List[str]) -> pd.DataFrame:
    if not fechas or len(fechas) < 1:
        return pd.DataFrame()
    
    df = df.copy()
    df["nombre_normalizado"] = df["nombre"].str.lower().str.strip()
    
    indices = []
    precio_base_promedio = None
    
    for fecha in fechas:
        df_fecha = df[df["fecha_extraccion"] == fecha]
        
        if df_fecha.empty:
            continue
        
        precio_promedio = df_fecha["precio"].mean()
        
        if precio_base_promedio is None:
            precio_base_promedio = precio_promedio
            indice = 100.0
        else:
            indice = (precio_promedio / precio_base_promedio) * 100
        
        indices.append({
            "fecha": fecha,
            "precio_promedio": precio_promedio,
            "indice": indice,
            "variacion_diaria": ((precio_promedio / precio_promedio) - 1) * 100 if len(indices) > 0 else 0,
            "num_productos": len(df_fecha)
        })
    
    return pd.DataFrame(indices)


def calcular_variaciones_por_categoria(df: pd.DataFrame, fechas: List[str]) -> pd.DataFrame:
    if len(fechas) < 2:
        return pd.DataFrame()
    
    df = df.copy()
    df["nombre_normalizado"] = df["nombre"].str.lower().str.strip()
    
    df_inicio = df[df["fecha_extraccion"] == fechas[0]]
    df_fin = df[df["fecha_extraccion"] == fechas[-1]]
    
    resultados = []
    
    categorias = set(df_inicio["categoria"].dropna().unique()) | set(df_fin["categoria"].dropna().unique())
    
    for cat in categorias:
        precio_inicio = df_inicio[df_inicio["categoria"] == cat]["precio"].mean()
        precio_fin = df_fin[df_fin["categoria"] == cat]["precio"].mean()
        
        if pd.isna(precio_inicio) or precio_inicio == 0:
            continue
        
        variacion_pct = ((precio_fin - precio_inicio) / precio_inicio) * 100
        
        count_inicio = len(df_inicio[df_inicio["categoria"] == cat])
        count_fin = len(df_fin[df_fin["categoria"] == cat])
        
        resultados.append({
            "categoria": cat,
            "precio_inicio": precio_inicio,
            "precio_fin": precio_fin,
            "variacion_porcentual": variacion_pct,
            "productos_inicio": count_inicio,
            "productos_fin": count_fin
        })
    
    return pd.DataFrame(resultados).sort_values("variacion_porcentual", ascending=False)


def calcular_metricas_inflacion(df: pd.DataFrame, fechas: List[str]) -> Dict:
    metricas = {
        "variacion_diaria_pct": 0.0,
        "variacion_semanal_pct": 0.0,
        "variacion_mensual_pct": 0.0,
        "variacion_acumulada_pct": 0.0,
        "indice_base_100": 100.0,
        "precio_promedio_actual": 0.0,
        "precio_promedio_anterior": 0.0,
        "num_productos": 0,
        "num_fechas": len(fechas)
    }
    
    if not fechas or df.empty:
        return metricas
    
    df = df.copy()
    
    precios_promedio = []
    for fecha in fechas:
        df_fecha = df[df["fecha_extraccion"] == fecha]
        if not df_fecha.empty:
            precios_promedio.append({
                "fecha": fecha,
                "precio_promedio": df_fecha["precio"].mean()
            })
    
    if not precios_promedio:
        return metricas
    
    metricas["precio_promedio_actual"] = precios_promedio[-1]["precio_promedio"]
    metricas["num_productos"] = len(df[df["fecha_extraccion"] == fechas[-1]]) if fechas else 0
    
    if len(precios_promedio) >= 2:
        precio_actual = precios_promedio[-1]["precio_promedio"]
        precio_anterior = precios_promedio[-2]["precio_promedio"]
        
        if precio_anterior > 0:
            metricas["variacion_diaria_pct"] = ((precio_actual - precio_anterior) / precio_anterior) * 100
        
        metricas["precio_promedio_anterior"] = precio_anterior
    
    if len(precios_promedio) >= 7:
        precio_semana_ant = precios_promedio[-7]["precio_promedio"]
        if precio_semana_ant > 0:
            metricas["variacion_semanal_pct"] = ((precio_actual - precio_semana_ant) / precio_semana_ant) * 100
    
    if len(precios_promedio) >= 30:
        precio_mes_ant = precios_promedio[-30]["precio_promedio"]
        if precio_mes_ant > 0:
            metricas["variacion_mensual_pct"] = ((precio_actual - precio_mes_ant) / precio_mes_ant) * 100
    
    if len(precios_promedio) >= 2:
        precio_base = precios_promedio[0]["precio_promedio"]
        if precio_base > 0:
            metricas["variacion_acumulada_pct"] = ((precio_actual - precio_base) / precio_base) * 100
            metricas["indice_base_100"] = (precio_actual / precio_base) * 100
    
    return metricas


def calcular_canasta(df: pd.DataFrame, fechas: List[str], productos_seleccionados: List[str] = None) -> Tuple[pd.DataFrame, Dict]:
    if not fechas or df.empty:
        return pd.DataFrame(), {}
    
    df = df.copy()
    df["nombre_normalizado"] = df["nombre"].str.lower().str.strip()
    
    if productos_seleccionados is None:
        producto_counts = df["nombre_normalizado"].value_counts()
        productos_seleccionados = producto_counts.head(20).index.tolist()
    
    df_canasta = df[df["nombre_normalizado"].isin(productos_seleccionados)]
    
    resultados = []
    for fecha in fechas:
        df_fecha = df_canasta[df_canasta["fecha_extraccion"] == fecha]
        
        if df_fecha.empty:
            continue
        
        precio_total = df_fecha["precio"].sum()
        precio_promedio = df_fecha["precio"].mean()
        
        resultados.append({
            "fecha": fecha,
            "precio_total_canasta": precio_total,
            "precio_promedio": precio_promedio,
            "num_productos": len(df_fecha)
        })
    
    df_canasta_result = pd.DataFrame(resultados)
    
    metricas_canasta = {}
    if not df_canasta_result.empty:
        if len(df_canasta_result) >= 2:
            precio_actual = df_canasta_result.iloc[-1]["precio_total_canasta"]
            precio_anterior = df_canasta_result.iloc[-2]["precio_total_canasta"]
            
            if precio_anterior > 0:
                metricas_canasta["variacion_mensual_pct"] = ((precio_actual - precio_anterior) / precio_anterior) * 100
            
            precio_base = df_canasta_result.iloc[0]["precio_total_canasta"]
            if precio_base > 0:
                metricas_canasta["variacion_acumulada_pct"] = ((precio_actual - precio_base) / precio_base) * 100
                metricas_canasta["indice_base_100"] = (precio_actual / precio_base) * 100
        
        metricas_canasta["precio_actual"] = df_canasta_result.iloc[-1]["precio_total_canasta"] if len(df_canasta_result) > 0 else 0
        metricas_canasta["num_productos_canasta"] = len(productos_seleccionados)
    
    return df_canasta_result, metricas_canasta


def calcular_distribucion_variaciones(df: pd.DataFrame, fechas: List[str]) -> Dict:
    if len(fechas) < 2:
        return {
            "subieron": 0,
            "bajaron": 0,
            "sin_cambio": 0,
            "total": 0,
            "variaciones": []
        }
    
    df = df.copy()
    df["nombre_normalizado"] = df["nombre"].str.lower().str.strip()
    
    df_inicio = df[df["fecha_extraccion"] == fechas[0]].set_index("nombre_normalizado")
    df_fin = df[df["fecha_extraccion"] == fechas[-1]].set_index("nombre_normalizado")
    
    eron = 0
    bajaron = 0
    sin_cambio = 0
    variaciones = []
    
    for nombre_norm in df_inicio.index:
        if nombre_norm in df_fin.index:
            precio_inicio = df_inicio.loc[nombre_norm, "precio"]
            precio_fin = df_fin.loc[nombre_norm, "precio"]
            
            if precio_inicio > 0:
                variacion_pct = ((precio_fin - precio_inicio) / precio_inicio) * 100
                variaciones.append(variacion_pct)
                
                if variacion_pct > 0.1:
                   eron += 1
                elif variacion_pct < -0.1:
                    bajaron += 1
                else:
                    sin_cambio += 1
    
    return {
        "subieron":eron,
        "bajaron": bajaron,
        "sin_cambio": sin_cambio,
        "total":eron + bajaron + sin_cambio,
        "variaciones": variaciones
    }


def calcular_estadisticas_por_categoria(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "categoria" not in df.columns:
        return pd.DataFrame()
    
    df = df.copy()
    df = df[df["categoria"].notna() & (df["categoria"] != "")]
    
    if df.empty:
        return pd.DataFrame()
    
    stats = df.groupby("categoria")["precio"].agg([
        ("promedio", "mean"),
        ("minimo", "min"),
        ("maximo", "max"),
        ("desviacion_estandar", "std"),
        ("count", "count")
    ]).reset_index()
    
    stats["rango"] = stats["maximo"] - stats["minimo"]
    stats["coef_variacion"] = (stats["desviacion_estandar"] / stats["promedio"]) * 100
    
    return stats.sort_values("promedio", ascending=False)


def get_productos_historico(df: pd.DataFrame, nombre_producto: str, fechas: List[str]) -> pd.DataFrame:
    df = df.copy()
    df["nombre_normalizado"] = df["nombre"].str.lower().str.strip()
    
    nombre_buscar = nombre_producto.lower().strip()
    
    df_producto = df[df["nombre_normalizado"].str.contains(nombre_buscar, na=False)]
    
    if df_producto.empty:
        return pd.DataFrame()
    
    resultados = []
    for fecha in fechas:
        df_fecha = df_producto[df_producto["fecha_extraccion"] == fecha]
        
        if not df_fecha.empty:
            for _, row in df_fecha.iterrows():
                resultados.append({
                    "fecha": fecha,
                    "nombre": row["nombre"],
                    "precio": row["precio"],
                    "categoria": row.get("categoria", ""),
                    "marca": row.get("marca", "")
                })
    
    return pd.DataFrame(resultados)


def calcular_cambios_precio(df: pd.DataFrame, fechas: List[str]) -> Dict:
    if len(fechas) < 2:
        return {
            "cambios_por_dia": {},
            "productos_mas_cambios": [],
            "categorias_mas_cambios": []
        }
    
    df = df.copy()
    df["nombre_normalizado"] = df["nombre"].str.lower().str.strip()
    
    cambios_por_dia = {}
    productos_cambios = {}
    categorias_cambios = {}
    
    for i in range(1, len(fechas)):
        fecha_ant = fechas[i-1]
        fecha_act = fechas[i]
        
        df_ant = df[df["fecha_extraccion"] == fecha_ant].set_index("nombre_normalizado")
        df_act = df[df["fecha_extraccion"] == fecha_act].set_index("nombre_normalizado")
        
        cambios = 0
        for nombre_norm in df_ant.index:
            if nombre_norm in df_act.index:
                precio_ant = df_ant.loc[nombre_norm, "precio"]
                precio_act = df_act.loc[nombre_norm, "precio"]
                
                if precio_ant != precio_act:
                    cambios += 1
                    
                    if nombre_norm not in productos_cambios:
                        productos_cambios[nombre_norm] = 0
                    productos_cambios[nombre_norm] += 1
                    
                    cat = df_ant.loc[nombre_norm].get("categoria", "")
                    if cat:
                        if cat not in categorias_cambios:
                            categorias_cambios[cat] = 0
                        categorias_cambios[cat] += 1
        
        cambios_por_dia[fecha_act] = cambios
    
    productos_mas_cambios = sorted(productos_cambios.items(), key=lambda x: x[1], reverse=True)[:10]
    categorias_mas_cambios = sorted(categorias_cambios.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "cambios_por_dia": cambios_por_dia,
        "productos_mas_cambios": [{"nombre": p[0], "cambios": p[1]} for p in productos_mas_cambios],
        "categorias_mas_cambios": [{"categoria": c[0], "cambios": c[1]} for c in categorias_mas_cambios]
    }


def calcular_top_variaciones(df: pd.DataFrame, fechas: List[str], top_n: int = 10) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if len(fechas) < 2:
        return pd.DataFrame(), pd.DataFrame()
    
    df = df.copy()
    df["nombre_normalizado"] = df["nombre"].str.lower().str.strip()
    
    df_inicio = df[df["fecha_extraccion"] == fechas[0]].set_index("nombre_normalizado")
    df_fin = df[df["fecha_extraccion"] == fechas[-1]].set_index("nombre_normalizado")
    
    variaciones = []
    
    for nombre_norm in df_inicio.index:
        if nombre_norm in df_fin.index:
            precio_inicio = df_inicio.loc[nombre_norm, "precio"]
            precio_fin = df_fin.loc[nombre_norm, "precio"]
            nombre = df_inicio.loc[nombre_norm, "nombre"]
            
            if precio_inicio > 0:
                variacion_pct = ((precio_fin - precio_inicio) / precio_inicio) * 100
            
                variaciones.append({
                    "nombre": nombre,
                    "precio_inicio": precio_inicio,
                    "precio_fin": precio_fin,
                    "variacion_porcentual": variacion_pct,
                    "variacion_absoluta": precio_fin - precio_inicio
                })
    
    df_variaciones = pd.DataFrame(variaciones)
    
    if df_variaciones.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    top_suben = df_variaciones.nlargest(top_n, "variacion_porcentual")
    top_bajan = df_variaciones.nsmallest(top_n, "variacion_porcentual")
    
    return top_suben, top_bajan
