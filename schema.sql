-- Schema para Supermarket Price Scraper
-- Ejecutar en Supabase SQL Editor

-- Crear tabla de productos
CREATE TABLE IF NOT EXISTS productos (
    id BIGSERIAL PRIMARY KEY,
    product_id VARCHAR(100),
    nombre TEXT NOT NULL,
    marca VARCHAR(100),
    categoria VARCHAR(100),
    subcategoria VARCHAR(100),
    tienda VARCHAR(50) DEFAULT 'dia',
    precio DECIMAL(10, 2),
    precio_por_unidad DECIMAL(10, 2),
    unidad_medida VARCHAR(50),
    iva DECIMAL(5, 2),
    stock INTEGER DEFAULT 1,
    disponible BOOLEAN DEFAULT true,
    imagen TEXT,
    clusters JSONB DEFAULT '[]',
    fecha_extraccion TIMESTAMP,
    url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para optimizar queries
CREATE INDEX IF NOT EXISTS idx_productos_fecha ON productos(fecha_extraccion);
CREATE INDEX IF NOT EXISTS idx_productos_tienda ON productos(tienda);
CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(categoria);
CREATE INDEX IF NOT EXISTS idx_productos_product_id ON productos(product_id);
CREATE INDEX IF NOT EXISTS idx_productos_nombre ON productos(nombre);

-- Tabla de logs de ejecución
CREATE TABLE IF NOT EXISTS logs (
    id BIGSERIAL PRIMARY KEY,
    tipo_ejecucion VARCHAR(50),
    cantidad_productos INTEGER DEFAULT 0,
    duracion_segundos DECIMAL(10, 2),
    estado VARCHAR(20),
    error_texto TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Función para actualizar fecha_extraccion si es NULL
UPDATE productos
SET fecha_extraccion = created_at
WHERE fecha_extraccion IS NULL;
