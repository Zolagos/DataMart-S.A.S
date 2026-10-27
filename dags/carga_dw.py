import csv
import io

from sqlalchemy import text

TABLAS = "dw.revenue_producto_dia, dw.fact_ventas, dw.fact_devoluciones, dw.dim_producto, audit.rechazos"

SQL_REVENUE_NETO = """
INSERT INTO dw.revenue_producto_dia
WITH v AS (SELECT fecha_utc::date AS fecha, codigo, sum(cantidad) AS unidades, sum(revenue_bruto) AS bruto
           FROM dw.fact_ventas GROUP BY 1, 2),
     d AS (SELECT fecha_utc::date AS fecha, codigo, sum(-cantidad) AS unidades, sum(monto_devuelto) AS monto
           FROM dw.fact_devoluciones WHERE tipo = 'devolucion' GROUP BY 1, 2)
SELECT coalesce(v.fecha, d.fecha), coalesce(v.codigo, d.codigo),
       coalesce(v.unidades, 0), coalesce(v.bruto, 0), coalesce(d.unidades, 0), coalesce(d.monto, 0),
       coalesce(v.bruto, 0) - coalesce(d.monto, 0)
FROM v FULL OUTER JOIN d ON v.fecha = d.fecha AND v.codigo = d.codigo
"""


def copiar(tabla, conn, columnas, filas):
    """Forma rápida de insertar en PostgreSQL desde pandas (COPY en vez de un INSERT por fila).
    Es la receta de la documentación de pandas para DataFrame.to_sql(method=...)."""
    buffer = io.StringIO()
    csv.writer(buffer).writerows(filas)
    buffer.seek(0)
    nombre = f"{tabla.schema}.{tabla.name}" if tabla.schema else tabla.name
    with conn.connection.cursor() as cur:
        cur.copy_expert(f"COPY {nombre} ({', '.join(columnas)}) FROM STDIN WITH CSV", buffer)


def cargar_todo(engine, productos, ventas, devoluciones, rechazos):
    with engine.begin() as conn:                      # una transacción: todo o nada
        conn.execute(text(f"TRUNCATE {TABLAS}"))
        for df, esquema, tabla in [(productos, "dw", "dim_producto"), (ventas, "dw", "fact_ventas"),
                                   (devoluciones, "dw", "fact_devoluciones"), (rechazos, "audit", "rechazos")]:
            df.to_sql(tabla, conn, schema=esquema, if_exists="append", index=False, method=copiar)
        conn.execute(text(SQL_REVENUE_NETO))


def contar(engine):
    with engine.connect() as conn:
        return {t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar()
                for t in ("dw.dim_producto", "dw.fact_ventas", "dw.fact_devoluciones", "audit.rechazos",
                          "dw.revenue_producto_dia")}