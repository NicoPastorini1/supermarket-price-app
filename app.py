import streamlit as st
import pandas as pd
import json
import os
import subprocess
import sys
import time as time_module
from datetime import datetime
from functools import lru_cache
from dotenv import load_dotenv
import altair as alt

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scraper.categorias import get_categorias
from scraper.productos import get_productos_categoria, guardar_productos
from scraper.logs import guardar_log, cargar_logs
from scraper.analisis_inflacion import (
    cargar_todos_los_datos,
    calcular_metricas_inflacion,
    calcular_indice_precios,
    calcular_variaciones_por_categoria,
    calcular_canasta,
    calcular_distribucion_variaciones,
    calcular_estadisticas_por_categoria,
    get_productos_historico,
    calcular_cambios_precio,
    calcular_top_variaciones
)

try:
    from scraper.supabase_client import obtener_productos_desde_supabase
    SUPABASE_DISPONIBLE = True
except:
    SUPABASE_DISPONIBLE = False

st.set_page_config(page_title="Price Scraper", layout="wide", page_icon="💰")

OUTPUT_DIR = "output"


def get_latest_json_file():
    """Obtiene el archivo productos_*.json más reciente."""
    search_dirs = [OUTPUT_DIR, "."]
    
    json_files = []
    for d in search_dirs:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.startswith("productos_") and f.endswith(".json"):
                    filepath = os.path.join(d, f)
                    fecha = f.replace("productos_", "").replace(".json", "")
                    json_files.append((filepath, fecha))
    
    if not json_files:
        return None
    
    json_files.sort(key=lambda x: x[1], reverse=True)
    return json_files[0][0]


@st.cache_data(ttl=0)
def load_all_products(use_latest_only=True):
    """Carga productos desde Supabase (prioridad) o JSON local como fallback."""
    if SUPABASE_DISPONIBLE and os.getenv("SUPABASE_URL"):
        try:
            if use_latest_only:
                productos = obtener_productos_desde_supabase(tienda="dia")
                if productos:
                    return productos, {"dia": productos}
            else:
                productos = obtener_productos_desde_supabase()
                if productos:
                    tiendas = {"dia": [p for p in productos if p.get("tienda") == "dia"]}
                    return productos, tiendas
        except Exception as e:
            st.warning(f"Error conectando a Supabase: {e}. Usando datos locales.")
    
    if use_latest_only:
        latest_file = get_latest_json_file()
        if not latest_file:
            return None, {}
        
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, list):
            data = {"productos": data, "tienda": "dia"}
        
        tienda = data.get("tienda", "dia")
        productos = data.get("productos", [])
        
        return productos, {tienda: productos} if productos else {}
    else:
        search_dirs = [OUTPUT_DIR, "."]
        
        json_files = []
        for d in search_dirs:
            if os.path.exists(d):
                json_files.extend([
                    os.path.join(d, f) for f in os.listdir(d) 
                    if f.startswith("productos_") and f.endswith(".json")
                ])
        
        all_products = []
        tiendas = {}
        
        for filepath in json_files:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if isinstance(data, list):
                data = {"productos": data, "tienda": "dia"}
            
            tienda = data.get("tienda", "dia")
            productos = data.get("productos", [])
            
            if productos:
                if tienda not in tiendas:
                    tiendas[tienda] = []
                tiendas[tienda].extend(productos)
                all_products.extend(productos)
        
        if not all_products:
            return None, {}
        
        seen_ids = set()
        unique_products = []
        for p in all_products:
            pid = p.get("productId")
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                unique_products.append(p)
        
        return unique_products, tiendas


@st.cache_data(ttl=0)
def load_product_history():
    """Carga el historial de precios desde Supabase (prioridad) o JSON local como fallback."""
    historial = {}
    
    if SUPABASE_DISPONIBLE and os.getenv("SUPABASE_URL"):
        try:
            productos = obtener_productos_desde_supabase()
            if productos:
                for p in productos:
                    pid = p.get("product_id") or p.get("productId")
                    if pid:
                        fecha = p.get("fecha_extraccion", "")[:10] if p.get("fecha_extraccion") else ""
                        if pid not in historial:
                            historial[pid] = []
                        historial[pid].append({
                            "fecha": fecha,
                            "precio": p.get("precio"),
                            "nombre": p.get("nombre")
                        })
                
                for pid in historial:
                    historial[pid].sort(key=lambda x: x["fecha"])
                
                return historial
        except Exception as e:
            st.warning(f"Error conectando a Supabase para historial: {e}")
    
    search_dirs = [OUTPUT_DIR, "."]
    
    json_files = []
    for d in search_dirs:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.startswith("productos_") and f.endswith(".json"):
                    filepath = os.path.join(d, f)
                    fecha = f.replace("productos_", "").replace(".json", "")
                    json_files.append((filepath, fecha))
    
    for filepath, fecha in json_files:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, list):
            data = {"productos": data}
        
        productos = data.get("productos", [])
        
        for p in productos:
            pid = p.get("productId")
            if pid:
                if pid not in historial:
                    historial[pid] = []
                historial[pid].append({
                    "fecha": fecha,
                    "precio": p.get("precio"),
                    "nombre": p.get("nombre")
                })
    
    for pid in historial:
        historial[pid].sort(key=lambda x: x["fecha"])
    
    return historial
    
    return historial


