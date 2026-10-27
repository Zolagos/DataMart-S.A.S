# Decisiones técnicas — Pipeline ETL DataMart S.A.S.

Las cifras salen de `docs/exploracion.md` (lo genera `scripts/explorar_fuentes.py`) y de
`docs/resultados_consultas.txt` (salida de `sql/preguntas_negocio.sql`), con los archivos reales de Kaggle.

**Resumen de una ejecución** (≈25 s): `data.csv` 541.909 filas = 5.268 repetidas + 4.145 rechazadas + 532.496 válidas.
Historial 536.350 filas = 5.200 repetidas + 0 rechazadas + 528.613 duplicadas de `data.csv` + 2.537 válidas.
Resultado: 525.007 ventas, 10.026 devoluciones/ajustes, 3.912 productos, revenue bruto £10.527.388,86 y neto £10.031.343,02.

## 1. Arquitectura

| Pieza | Qué es | Por qué |
|---|---|---|
| `postgres-airflow` | PostgreSQL solo para los metadatos de Airflow | Distinta del repositorio analítico |
| `postgres-dw` | PostgreSQL del repositorio analítico | Las tablas se crean al iniciar con `sql/01_crear_tablas.sql` |
| `airflow-init` | Corre una vez al levantar | Crea la base de Airflow, el admin, la Connection y las Variables (`docker/init_airflow.sh`) |
| `airflow-webserver` / `airflow-scheduler` | Airflow 2.10.5 con `LocalExecutor` | Es la arquitectura: webserver + scheduler + admin |
| Secretos | Solo en `.env`, que no se sube a Git | Ninguna contraseña aparece en el código. La `FERNET_KEY` cifra la contraseña guardada en la Connection |

Todo se levanta con `docker compose up -d`.

**Connection**: `datamart_dw` (PostgreSQL destino). El DAG la usa con `PostgresHook("datamart_dw")`.

**Variables** (`config/variables.json`, se importan al iniciar): `datamart_ruta_datos`,
`datamart_archivo_ventas_diarias`, `datamart_archivo_historial`, `datamart_formato_fecha_ventas_diarias`,
`datamart_formato_fecha_historial`, `datamart_zona_horaria` y `datamart_umbral_rechazo`. Son parámetros
operativos: se cambian en la interfaz (Admin → Variables) sin tocar el código.

## 2. El DAG `datamart_etl_diario`

```
extraer_ventas_diarias ─┐
                        ├─> transformar -> validar_calidad -> cargar_repositorio -> verificar_carga
extraer_historial ──────┘
```
- Programación diaria (`@daily`), sin `catchup` (cada ejecución procesa los archivos completos).
- **Reintentos**: 3 por tarea, con espera creciente (1, 2, 4 min). `validar_calidad` no reintenta, porque un dato malo no se arregla reintentando.
- Las tareas se pasan los datos como **Parquet** en `data/trabajo/<fecha>/`. Por XCom solo viajan conteos.
- `validar_calidad` detiene la carga si la conciliación no cuadra (leídas = duplicadas + rechazadas + válidas) o si una fuente supera el umbral de rechazo.
- `verificar_carga` comprueba que lo que quedó en la base es igual a lo que se transformó.

## 3. Unificación de las dos fuentes

| Concepto | `data.csv` (carrie1/ecommerce-data) | `Sales Transaction v.4a.csv` (gabrielramos87) | Nombre común |
|---|---|---|---|
| Factura | `InvoiceNo` | `TransactionNo` | `factura` |
| Código | `StockCode` | `ProductNo` | `codigo` |
| Descripción | `Description` (MAYÚSCULAS) | `ProductName` (Formato Título) | `descripcion` |
| Cantidad | `Quantity` | `Quantity` | `cantidad` |
| Fecha | `InvoiceDate` = `12/1/2010 8:26` (con hora) | `Date` = `12/9/2019` (sin hora) | `fecha` |
| Precio | `UnitPrice` | `Price` | `precio` |
| Cliente | `CustomerID` | `CustomerNo` | `cliente` |
| País | `Country` | `Country` | `pais` |

## 4. Reglas de negocio

