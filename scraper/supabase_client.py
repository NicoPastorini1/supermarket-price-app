from supabase import create_client, Client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mkyddyiqlbiewpwlhhbk.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

_client: Client = None

def get_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_KEY:
            raise ValueError("SUPABASE_KEY no está configurada")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client

def guardar_productos_supabase(productos: list[dict]) -> bool:
    client = get_client()
    if not productos:
        return False
    
    data = []
    for p in productos:
        data.append({
            "product_id": p.get("productId", ""),
            "nombre": p.get("nombre", ""),
            "marca": p.get("marca", ""),
            "categoria": p.get("categoria", ""),
            "subcategoria": p.get("subcategoria", ""),
            "tienda": p.get("tienda", "dia"),
            "precio": p.get("precio", 0),
            "precio_por_unidad": p.get("precio_por_unidad"),
            "unidad_medida": p.get("unidad_medida"),
            "iva": p.get("iva"),
            "stock": p.get("stock", 1),
            "disponible": p.get("disponible", True),
            "imagen": p.get("imagen"),
            "url": p.get("url"),
            "fecha_extraccion": p.get("fecha_extraccion")
        })
    
    try:
        response = client.table("productos").insert(data).execute()
        print(f"[Supabase] {len(response.data)} productos guardados")
        return True
    except Exception as e:
        print(f"[Supabase] Error al guardar: {e}")
        return False

def obtener_productos_desde_supabase(tienda: str = None, fecha: str = None) -> list[dict]:
    client = get_client()
    
    query = client.table("productos").select("*")
    
    if tienda:
        query = query.eq("tienda", tienda)
    
    if fecha:
        query = query.eq("fecha_extraccion", fecha)
    
    response = query.execute()
    return response.data

def eliminar_productos_fecha(fecha: str, tienda: str = "dia") -> bool:
    client = get_client()
    try:
        client.table("productos").delete().eq("fecha_extraccion", fecha).eq("tienda", tienda).execute()
        print(f"[Supabase] Productos del {fecha} eliminados")
        return True
    except Exception as e:
        print(f"[Supabase] Error al eliminar: {e}")
        return False