def mostrar_historial_precio(product_id, historial):
    """Muestra un mini gráfico de historial de precios para un producto."""
    if product_id not in historial or len(historial[product_id]) < 2:
        return None
    
    data = historial[product_id]
    
    df_hist = pd.DataFrame(data)
    df_hist["fecha"] = pd.to_datetime(df_hist["fecha"])
    df_hist = df_hist.sort_values("fecha")
    
    if len(df_hist) < 2:
        return None
    
    df_hist["variacion_diaria"] = df_hist["precio"].diff()
    df_hist["variacion_pct"] = df_hist["precio"].pct_change() * 100
    
    variacion_actual = df_hist["variacion_diaria"].iloc[-1] if len(df_hist) > 0 else 0
    variacion_pct_actual = df_hist["variacion_pct"].iloc[-1] if len(df_hist) > 0 else 0
    
    chart = alt.Chart(df_hist).mark_line(point=True, strokeWidth=2).encode(
        x=alt.X("fecha:T", axis=alt.Axis(format="%d/%m", title="Fecha")),
        y=alt.Y("precio:Q", title="Precio ($)"),
        tooltip=["fecha:T", "precio:Q", "variacion_diaria:Q", "variacion_pct:Q"]
    ).properties(
        height=150,
        width=250
    ).configure_view(
        strokeWidth=0
    )
    
    return chart, variacion_actual, variacion_pct_actual


def mostrar_home():
    """Página principal con botones de actualización y datos."""
    st.title("Price Scraper")
    st.markdown("Comparador de precios de Supermercados")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Actualizar todo", type="primary", use_container_width=True):
            with st.spinner("Actualizando categorías y productos..."):
                inicio = time_module.time()
                try:
                    result = subprocess.run(
                        [sys.executable, "scraper/main.py"],
                        capture_output=True, text=True, timeout=600
                    )
                    duracion = time_module.time() - inicio
                    if result.returncode == 0:
                        st.success("✓ Actualización completa!")
                        guardar_log("completo", 0, duracion, "exitoso")
                    else:
                        st.error(f"Error: {result.stderr}")
                        guardar_log("completo", 0, duracion, "error", result.stderr)
                    st.rerun()
                except Exception as e:
                    duracion = time_module.time() - inicio
                    st.error(f"Error: {e}")
                    guardar_log("completo", 0, duracion, "error", str(e))
                    st.rerun()
    
    with col2:
        if st.button("🔄 Actualizar: Categorías", use_container_width=True):
            with st.spinner("Obteniendo categorías..."):
                inicio = time_module.time()
                try:
                    cats = get_categorias()
                    os.makedirs("output", exist_ok=True)
                    with open("output/categorias.json", "w", encoding="utf-8") as f:
                        json.dump(cats, f, ensure_ascii=False, indent=2)
                    duracion = time_module.time() - inicio
                    st.success(f"✓ {len(cats)} categorías actualizadas!")
                    guardar_log("categorias", len(cats), duracion, "exitoso")
                    st.rerun()
                except Exception as e:
                    duracion = time_module.time() - inicio
                    st.error(f"Error: {e}")
                    guardar_log("categorias", 0, duracion, "error", str(e))
                    st.rerun()
    
    with col3:
        if st.button("🔄 Actualizar: Productos", use_container_width=True):
            with st.spinner("Obteniendo productos..."):
                inicio = time_module.time()
                try:
                    prods, metadata = get_productos_categoria(tienda="dia")
                    duracion = time_module.time() - inicio
                    if prods:
                        json_path, csv_path = guardar_productos(prods, OUTPUT_DIR)
                        st.success(f"✓ {len(prods)} productos actualizados!")
                        guardar_log("productos", len(prods), duracion, "exitoso", 
                                   productos_unicos=len(prods),
                                   categorias=metadata.get("categorias", 0),
                                   paginas_procesadas=metadata.get("paginas", 0))
                    else:
                        st.warning("No se encontraron productos")
                        guardar_log("productos", 0, duracion, "sin_datos")
                    st.rerun()
                except Exception as e:
                    duracion = time_module.time() - inicio
                    st.error(f"Error: {e}")
                    guardar_log("productos", 0, duracion, "error", str(e))
                    st.rerun()
    
    st.divider()
    mostrar_datos()


