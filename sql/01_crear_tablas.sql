CREATE SCHEMA IF NOT EXISTS dw;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS dw.dim_producto (
    codigo                text PRIMARY KEY,      
    descripcion           text NOT NULL,         
    categoria             text NOT NULL,
    variantes_escritura   integer NOT NULL,      
    variantes_descripcion integer NOT NULL      
);

CREATE TABLE IF NOT EXISTS dw.fact_ventas (
    fuente               text NOT NULL,          
    fila_origen          integer NOT NULL,       
    factura              text NOT NULL,
    fecha_utc            timestamptz NOT NULL,
    codigo               text NOT NULL REFERENCES dw.dim_producto (codigo),
    cliente              text,                   
    cliente_identificado boolean NOT NULL,
    pais                 text NOT NULL,
    cantidad             integer NOT NULL CHECK (cantidad > 0),
    precio               numeric(12, 4) NOT NULL CHECK (precio > 0),
    revenue_bruto        numeric(14, 4) NOT NULL,   -- cantidad x precio
    PRIMARY KEY (fuente, fila_origen)
);

CREATE TABLE IF NOT EXISTS dw.fact_devoluciones (
    fuente               text NOT NULL,
    fila_origen          integer NOT NULL,
    factura              text NOT NULL,
    tipo                 text NOT NULL CHECK (tipo IN ('devolucion', 'ajuste_inventario')),
    fecha_utc            timestamptz NOT NULL,
    codigo               text NOT NULL REFERENCES dw.dim_producto (codigo),
    cliente              text,
    cliente_identificado boolean NOT NULL,
    pais                 text NOT NULL,
    cantidad             integer NOT NULL CHECK (cantidad <= 0),  
    precio               numeric(12, 4) NOT NULL,
    monto_devuelto       numeric(14, 4) NOT NULL,                  
    PRIMARY KEY (fuente, fila_origen)
);

CREATE TABLE IF NOT EXISTS dw.revenue_producto_dia (
    fecha              date NOT NULL,
    codigo             text NOT NULL REFERENCES dw.dim_producto (codigo),
    unidades_vendidas  integer NOT NULL,
    revenue_bruto      numeric(16, 4) NOT NULL,
    unidades_devueltas integer NOT NULL,
    monto_devuelto     numeric(16, 4) NOT NULL,
    revenue_neto       numeric(16, 4) NOT NULL,
    PRIMARY KEY (fecha, codigo)
);

CREATE TABLE IF NOT EXISTS audit.rechazos (
    fuente      text NOT NULL,
    fila_origen integer NOT NULL,
    motivo      text NOT NULL,
    -- los valores tal cual llegaron en el archivo (texto)
    factura text, codigo text, descripcion text, cantidad text, fecha text, precio text, cliente text, pais text,
    PRIMARY KEY (fuente, fila_origen)
);