| Regla | Cómo se aplicó |
|---|---|
| Cantidad ≤ 0 no es venta | `fact_ventas` solo tiene cantidad > 0. Cantidad ≤ 0 va a `fact_devoluciones`: con factura `C…` es `devolucion`; sin `C` es `ajuste_inventario` (daños, conteos). La base lo garantiza con `CHECK`. |
| Precio ≤ 0 en venta → log de rechazos | Precio 0 con cantidad > 0: `venta_con_precio_cero`. Precio negativo: `precio_negativo`. Van a `audit.rechazos` con la fuente, la línea del archivo y los valores originales. |
| Fechas en UTC | `data.csv` trae la hora de la tienda en Londres: se localiza en `Europe/London` y se pasa a UTC (en verano resta 1 hora). El historial solo trae fecha: no hay hora que convertir, así que se guarda ese día a las 00:00 UTC. Pasarla por Londres la movería al día anterior en verano. |
| Códigos en mayúsculas y sin espacios | `' 85123a '` → `'85123A'` antes de cualquier cruce. |
| Revenue bruto y neto | `revenue_bruto = cantidad × precio` en cada venta. `revenue_producto_dia.revenue_neto` = bruto − monto devuelto **del mismo código el mismo día**. Los ajustes de inventario no restan dinero: no son dinero devuelto a un cliente. |

Otras decisiones:
- **Filas repetidas exactas** dentro de un archivo: se toman como carga doble y se quitan (se cuentan, no se rechazan).
- **Códigos que no siguen el patrón** del catálogo (5 dígitos y hasta 2 letras): `POST`, `DOT`, `M`, `BANK CHARGES`… son portes y comisiones, no productos. Se rechazan con motivo `codigo_no_es_producto`, para no inflar el revenue de productos. Quedan en el log por si finanzas los necesita.
- **Países abreviados**: `EIRE` → `Ireland`, `RSA` → `South Africa`, `USA` → `United States`.
- **Categoría**: no se implementó el API. Se asigna con **palabras clave** de la descripción (`CATEGORIAS` en `dags/transformaciones.py`), revisadas en orden: `T-LIGHT HOLDER` es Hogar aunque contenga `LIGHT`. Lo que no coincide queda en "Otros".

## 5. Casos ambiguos

**a) Transacciones sin CustomerID → se incluyen.** Son ventas reales: 135.080 líneas de `data.csv` (24,9 %) no tienen cliente, y excluirlas subestimaría el revenue. Quedan con `cliente = NULL` y `cliente_identificado = false`. **Impacto** (P5): son solo el 6,8 % de las facturas, pero el **14,3 % del revenue**. Su ticket promedio es £1.100, frente a £479 de los identificados, con 96 productos por factura frente a 21. Parecen compras grandes registradas a mano o de mayoristas; excluirlas habría borrado una de cada siete libras vendidas. No sirven para análisis por cliente (recurrencia, fidelidad), pero sí para revenue, productos y países.
Dato de la exploración: el historial **sí** trae cliente en 130.926 de esas líneas (los rellenó). Como gana `data.csv`, se respeta el dato original: sin cliente.

**b) Nombre canónico → la escritura más frecuente.** Se normaliza (MAYÚSCULAS, sin espacios de sobra) y gana el texto que más se repite para ese código, contando solo líneas con precio > 0. Las notas de los ajustes (`damaged`, `?`) no son nombres. En empate, orden alfabético. `variantes_escritura` y `variantes_descripcion` guardan cuántas versiones había (pregunta P6).

**c) Duplicados entre fuentes → clave compuesta `factura + código + cantidad`; gana `data.csv`.** La exploración muestra que las fechas **no se solapan** (`data.csv` de 2010-12 a 2011-12; historial de 2018-12 a 2019-12). Aun así, 23.190 de las 23.204 facturas del historial también están en `data.csv`:

| Clave de comparación | Filas del historial que coinciden |
|---|---|
| factura + código + cantidad | **534.420 (99,6 %)** |
| ... + cliente | 403.494 (75,2 %): el historial rellenó clientes vacíos |
| ... + fecha | 0 (0 %): las fechas están corridas 8 años |