def mostrar_datos():
    """Muestra los datos de productos."""
    productos, tiendas_dict = load_all_products()
    
    if not productos:
        st.info("No hay datos disponibles. Actualizá los productos primero.")
        return
    
    tiendas = list(tiendas_dict.keys())
    df = pd.DataFrame(productos)
    
    if "tienda" in df.columns:
        df_tienda = df[df["tienda"] == "dia"] if "dia" in df["tienda"].values else df
    else:
        df_tienda = df
    
    st.metric("Total Productos", len(df_tienda))
    
    historial = load_product_history()
    
    if historial:
        df_tienda["variacion_pct"] = 0.0
        df_tienda["precio_anterior"] = None
        
        for idx, row in df_tienda.iterrows():
            pid = row.get("productId")
            if pid and pid in historial and len(historial[pid]) >= 2:
                hist = historial[pid]
                precio_actual = row.get("precio")
                precio_anterior = hist[-2].get("precio")
                if precio_anterior and precio_anterior > 0:
                    df_tienda.at[idx, "variacion_pct"] = ((precio_actual - precio_anterior) / precio_anterior) * 100
                    df_tienda.at[idx, "precio_anterior"] = precio_anterior
    
    st.subheader("Filtros")
    
    col_buscar, col_marca, col_categoria, col_variacion = st.columns(4)
    
    with col_buscar:
        busqueda = st.text_input("Buscar producto", placeholder="Ej: leche, fideos...")
    
    with col_marca:
        if "marca" in df_tienda.columns:
            marcas = ["Todas"] + sorted(df_tienda["marca"].dropna().unique().tolist())
            marca_sel = st.selectbox("Marca", marcas)
        else:
            marca_sel = "Todas"
    
    with col_categoria:
        if "categoria" in df_tienda.columns:
            categorias = ["Todas"] + sorted(df_tienda["categoria"].dropna().unique().tolist())
            categoria_sel = st.selectbox("Categoría", categorias)
        else:
            categoria_sel = "Todas"
    
    with col_variacion:
        variacion_opciones = ["Todas", "Subieron ▲", "Bajaron ▼", "Sin cambios"]
        variacion_sel = st.selectbox("Variación precio", variacion_opciones)
    
    df_filtrado = df_tienda.copy()
    
    if busqueda and "nombre" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["nombre"].str.lower().str.contains(busqueda.lower(), na=False)]
    
    if variacion_sel == "Subieron ▲":
        df_filtrado = df_filtrado[df_filtrado["variacion_pct"] > 0.1]
    elif variacion_sel == "Bajaron ▼":
        df_filtrado = df_filtrado[df_filtrado["variacion_pct"] < -0.1]
    elif variacion_sel == "Sin cambios":
        df_filtrado = df_filtrado[(df_filtrado["variacion_pct"] >= -0.1) & (df_filtrado["variacion_pct"] <= 0.1)]
    
    if marca_sel != "Todas" and "marca" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["marca"] == marca_sel]
    if categoria_sel != "Todas" and "categoria" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["categoria"] == categoria_sel]
    
    st.subheader(f"Productos ({len(df_filtrado)} resultados)")
    
    cols_per_row = 4
    rows = [df_filtrado.iloc[i:i+cols_per_row] for i in range(0, min(len(df_filtrado), 50), cols_per_row)]
    
    historial = load_product_history()
    
    def imagen_valida(url):
        if not url:
            return False
        url_lower = url.lower()
        return 'footer' not in url_lower and 'logo' not in url_lower and url_lower.startswith('http')
    
    for row_group in rows:
        cols = st.columns(cols_per_row)
        for idx, (_, row) in enumerate(row_group.iterrows()):
            with cols[idx]:
                with st.container(border=True):
                    card_html = f'''
                    <div style="display:flex;flex-direction:column;height:320px;">
                        <div style="height:150px;display:flex;align-items:center;justify-content:center;overflow:hidden;">
                    '''
                    
                    img_url = row.get("imagen")
                    if img_url and imagen_valida(img_url):
                        card_html += f'<img src="{img_url}" style="max-height:150px;max-width:100%;object-fit:contain;">'
                    else:
                        card_html += '<span style="font-size:40px;">📦</span>'
                    
                    card_html += '''
                        </div>
                        <div style="flex:1;overflow:hidden;">
                    '''
                    st.markdown(card_html, unsafe_allow_html=True)
                    
                    nombre = str(row.get('nombre', ''))
                    st.markdown(f"**{nombre[:40]}...**" if len(nombre) > 40 else f"**{nombre}**")
                    
                    precio = row.get('precio', 0)
                    precio_str = f"${int(precio):,}".replace(",", ".") if precio else "$0"
                    st.markdown(f"### {precio_str}")
                    
                    product_id = row.get('productId')
                    tiene_historial = False
                    if product_id and product_id in historial and len(historial[product_id]) >= 2:
                        result = mostrar_historial_precio(product_id, historial)
                        if result:
                            chart, variacion, variacion_pct = result
                            emoji = "📈" if variacion > 0 else ("📉" if variacion < 0 else "➡️")
                            st.caption(f"{emoji} {variacion_pct:+.1f}%")
                            with st.expander("📊"):
                                st.altair_chart(chart, use_container_width=True)
                            tiene_historial = True
                    
                    st.markdown('</div></div>', unsafe_allow_html=True)
                    

    
    with st.expander("Ver datos en tabla"):
        cols_tabla = ["nombre", "marca", "precio"]
        if "categoria" in df_tienda.columns:
            cols_tabla.insert(2, "categoria")
        if "precio_por_unidad" in df_tienda.columns:
            cols_tabla.append("precio_por_unidad")
        if "stock" in df_tienda.columns:
            cols_tabla.append("stock")
        
        df_display = df_filtrado[[c for c in cols_tabla if c in df_filtrado.columns]].copy()
        if 'precio' in df_display.columns:
            df_display['precio'] = df_display['precio'].apply(lambda x: f"${int(x):,}".replace(",", ".") if pd.notna(x) else "$0")
        
        st.dataframe(
            df_display,
            use_container_width=True,
            height=400
        )


