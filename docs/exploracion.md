# Exploración de las fuentes (datos sin limpiar)


## ventas_diarias — data.csv

| Revisión | Resultado |
|---|---|
| Filas y columnas | 541,909 filas · columnas originales: InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country |
| Ejemplo de fecha (texto) | 12/1/2010 8:26 |
| Rango de fechas | 2010-12-01 08:26:00 a 2011-12-09 12:50:00 |
| Fechas que no se pudieron leer | 0 |
| Nulos por columna | descripcion=1,454, cliente=135,080 |
| Sin cliente (vacío o no numérico, ej. NA) | 135,080 (24.9%) |
| Filas repetidas exactas | 5,268 |
| Cantidad mínima / máxima | -80,995 / 80,995 |
| Cantidad <= 0 (devoluciones o ajustes) | 10,624 |
| Facturas que empiezan con C (canceladas) | 9,288 |
| Precio mínimo / máximo | -11,062.06 / 38,970.00 |
| Precio = 0 / precio < 0 | 2,515 / 2 |
| Códigos de producto distintos | 3,958 |
| Filas con código que NO es producto | 2,995 (ej.: POST, DOT, M, C2, D, S) |
| Códigos con más de una escritura | 642 |
| Códigos con textos realmente distintos | 638 |
| Países distintos | 38 |

## historial — Sales Transaction v.4a.csv

| Revisión | Resultado |
|---|---|
| Filas y columnas | 536,350 filas · columnas originales: TransactionNo, ProductNo, ProductName, Quantity, Date, Price, CustomerNo, Country |
| Ejemplo de fecha (texto) | 12/9/2019 |
| Rango de fechas | 2018-12-01 00:00:00 a 2019-12-09 00:00:00 |
| Fechas que no se pudieron leer | 0 |
| Nulos por columna |  |
| Sin cliente (vacío o no numérico, ej. NA) | 55 (0.0%) |
| Filas repetidas exactas | 5,200 |
| Cantidad mínima / máxima | -80,995 / 80,995 |
| Cantidad <= 0 (devoluciones o ajustes) | 8,585 |
| Facturas que empiezan con C (canceladas) | 8,585 |
| Precio mínimo / máximo | 5.13 / 660.62 |
| Precio = 0 / precio < 0 | 0 / 0 |
| Códigos de producto distintos | 3,768 |
| Filas con código que NO es producto | 0 (ej.: ) |
| Códigos con más de una escritura | 0 |
| Códigos con textos realmente distintos | 0 |
| Países distintos | 38 |

## Comparación entre las dos fuentes

| Revisión | Resultado |
|---|---|
| Facturas en común | 23,190 de 23,204 del historial |
| Filas del historial que coinciden con data.csv por factura + código + cantidad | 534,420 (99.6%) |
| Filas del historial que coinciden con data.csv por ... + cliente | 403,494 (75.2%) |
| Filas del historial que coinciden con data.csv por ... + fecha | 0 (0.0%) |
| Filas que en data.csv NO tienen cliente y en el historial SÍ | 130,926 |
