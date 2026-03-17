"""
categorias.py
Obtiene el árbol de categorías de Supermercados DIA Argentina.
Devuelve una lista de dicts con {nombre, category_id, path}
"""

import requests

BASE_URL = "https://diaonline.supermercadosdia.com.ar"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

def get_categorias() -> list[dict]:
    """
    Llama al endpoint de categorías de VTEX y devuelve la lista plana
    de todas las subcategorías (las que tienen productos).
    """
    url = f"{BASE_URL}/api/catalog_system/pub/category/tree/3"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    tree = resp.json()

    categorias = []
    for top in tree:
        _extraer_hojas(top, categorias)

    return categorias


def _extraer_hojas(nodo: dict, resultado: list, path: str = ""):
    """Recorre el árbol recursivamente y extrae las categorías hoja."""
    nombre = nodo.get("name", "")
    cat_id = nodo.get("id")
    path_actual = f"{path}/{nombre}" if path else nombre
    hijos = nodo.get("children", [])

    if not hijos:
        # Es una hoja → tiene productos directos
        resultado.append({
            "nombre": nombre,
            "category_id": cat_id,
            "path": path_actual,
        })
    else:
        for hijo in hijos:
            _extraer_hojas(hijo, resultado, path_actual)


if __name__ == "__main__":
    cats = get_categorias()
    print(f"Total categorías: {len(cats)}")
    for c in cats:
        print(f"  [{c['category_id']}] {c['path']}")