def mostrar_logs():
    """Página de logs de ejecuciones con filtros y análisis."""
    st.title("📋 Logs de Ejecución")
    
    df_logs = cargar_logs()
    
    if df_logs.empty:
        st.info("No hay logs disponibles.")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ejecuciones", len(df_logs))
    col2.metric("Exitosas", len(df_logs[df_logs["estado"] == "exitoso"]))
    col3.metric("Errores", len(df_logs[df_logs["estado"] == "error"]))
    col4.metric("Productos Total", int(df_logs["cantidad_productos"].sum()))
    
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Duración Promedio", f"{df_logs['duracion_segundos'].mean():.1f}s")
    col6.metric("Más Rápida", f"{df_logs['duracion_segundos'].min():.1f}s")
    col7.metric("Más Lenta", f"{df_logs['duracion_segundos'].max():.1f}s")
    col8.metric("Velocidad Promedio", f"{df_logs['velocidad_productos_x_seg'].mean():.1f} prod/s")
    
    st.subheader("Filtros")
    
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    with col_f1:
        filtro_tipo = st.multiselect(
            "Tipo de ejecución",
            options=df_logs["tipo_ejecucion"].unique(),
            default=df_logs["tipo_ejecucion"].unique()
        )
    
    with col_f2:
        filtro_estado = st.multiselect(
            "Estado",
            options=df_logs["estado"].unique(),
            default=df_logs["estado"].unique()
        )
    
    with col_f3:
        fechas = sorted(df_logs["fecha"].unique(), reverse=True)
        filtro_fecha = st.multiselect(
            "Fecha",
            options=fechas,
            default=fechas[:7] if len(fechas) > 7 else fechas
        )
    
    with col_f4:
        min_productos = int(df_logs["cantidad_productos"].min())
        max_productos = int(df_logs["cantidad_productos"].max())
        rango = st.slider("Cantidad productos", min_productos, max_productos if max_productos > 0 else 100, (min_productos, max_productos if max_productos > 0 else 100))
    
    df_filtrado = df_logs[
        (df_logs["tipo_ejecucion"].isin(filtro_tipo)) &
        (df_logs["estado"].isin(filtro_estado)) &
        (df_logs["fecha"].isin(filtro_fecha)) &
        (df_logs["cantidad_productos"] >= rango[0]) &
        (df_logs["cantidad_productos"] <= rango[1])
    ].copy()
    
    st.divider()
    st.subheader(f"Historial ({len(df_filtrado)} registros)")
    
    df_display = df_filtrado.sort_values(["fecha", "hora"], ascending=[False, False]).head(100)
    
    def estilo_estado(val):
        if val == "exitoso":
            return "color: #13ec5b; font-weight: bold"
        elif val == "error":
            return "color: #ff6b6b; font-weight: bold"
        elif val == "sin_datos":
            return "color: #ffa502; font-weight: bold"
        return ""
    
    cols_mostrar = ["fecha", "hora", "tipo_ejecucion", "cantidad_productos", "duracion_segundos", "velocidad_productos_x_seg", "estado"]
    df_view = df_display[cols_mostrar].copy()
    df_view.columns = ["Fecha", "Hora", "Tipo", "Productos", "Duración(s)", "Velocidad(prod/s)", "Estado"]
    
    st.dataframe(
        df_view.style.applymap(estilo_estado, subset=["Estado"]),
        use_container_width=True,
        height=400
    )
    
    if len(df_filtrado) > 1:
        st.subheader("📊 Análisis")
        
        col_a1, col_a2 = st.columns(2)
        
        with col_a1:
            st.markdown("#### Productos por Ejecución")
            st.line_chart(df_filtrado.set_index("fecha")["cantidad_productos"])
        
        with col_a2:
            st.markdown("#### Duración por Ejecución")
            st.line_chart(df_filtrado.set_index("fecha")["duracion_segundos"])
        
        col_a3, col_a4 = st.columns(2)
        
        with col_a3:
            st.markdown("#### Ejecuciones por Tipo")
            tipo_counts = df_filtrado["tipo_ejecucion"].value_counts()
            st.bar_chart(tipo_counts)
        
        with col_a4:
            st.markdown("#### Estado de Ejecuciones")
            estado_counts = df_filtrado["estado"].value_counts()
            st.bar_chart(estado_counts)
        
        with st.expander("Ver todos los datos"):
            st.dataframe(df_filtrado.sort_values(["fecha", "hora"], ascending=[False, False]), use_container_width=True)


