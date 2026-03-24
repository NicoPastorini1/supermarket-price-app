"""
main.py
Orquesta el scraping completo de Supermercados DIA Argentina.
Resultado: output/productos_YYYY-MM-DD.json y guarda en Supabase
"""

import time
import os
from datetime import datetime
from categorias import get_categorias
from productos import get_productos_categoria, guardar_productos
from logs import guardar_log
from supabase_client import guardar_productos_supabase, eliminar_productos_fecha

OUTPUT_DIR = "output"
TIENDA = "dia"


def main():
    inicio = time.time()
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    print("=" * 50)
    print("DIA Argentina — Scraper de productos")
    print(f"Fecha: {fecha_hoy} {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 50)

    print("\n[1/2] Obteniendo categorías...")
    categorias = get_categorias()
    print(f"  → {len(categorias)} categorías encontradas")

    print("\n[2/2] Scrapeando productos...")
    todos = []
    metadata = {"duracion": 0, "categorias": 0, "paginas": 0}

    try:
        todos, metadata = get_productos_categoria(tienda=TIENDA)
        print(f"  → {len(todos)} productos obtenidos")
    except Exception as e:
        duracion = time.time() - inicio
        print(f"  → ERROR: {e}")
        guardar_log("completo", 0, duracion, "error", str(e))
        return

    if todos:
        json_path, csv_path = guardar_productos(todos, OUTPUT_DIR)
        
        duracion = time.time() - inicio
        
        print("\n[3/3] Guardando en Supabase...")
        supabase_guardado = False
        if os.getenv("SUPABASE_KEY"):
            try:
                eliminar_productos_fecha(fecha_hoy, TIENDA)
                supabase_guardado = guardar_productos_supabase(todos)
            except Exception as e:
                print(f"  → Error Supabase: {e}")
        
        print("\n" + "=" * 50)
        print(f"✓ Total productos únicos: {len(todos)}")
        print(f"✓ JSON: {json_path}")
        if supabase_guardado:
            print(f"✓ Supabase: ✓")
        print(f"✓ Duración total: {duracion:.1f}s")
        print("=" * 50)
        
        guardar_log("completo", len(todos), duracion, "exitoso",
                   productos_unicos=len(todos),
                   categorias=metadata.get("categorias", 0),
                   paginas_procesadas=metadata.get("paginas", 0))
    else:
        duracion = time.time() - inicio
        print("\n⚠️ No se encontraron productos")
        guardar_log("completo", 0, duracion, "sin_datos")


if __name__ == "__main__":
    main()
