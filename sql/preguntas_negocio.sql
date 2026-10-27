\echo '=== P1. Evolución mensual de las ventas netas (descontando devoluciones)'
SELECT to_char(fecha, 'YYYY-MM')        AS mes,
       round(sum(revenue_bruto), 2)      AS revenue_bruto,
       round(sum(monto_devuelto), 2)     AS devoluciones,
       round(sum(revenue_neto), 2)       AS revenue_neto
FROM dw.revenue_producto_dia
GROUP BY 1
ORDER BY 1;

\echo '=== P2. Categorías: revenue bruto y proporción de devoluciones'
SELECT p.categoria,
       round(sum(r.revenue_bruto), 2)                                            AS revenue_bruto,
       round(sum(r.monto_devuelto), 2)                                           AS monto_devuelto,
       round(100.0 * sum(r.monto_devuelto) / nullif(sum(r.revenue_bruto), 0), 2) AS pct_devolucion
FROM dw.revenue_producto_dia r
JOIN dw.dim_producto p USING (codigo)
GROUP BY p.categoria
ORDER BY revenue_bruto DESC;

\echo '=== P3a. Top 10 productos por revenue neto'
SELECT p.codigo, p.descripcion, round(sum(r.revenue_neto), 2) AS revenue_neto
FROM dw.revenue_producto_dia r
JOIN dw.dim_producto p USING (codigo)
GROUP BY p.codigo, p.descripcion
ORDER BY revenue_neto DESC
LIMIT 10;

\echo '=== P3b. Top 10 productos con mayor tasa de devolución (mínimo 100 unidades vendidas)'
SELECT p.codigo, p.descripcion,
       sum(r.unidades_vendidas)  AS vendidas,
       sum(r.unidades_devueltas) AS devueltas,
       round(100.0 * sum(r.unidades_devueltas) / sum(r.unidades_vendidas), 2) AS tasa_devolucion_pct
FROM dw.revenue_producto_dia r
JOIN dw.dim_producto p USING (codigo)
GROUP BY p.codigo, p.descripcion
HAVING sum(r.unidades_vendidas) >= 100
ORDER BY tasa_devolucion_pct DESC
LIMIT 10;

\echo '=== P4. Países: transacciones y ticket promedio (transacción = factura de venta)'
WITH facturas AS (
    SELECT pais, factura, sum(revenue_bruto) AS total
    FROM dw.fact_ventas
    GROUP BY pais, factura
)
SELECT pais,
       count(*)                                            AS transacciones,
       round(100.0 * count(*) / sum(count(*)) OVER (), 2)  AS pct_transacciones,
       round(avg(total), 2)                                AS ticket_promedio
FROM facturas
GROUP BY pais
ORDER BY transacciones DESC;

\echo '=== P5. Clientes identificados vs transacciones sin CustomerID'
WITH facturas AS (
    SELECT cliente_identificado, factura, sum(revenue_bruto) AS total, count(*) AS lineas
    FROM dw.fact_ventas
    GROUP BY cliente_identificado, factura
)
SELECT CASE WHEN cliente_identificado THEN 'Con CustomerID' ELSE 'Sin CustomerID' END AS grupo,
       count(*)                                                 AS facturas,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1)       AS pct_facturas,
       round(100.0 * sum(total) / sum(sum(total)) OVER (), 1)   AS pct_revenue,
       round(avg(total), 2)                                     AS ticket_promedio,
       round(avg(lineas), 1)                                    AS productos_por_factura
FROM facturas
GROUP BY cliente_identificado
ORDER BY grupo;

\echo '=== P6a. Productos sin descripción consistente (más de un texto para el mismo código)'
SELECT codigo, descripcion AS nombre_canonico, variantes_escritura, variantes_descripcion
FROM dw.dim_producto
WHERE variantes_descripcion > 1
ORDER BY variantes_descripcion DESC, codigo
LIMIT 20;

\echo '=== P6b. Códigos únicos de producto en total y cuántos tienen descripción inconsistente'
SELECT count(*)                                                  AS codigos_unicos,
       count(*) FILTER (WHERE variantes_escritura > 1)           AS con_varias_escrituras,
       count(*) FILTER (WHERE variantes_descripcion > 1)         AS con_textos_distintos
FROM dw.dim_producto;

\echo '=== P7. Base para la recomendación: productos que más dinero devuelven'
SELECT p.codigo, p.descripcion, p.categoria,
       round(sum(r.monto_devuelto), 2)                                               AS monto_devuelto,
       round(100.0 * sum(r.monto_devuelto) / sum(sum(r.monto_devuelto)) OVER (), 2) AS pct_del_total_devuelto,
       round(100.0 * sum(r.monto_devuelto) / nullif(sum(r.revenue_bruto), 0), 2)   AS pct_devolucion
FROM dw.revenue_producto_dia r
JOIN dw.dim_producto p USING (codigo)
GROUP BY p.codigo, p.descripcion, p.categoria
ORDER BY monto_devuelto DESC
LIMIT 10;

\echo '=== Validación: rechazos por fuente y motivo'
SELECT fuente, motivo, count(*) AS registros
FROM audit.rechazos
GROUP BY fuente, motivo
ORDER BY fuente, registros DESC;