def mostrar_dashboard():
    """Dashboard para analizar datos de productos."""
    st.title("📊 Dashboard - Análisis de Datos")
    
    productos, tiendas_dict = load_all_products()
    
    if not productos:
        st.info("No hay datos disponibles. Actualizá los productos primero.")
        return
    
    df = pd.DataFrame(productos)
    
    st.subheader("🔍 Filtros")
    
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    with col_f1:
        busqueda = st.text_input("Buscar producto", placeholder="Ej: leche, arroz...")
    
    with col_f2:
        precio_min = float(df['precio'].min()) if 'precio' in df.columns else 0
        precio_max = float(df['precio'].max()) if 'precio' in df.columns else 10000
        rango_precio = st.slider("Rango de precio", precio_min, precio_max, (precio_min, precio_max))
    
    with col_f3:
        if "marca" in df.columns and df["marca"].notna().any():
            marcas = ["Todas"] + sorted(df["marca"].dropna().unique().tolist())
            marca_sel = st.selectbox("Marca", marcas[:50])
        else:
            marca_sel = "Todas"
    
    with col_f4:
        if "categoria" in df.columns and df["categoria"].notna().any():
            categorias = ["Todas"] + sorted(df["categoria"].dropna().unique().tolist())
            categoria_sel = st.selectbox("Categoría", categorias[:50])
        else:
            categoria_sel = "Todas"
    
    df_filtrado = df.copy()
    
    if busqueda and "nombre" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["nombre"].str.lower().str.contains(busqueda.lower(), na=False)]
    
    if "precio" in df_filtrado.columns:
        df_filtrado = df_filtrado[(df_filtrado["precio"] >= rango_precio[0]) & (df_filtrado["precio"] <= rango_precio[1])]
    
    if marca_sel != "Todas" and "marca" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["marca"] == marca_sel]
    
    if categoria_sel != "Todas" and "categoria" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["categoria"] == categoria_sel]
    
    st.divider()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Productos encontrados", len(df_filtrado))
    if "precio" in df_filtrado.columns and len(df_filtrado) > 0:
        col2.metric("Precio mínimo", f"${int(df_filtrado['precio'].min()):,}".replace(",", "."))
        col3.metric("Precio máximo", f"${int(df_filtrado['precio'].max()):,}".replace(",", "."))
        col4.metric("Precio promedio", f"${int(df_filtrado['precio'].mean()):,}".replace(",", "."))
    
    st.divider()
    
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.markdown("#### Distribución de Precios")
        if "precio" in df_filtrado.columns and len(df_filtrado) > 0:
            bins = st.slider("Cantidad de bins", 5, 50, 20)
            hist, bin_edges = pd.cut(df_filtrado["precio"], bins=bins, retbins=True)
            hist_counts = hist.value_counts().sort_index()
            hist_labels = [f"${int(b.left):,}-${int(b.right)}" for b in hist_counts.index]
            hist_df = pd.DataFrame({"rango": hist_labels, "cantidad": hist_counts.values})
            st.bar_chart(hist_df.set_index("rango"))
    
    with col_g2:
        st.markdown("#### Top 10 Productos más caros")
        if "precio" in df_filtrado.columns and len(df_filtrado) > 0:
            top_caros = df_filtrado.nlargest(10, "precio")[["nombre", "precio"]].copy()
            top_caros["precio"] = top_caros["precio"].apply(lambda x: f"${int(x):,}".replace(",", "."))
            st.dataframe(top_caros, use_container_width=True, hide_index=True)
    
    st.subheader("📋 Productos Filtrados")
    
    st.dataframe(
        df_filtrado[["nombre", "precio", "marca"]].head(100) if "precio" in df_filtrado.columns else df_filtrado[["nombre"]].head(100),
        use_container_width=True,
        height=300
    )


