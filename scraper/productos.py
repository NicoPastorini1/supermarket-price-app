"""
productos.py
Scraping de productos de DIA usando sitemap y BeautifulSoup.
Genera JSON y CSV con fecha.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import os
import base64
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import time as time_module

BASE_URL = "https://diaonline.supermercadosdia.com.ar"
GRAPHQL_URL = "https://diaonline.supermercadosdia.com.ar/_v/segment/graphql/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
PAGE_SIZE = 50
MAX_WORKERS = 10
import os
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


def obtener_categoria(product_url):
    """Obtiene la categoría del producto desde GraphQL."""
    match = re.search(r'-(\d+)/p$', product_url)
    if not match:
        return ""
    
    product_id = match.group(1)
    
    slug_match = re.search(r'/([^/]+)/p$', product_url)
    slug = slug_match.group(1) if slug_match else ""
    
    variables = {
        "slug": slug,
        "identifier": {"field": "id", "value": product_id}
    }
    
    extensions = {
        "persistedQuery": {
            "version": 1,
            "sha256Hash": "53499216049dd492b152bf436ef58faab80f8894796fbf9ee596b5ba3e5ef505",
            "sender": "vtex.store-resources@0.x",
            "provider": "vtex.search-graphql@0.x"
        },
        "variables": base64.b64encode(json.dumps(variables).encode()).decode()
    }
    
    params = {
        "workspace": "master",
        "maxAge": "short",
        "appsEtag": "remove",
        "domain": "store",
        "locale": "es-AR",
        "__bindingId": "39bdf81c-0d1f-4400-9510-96377195dd22",
        "operationName": "ProductCategoryTree",
        "extensions": json.dumps(extensions)
    }
    
    try:
        response = requests.get(GRAPHQL_URL, params=params, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            category_tree = data.get("data", {}).get("product", {}).get("categoryTree", [])
            if category_tree:
                return category_tree[0].get("name", "")
    except:
        pass
    
    return ""


def limpiar_precio(precio_texto):
    """Limpia texto de precio y convierte a float."""
    if not precio_texto:
        return 0.0
    precio_limpio = precio_texto.replace('$', '').replace('.', '').replace(',', '.').strip()
    try:
        return float(precio_limpio)
    except ValueError:
        return 0.0


def extraer_producto_detalle(product_url, tienda="dia"):
    """Extrae datos de una página de producto individual."""
    try:
        response = requests.get(product_url, headers=HEADERS, timeout=20)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        fecha = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        nombre = None
        precio = 0.0
        marca = ""
        imagen = None
        
        title = soup.find('title')
        if title:
            nombre = title.text.strip().split('|')[0].strip()
        
        for script in soup.find_all('script'):
            script_text = script.string or ""
            if '"productName"' in script_text or '"Price"' in script_text:
                name_match = re.search(r'"productName"\s*:\s*"([^"]+)"', script_text)
                if name_match:
                    nombre = name_match.group(1)
                
                price_match = re.search(r'"Price"\s*:\s*(\d+\.?\d*)', script_text)
                if price_match:
                    precio = float(price_match.group(1))
                
                brand_match = re.search(r'"brand"\s*:\s*"([^"]+)"', script_text)
                if brand_match:
                    marca = brand_match.group(1)
                
                break
        
        img_tag = soup.find('img', {'data-testid': 'product-image'})
        if not img_tag:
            img_tag = soup.find('img', {'class': lambda x: x and 'image' in x})
        if not img_tag:
            img_tag = soup.find('img')
        if img_tag:
            imagen = img_tag.get('src') or img_tag.get('data-src')
        
        categoria = obtener_categoria(product_url)
        
        if nombre and precio > 0:
            return {
                "productId": nombre.lower().replace(' ', '-')[:30],
                "nombre": nombre,
                "marca": marca,
                "categoria": categoria,
                "subcategoria": "",
                "tienda": tienda,
                "precio": precio,
                "precio_por_unidad": None,
                "unidad_medida": None,
                "iva": None,
                "stock": 1,
                "disponible": True,
                "imagen": imagen,
                "clusters": [],
                "fecha_extraccion": fecha,
                "url": product_url
            }
        
        return None
        
    except Exception as e:
        return None


def extraer_productos_de_pagina(page_url, categoria, subcategoria, tienda="dia", debug=False):
    """Extrae productos de una página usando BeautifulSoup."""
    productos = []
    try:
        response = requests.get(page_url, headers=HEADERS, timeout=20)
        if response.status_code != 200:
            return productos

        soup = BeautifulSoup(response.text, 'html.parser')
        
        if debug:
            print(f"\n=== DEBUG: {page_url} ===")
            print(f"Total divs: {len(soup.find_all('div'))}")
            print(f"HTML sample: {str(soup)[:2000]}")
            return productos

        productos_divs = soup.find_all('div', class_='diaio-search-result-0-x-galleryItem')

        fecha = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        for producto_div in productos_divs:
            try:
                nombre_elem = producto_div.find(
                    'span',
                    class_='vtex-product-summary-2-x-productBrand vtex-product-summary-2-x-brandName t-body'
                )
                precio_elem = producto_div.find(
                    'span',
                    class_='diaio-store-5-x-sellingPriceValue'
                )

                if nombre_elem and precio_elem:
                    nombre = nombre_elem.text.strip()
                    precio = limpiar_precio(precio_elem.text.strip())

                    img_elem = producto_div.find('img')
                    imagen = img_elem.get('src') if img_elem else None

                    productos.append({
                        "productId": f"{nombre.lower().replace(' ', '-')[:20]}_{categoria}",
                        "nombre": nombre,
                        "marca": "",
                        "categoria": categoria,
                        "subcategoria": subcategoria,
                        "tienda": tienda,
                        "precio": precio,
                        "precio_por_unidad": None,
                        "unidad_medida": None,
                        "iva": None,
                        "stock": 1,
                        "disponible": True,
                        "imagen": imagen,
                        "clusters": [],
                        "fecha_extraccion": fecha,
                    })
            except Exception:
                pass
    except Exception:
        pass
    return productos


def get_productos_categoria(category_id: int = None, category_path: str = "", tienda: str = "dia") -> tuple[list[dict], dict]:
    """
    Obtiene todos los productos usando el sitemap y scraping con BeautifulSoup.
    Retorna: (productos, metadata)
    """
    inicio = time_module.time()
    productos = []
    paginas_procesadas = 0
    categorias_encontradas = 0
    duracion = 0.0
    
    sitemap_urls = [
        f"https://diaonline.supermercadosdia.com.ar/sitemap/product-{i}.xml" for i in range(6)
    ]

    all_locs = []
    for sitemap_url in sitemap_urls:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌐 Obteniendo: {sitemap_url}")
            response = requests.get(sitemap_url, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'xml')
                locs = soup.find_all('loc')
                all_locs.extend([loc.text.strip() for loc in locs])
                print(f"  → {len(locs)} URLs encontradas")
            else:
                print(f"  [!] No disponible: {response.status_code}")
        except Exception as e:
            print(f"  [!] Error: {e}")
            continue

    if not all_locs:
        print(f"  [!] No se encontraron URLs en los sitemaps")
        return productos, {"duracion": 0.0, "categorias": 0, "paginas": 0}

    tareas = []
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📋 Obteniendo URLs de productos ({len(all_locs)} encontradas)...")

    for loc in all_locs[:2000]:
        url_producto = loc
        if url_producto.endswith('/p'):
            from urllib.parse import urlparse, unquote
            path = urlparse(url_producto).path
            slug = path.strip('/').split('/')[0]
            nombre = unquote(slug).replace('-', ' ').title()
            nombre = nombre.replace('Ml', 'ml').replace('Gr', 'g').replace('Cm', 'cm')
            tareas.append((url_producto, nombre))

    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏳ {len(tareas)} productos a procesar...")

    def procesar_producto(args):
        url, nombre = args
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            precio = 0.0
            imagen = None
            
            for script in soup.find_all('script'):
                script_text = script.string or ""
                import re
                price_match = re.search(r'"Price"\s*:\s*(\d+\.?\d*)', script_text)
                if price_match:
                    precio = float(price_match.group(1))
                
                if not imagen:
                    img_match = re.search(r'"image"\s*:\s*"([^"]*ardiaprod[^"]+)"', script_text)
                    if img_match:
                        imagen = img_match.group(1)
                        if imagen and not imagen.startswith('http'):
                            imagen = 'https:' + imagen
            
            if not imagen:
                img_tag = soup.find('img', class_='vtex-store-components-3-x-productImageTag--main')
                if img_tag:
                    imagen = img_tag.get('src') or img_tag.get('data-src')
                else:
                    imgs = soup.find_all('img', class_=lambda x: x and 'productImageTag' in x)
                    for img in imgs[:1]:
                        src = img.get('src') or img.get('data-src')
                        if src and 'ids/' in src and 'footer' not in src and 'logo' not in src.lower():
                            imagen = src
                            break
                
                if imagen and not imagen.startswith('http'):
                    imagen = 'https:' + imagen
            
            return {
                "productId": f"{nombre.lower().replace(' ', '-')[:30]}",
                "nombre": nombre,
                "marca": "",
                "categoria": "",
                "subcategoria": "",
                "tienda": "dia",
                "precio": precio,
                "precio_por_unidad": None,
                "unidad_medida": None,
                "iva": None,
                "stock": 1,
                "disponible": True,
                "imagen": imagen,
                "clusters": [],
                "fecha_extraccion": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "url": url
            }
        except:
            return None

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(procesar_producto, args): args
                for args in tareas
            }

            count = 0
            for future in as_completed(futures):
                result = future.result()
                if result:
                    productos.append(result)
                    if len(productos) == 1:
                        print(f"  → Primer producto: {result['nombre']} - ${result['precio']}")
                count += 1
                if count % 50 == 0:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📦 Procesados {count}/{len(tareas)} productos...")

        duracion = time_module.time() - inicio
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Scraping completado: {len(productos)} productos en {duracion:.1f}s")

    except Exception as e:
        duracion = time_module.time() - inicio
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error general: {e}")
    
    metadata = {
        "duracion": duracion,
        "categorias": categorias_encontradas,
        "paginas": paginas_procesadas
    }
    
    return productos, metadata


def guardar_productos(productos: list[dict], output_dir: str = OUTPUT_DIR):
    """Guarda los productos en JSON con fecha."""
    if not productos:
        return None, None

    os.makedirs(output_dir, exist_ok=True)
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    df = pd.DataFrame(productos)
    df = df.drop_duplicates(subset=['nombre', 'categoria', 'subcategoria'])

    json_path = os.path.join(output_dir, f"productos_{fecha_hoy}.json")

    resultado = {
        "tienda": "dia",
        "fecha_extraccion": fecha_hoy,
        "total_productos": len(df),
        "productos": df.to_dict("records"),
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 💾 JSON guardado: {json_path}")

    return json_path, None


if __name__ == "__main__":
    prods, metadata = get_productos_categoria(tienda="dia")
    print(f"Productos encontrados: {len(prods)}")
    json_path, _ = guardar_productos(prods)
    if json_path:
        print(f"JSON: {json_path}")