Es decir: el historial es **la misma operación** con la fecha corrida 8 años, otros precios y clientes inventados donde faltaban. Cargar ambos contaría dos veces casi todas las ventas. Por eso la clave **no** lleva fecha, precio ni cliente. Gana `data.csv` porque trae la hora, el precio y el cliente originales. Las 2.537 filas del historial sin pareja sí se cargan, y son las ventas de 2018-2019 que aparecen en P1. Si una factura repite la misma clave, se emparejan por orden de aparición (1.ª con 1.ª, 2.ª con 2.ª), para no borrar líneas legítimas.

## 6. Modelo del repositorio analítico

Diagrama: `docs/modelo_datos.png` (también `docs/modelo_datos.dbml` para dbdiagram.io).

- **`dim_producto`**: un registro por código, con el nombre canónico y la categoría.
- **`fact_ventas`** y **`fact_devoluciones`**: una fila por línea de factura, **separadas** como pide la regla de negocio. La llave `(fuente, fila_origen)` permite rastrear cualquier dato hasta su línea en el CSV.
- **`revenue_producto_dia`**: el neto por producto y día ya calculado. Responde P1, P2, P3 y P7 con una consulta simple.
- **`audit.rechazos`**: el log que pide la prueba: motivo, fuente y valores originales.
- País y cliente quedan como columnas de los hechos, sin tablas aparte: las preguntas solo agrupan por ellos y no tienen más atributos. Eso mantiene el modelo simple.

## 7. Idempotencia

Cada ejecución procesa los archivos completos y `cargar_repositorio` reemplaza el contenido de las tablas en **una sola transacción**: `TRUNCATE` de las tablas → inserción de las filas nuevas → cálculo del neto → `COMMIT`. Si algo falla, PostgreSQL hace `ROLLBACK` y quedan intactos los datos de la carga anterior. Con los mismos archivos, el resultado es exactamente el mismo: se comprobó comparando una huella `md5` de cada tabla antes y después de correr el DAG dos veces. `max_active_runs=1` evita dos cargas al mismo tiempo.

## 8. Pendientes y cómo los resolvería
- **API de catálogo** (opcional en la prueba): un servicio FastAPI en el compose con `/productos?page=` y `/productos/{codigo}`. Una tarea `extraer_catalogo` lo consumiría y usaría su categoría, dejando las palabras clave como plan B.
- **Carga incremental** por día en lugar de reemplazar todo, cuando los archivos lleguen separados por fecha.
- **Moneda**: tabla de tasas de cambio si se suman Colombia, México y Perú.

## 9. Recomendación al equipo de producto

**Poner un control de aprobación a los pedidos de más de 10.000 unidades por línea antes de facturarlos.**

- **Evidencia** (P7 y P3b): de £496.045,84 devueltos en total, **£245.949,24 (49,6 %) corresponden a solo dos productos, y casi todo es un único pedido de cada uno**. Son el `23843 PAPER CRAFT, LITTLE BIRDIE` (80.995 unidades, factura 581483 del 9-dic-2011, devuelta 12 minutos después en la C581484) y el `23166 MEDIUM CERAMIC TOP STORAGE JAR` (74.215 unidades, factura 541431 del 18-ene-2011, devuelta 16 minutos después). Ambos son errores de digitación facturados y anulados.
- **Impacto**: solo 3 líneas de venta en todo el periodo superan 10.000 unidades, así que el control casi no afecta la operación normal. Esos dos errores inflan la tasa de devolución de **Papelería** (18,3 %, la más alta en P2) y de Hogar, y distorsionan los reportes mensuales: diciembre de 2011 muestra £174.091 en devoluciones.
- **Cómo medirlo**: revisar mensualmente con P1 y P2 la tasa de devolución por categoría. Sin esos dos errores, la tasa global pasaría de 4,71 % a ≈2,4 %.
- **Segunda prioridad**: productos con devolución alta y recurrente, no por un único error. Por ejemplo, `21108 FAIRY CAKE FLANNEL` (36,5 % de devolución) y `23113 PANTRY CHOPPING BOARD` (82 %): revisar su calidad o su descripción en la tienda.