def mostrar_analisis_inflacion():
    st.title("📈 Análisis de Inflación")
    
    df, fechas = cargar_todos_los_datos()
    
    if df.empty or len(fechas) < 2:
        st.info("Se necesitan al menos 2 días de datos para analizar inflación. Actualizá los productos varios días.")
        return
    
    st.markdown(f"**Período:** {fechas[0]} a {fechas[-1]} ({len(fechas)} días)")
    
    metricas = calcular_metricas_inflacion(df, fechas)
    
    st.subheader("📊 KPIs Principales")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Inflación Diaria", f"{metricas['variacion_diaria_pct']:+.2f}%", delta_color="inverse")
    with col2:
        st.metric("Inflación Semanal", f"{metricas['variacion_semanal_pct']:+.2f}%", delta_color="inverse")
    with col3:
        st.metric("Inflación Mensual", f"{metricas['variacion_mensual_pct']:+.2f}%", delta_color="inverse")
    with col4:
        st.metric("Inflación Acumulada", f"{metricas['variacion_acumulada_pct']:+.2f}%", delta_color="inverse")
    with col5:
        st.metric("Índice Base 100", f"{metricas['indice_base_100']:.2f}")
    
    st.divider()
    
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.subheader("📈 Evolución del Índice de Precios")
        df_indice = calcular_indice_precios(df, fechas)
        if not df_indice.empty:
            df_indice["fecha"] = pd.to_datetime(df_indice["fecha"])
            chart = alt.Chart(df_indice).mark_line(point=True, strokeWidth=2, color="#13ec5b").encode(
                x=alt.X("fecha:T", axis=alt.Axis(format="%d/%m", title="Fecha")),
                y=alt.Y("indice:Q", title="Índice (Base 100)", scale=alt.Scale(zero=True)),
                tooltip=["fecha:T", "indice:Q", "precio_promedio:Q"]
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)
    
    with col_g2:
        st.subheader("🍔 Precio de la Canasta")
        df_canasta, metricas_canasta = calcular_canasta(df, fechas)
        if not df_canasta.empty:
            df_canasta["fecha"] = pd.to_datetime(df_canasta["fecha"])
            chart = alt.Chart(df_canasta).mark_line(point=True, strokeWidth=2, color="#ff6b6b").encode(
                x=alt.X("fecha:T", axis=alt.Axis(format="%d/%m", title="Fecha")),
                y=alt.Y("precio_total_canasta:Q", title="Precio Total ($)"),
                tooltip=["fecha:T", "precio_total_canasta:Q"]
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)
            
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.metric("Precio Canasta", f"${metricas_canasta.get('precio_actual', 0):,.0f}".replace(",", "."))
            with col_c2:
                st.metric("Variación Acumulada", f"{metricas_canasta.get('variacion_acumulada_pct', 0):+.2f}%")
    
    st.divider()
    
    st.subheader("📊 Variaciones por Categoría")
    
    df_categorias = calcular_variaciones_por_categoria(df, fechas)
    
    if not df_categorias.empty:
        col_cat1, col_cat2 = st.columns(2)
        
        with col_cat1:
            st.markdown("**Categorías que más subieron**")
            top_suben = df_categorias.head(5)
            st.dataframe(top_suben[["categoria", "variacion_porcentual", "precio_fin"]].rename(
                columns={"categoria": "Categoría", "variacion_porcentual": "Variación %", "precio_fin": "Precio $"}),
                use_container_width=True, hide_index=True)
        
        with col_cat2:
            st.markdown("**Categorías que bajaron**")
            top_bajan = df_categorias.tail(5)
            st.dataframe(top_bajan[["categoria", "variacion_porcentual", "precio_fin"]].rename(
                columns={"categoria": "Categoría", "variacion_porcentual": "Variación %", "precio_fin": "Precio $"}),
                use_container_width=True, hide_index=True)
        
        st.markdown("**Variación por Categoría**")
        chart_cat = alt.Chart(df_categorias.head(15)).mark_bar().encode(
            x=alt.X("variacion_porcentual:Q", title="Variación %"),
            y=alt.Y("categoria:N", sort="-x"),
            color=alt.Color("variacion_porcentual:Q", scale=alt.Scale(scheme="redyellowgreen"), legend=None)
        ).properties(height=400)
        st.altair_chart(chart_cat, use_container_width=True)
    
    st.divider()
    
    col_t1, col_t2 = st.columns(2)
    
    with col_t1:
        st.subheader("📈 Productos con Mayor Aumento")
        top_suben_prod, _ = calcular_top_variaciones(df, fechas, top_n=10)
        if not top_suben_prod.empty:
            st.dataframe(top_suben_prod[["nombre", "precio_inicio", "precio_fin", "variacion_porcentual"]].rename(
                columns={"nombre": "Producto", "precio_inicio": "Precio Inicio", "precio_fin": "Precio Fin", "variacion_porcentual": "Variación %"}),
                use_container_width=True, hide_index=True)
    
    with col_t2:
        st.subheader("📉 Productos con Mayor Caída")
        _, top_bajan_prod = calcular_top_variaciones(df, fechas, top_n=10)
        if not top_bajan_prod.empty:
            st.dataframe(top_bajan_prod[["nombre", "precio_inicio", "precio_fin", "variacion_porcentual"]].rename(
                columns={"nombre": "Producto", "precio_inicio": "Precio Inicio", "precio_fin": "Precio Fin", "variacion_porcentual": "Variación %"}),
                use_container_width=True, hide_index=True)
    
    st.divider()
    
    st.subheader("📊 Distribución de Variaciones")
    
    distribucion = calcular_distribucion_variaciones(df, fechas)
    
    if distribucion["total"] > 0:
        col_d1, col_d2, col_d3, col_d4 = st.columns(4)
        
        with col_d1:
            st.metric("Productos que Subieron", f"{distribucion['subieron']} ({distribucion['subieron']/distribucion['total']*100:.1f}%)")
        with col_d2:
            st.metric("Productos que Bajaron", f"{distribucion['bajaron']} ({distribucion['bajaron']/distribucion['total']*100:.1f}%)")
        with col_d3:
            st.metric("Sin Cambios", f"{distribucion['sin_cambio']} ({distribucion['sin_cambio']/distribucion['total']*100:.1f}%)")
        with col_d4:
            st.metric("Total Analizados", distribucion["total"])
        
        if distribucion["variaciones"]:
            st.markdown("**Histograma de Variaciones de Precio**")
            df_variaciones = pd.DataFrame({"variacion": distribucion["variaciones"]})
            chart_hist = alt.Chart(df_variaciones).mark_bar().encode(
                x=alt.X("variacion:Q", bin=alt.Bin(maxbins=30), title="Variación %"),
                y=alt.Y("count():Q", title="Cantidad")
            ).properties(height=250)
            st.altair_chart(chart_hist, use_container_width=True)
    
    st.divider()
    
    st.subheader("📋 Estadísticas por Categoría")
    
    df_stats = calcular_estadisticas_por_categoria(df)
    
    if not df_stats.empty:
        st.dataframe(df_stats.rename(columns={
            "categoria": "Categoría", "promedio": "Promedio", "minimo": "Mínimo",
            "maximo": "Máximo", "desviacion_estandar": "Desv. Est.",
            "rango": "Rango", "coef_variacion": "Coef. Var. %", "count": "Productos"
        }), use_container_width=True, hide_index=True)
    
    st.divider()
    
    st.subheader("🔄 Frecuencia de Cambios de Precio")
    
    cambios = calcular_cambios_precio(df, fechas)
    
    col_c1, col_c2 = st.columns(2)
    
    with col_c1:
        st.markdown("**Productos con más cambios de precio**")
        if cambios["productos_mas_cambios"]:
            df_prod_cambios = pd.DataFrame(cambios["productos_mas_cambios"])
            st.dataframe(df_prod_cambios.rename(columns={"nombre": "Producto", "cambios": "Cambios"}),
                use_container_width=True, hide_index=True)
    
    with col_c2:
        st.markdown("**Categorías con más cambios de precio**")
        if cambios["categorias_mas_cambios"]:
            df_cat_cambios = pd.DataFrame(cambios["categorias_mas_cambios"])
            st.dataframe(df_cat_cambios.rename(columns={"categoria": "Categoría", "cambios": "Cambios"}),
                use_container_width=True, hide_index=True)
    
    if cambios["cambios_por_dia"]:
        st.markdown("**Cambios de precio por día**")
        df_cambios_dia = pd.DataFrame(list(cambios["cambios_por_dia"].items()), columns=["fecha", "cambios"])
        df_cambios_dia["fecha"] = pd.to_datetime(df_cambios_dia["fecha"])
        chart_cambios = alt.Chart(df_cambios_dia).mark_line(point=True).encode(
            x=alt.X("fecha:T", axis=alt.Axis(format="%d/%m")),
            y=alt.Y("cambios:Q")
        ).properties(height=200)
        st.altair_chart(chart_cambios, use_container_width=True)
    
    st.divider()
    
    st.subheader("🔍 Evolución de Precio por Producto")
    
    col_prod1, col_prod2 = st.columns([2, 1])
    
    with col_prod1:
        producto_buscar = st.text_input("Buscar producto", placeholder="Ej: leche, arroz...")
    
    with col_prod2:
        cant_graficos = st.selectbox("Cantidad de productos", [3, 5, 10], index=0)
    
    if producto_buscar:
        df_prod_hist = get_productos_historico(df, producto_buscar, fechas)
        
        if not df_prod_hist.empty:
            df_prod_hist["fecha"] = pd.to_datetime(df_prod_hist["fecha"])
            
            productos_unicos = df_prod_hist["nombre"].unique()[:cant_graficos]
            df_filtro = df_prod_hist[df_prod_hist["nombre"].isin(productos_unicos)]
            
            chart_prod = alt.Chart(df_filtro).mark_line(point=True).encode(
                x=alt.X("fecha:T", axis=alt.Axis(format="%d/%m")),
                y=alt.Y("precio:Q"),
                color="nombre:N",
                tooltip=["fecha:T", "precio:Q", "nombre:N"]
            ).properties(height=350)
            st.altair_chart(chart_prod, use_container_width=True)


st.markdown("""
<style>
    div[data-testid="stSidebar"] {
        background-color: #102216;
    }
    div[data-testid="stSidebar"] .stRadio > label {
        background-color: #13ec5b;
        color: #102216;
        padding: 12px 20px;
        border-radius: 8px;
        margin-bottom: 8px;
        font-weight: bold;
        width: 100%;
        display: block;
    }
    div[data-testid="stSidebar"] .stRadio > label:has(input:checked) {
        background-color: #0fa845;
    }
    div[data-testid="stSidebar"] .stRadio > div {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    div[data-testid="stSidebar"] .stRadio > div > label {
        margin: 0;
    }
    .stButton > button {
        border-radius: 12px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

if "pagina" not in st.session_state:
    st.session_state.pagina = "Home"

with st.sidebar:
    st.markdown("### 💰 Price Scraper")
    st.divider()
    
    if st.button("🏠 Home", use_container_width=True, 
                 type="primary" if st.session_state.pagina == "Home" else "secondary"):
        st.session_state.pagina = "Home"
        st.rerun()
    
    if st.button("📊 Dashboard", use_container_width=True,
                 type="primary" if st.session_state.pagina == "Dashboard" else "secondary"):
        st.session_state.pagina = "Dashboard"
        st.rerun()
    
    if st.button("📋 Logs", use_container_width=True,
                 type="primary" if st.session_state.pagina == "Logs" else "secondary"):
        st.session_state.pagina = "Logs"
        st.rerun()
    
    if st.button("📈 Inflación", use_container_width=True,
                 type="primary" if st.session_state.pagina == "Inflación" else "secondary"):
        st.session_state.pagina = "Inflación"
        st.rerun()
    
    st.divider()
    st.caption("Navegación")

if st.session_state.pagina == "Home":
    mostrar_home()
elif st.session_state.pagina == "Dashboard":
    mostrar_dashboard()
elif st.session_state.pagina == "Inflación":
    mostrar_analisis_inflacion()
else:
    mostrar_logs()
