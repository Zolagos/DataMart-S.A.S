import sys
from pathlib import Path

import pandas as pd
from airflow.models import Variable

sys.path.insert(0, "/opt/airflow/dags")
import transformaciones as tf  

lineas_md = ["# Exploración de las fuentes (datos sin limpiar)\n"]


def mostrar(texto=""):
    print(texto)
    lineas_md.append(texto)


datos = {}
for fuente in ("ventas_diarias", "historial"):
    ruta = Path(Variable.get("datamart_ruta_datos")) / Variable.get(f"datamart_archivo_{fuente}")
    df = tf.leer_csv(ruta, fuente)
    cantidad = pd.to_numeric(df["cantidad"], errors="coerce")
    precio = pd.to_numeric(df["precio"], errors="coerce")
    fecha = pd.to_datetime(df["fecha"], format=Variable.get(f"datamart_formato_fecha_{fuente}"), errors="coerce")
    codigo = df["codigo"].str.upper().str.replace(" ", "", regex=False)
    no_producto = codigo[~codigo.fillna("").str.match(tf.PATRON_PRODUCTO)]
    desc = df.dropna(subset=["descripcion"]).assign(codigo=codigo,
                                                    normalizada=lambda d: d["descripcion"].str.upper().str.split().str.join(" "))
    datos[fuente] = df.assign(codigo=codigo, cantidad=cantidad, fecha_dt=fecha,
                              cliente=pd.to_numeric(df["cliente"], errors="coerce"))

    mostrar(f"\n## {fuente} — {ruta.name}\n")
    mostrar("| Revisión | Resultado |\n|---|---|")
    filas = [
        ("Filas y columnas", f"{len(df):,} filas · columnas originales: {', '.join(tf.COLUMNAS[fuente])}"),
        ("Ejemplo de fecha (texto)", df["fecha"].iloc[0]),
        ("Rango de fechas", f"{fecha.min()} a {fecha.max()}"),
        ("Fechas que no se pudieron leer", f"{fecha.isna().sum():,}"),
        ("Nulos por columna", ", ".join(f"{c}={n:,}" for c, n in df.iloc[:, 2:].isna().sum().items() if n)),
        ("Sin cliente (vacío o no numérico, ej. NA)", f"{datos[fuente]['cliente'].isna().sum():,} "
                                                     f"({datos[fuente]['cliente'].isna().mean():.1%})"),
        ("Filas repetidas exactas", f"{df.iloc[:, 2:].duplicated().sum():,}"),
        ("Cantidad mínima / máxima", f"{cantidad.min():,.0f} / {cantidad.max():,.0f}"),
        ("Cantidad <= 0 (devoluciones o ajustes)", f"{(cantidad <= 0).sum():,}"),
        ("Facturas que empiezan con C (canceladas)", f"{df['factura'].str.upper().str.startswith('C').sum():,}"),
        ("Precio mínimo / máximo", f"{precio.min():,.2f} / {precio.max():,.2f}"),
        ("Precio = 0 / precio < 0", f"{(precio == 0).sum():,} / {(precio < 0).sum():,}"),
        ("Códigos de producto distintos", f"{codigo.nunique():,}"),
        ("Filas con código que NO es producto", f"{len(no_producto):,} (ej.: {', '.join(no_producto.value_counts().head(6).index)})"),
        ("Códigos con más de una escritura", f"{(desc.groupby('codigo')['descripcion'].nunique() > 1).sum():,}"),
        ("Códigos con textos realmente distintos", f"{(desc.groupby('codigo')['normalizada'].nunique() > 1).sum():,}"),
        ("Países distintos", f"{df['pais'].nunique()}"),
    ]
    for nombre, valor in filas:
        mostrar(f"| {nombre} | {valor} |")

v, h = datos["ventas_diarias"], datos["historial"]


def coinciden(clave):
    """Filas del historial que tienen una fila igual en data.csv según la clave."""
    return h.merge(v[clave].drop_duplicates(), on=clave).shape[0]


h["dia"], v["dia"] = h["fecha_dt"].dt.date, v["fecha_dt"].dt.date
mostrar("\n## Comparación entre las dos fuentes\n")
mostrar("| Revisión | Resultado |\n|---|---|")
mostrar(f"| Facturas en común | {len(set(v['factura']) & set(h['factura'])):,} de {h['factura'].nunique():,} del historial |")
for nombre, clave in [("factura + código + cantidad", ["factura", "codigo", "cantidad"]),
                      ("... + cliente", ["factura", "codigo", "cantidad", "cliente"]),
                      ("... + fecha", ["factura", "codigo", "cantidad", "dia"])]:
    n = coinciden(clave)
    mostrar(f"| Filas del historial que coinciden con data.csv por {nombre} | {n:,} ({n / len(h):.1%}) |")
sin_cliente = h.merge(v.loc[v["cliente"].isna(), ["factura", "codigo", "cantidad"]].drop_duplicates(),
                      on=["factura", "codigo", "cantidad"])
mostrar(f"| Filas que en data.csv NO tienen cliente y en el historial SÍ | "
        f"{sin_cliente['cliente'].notna().sum():,} |")

Path("/opt/airflow/docs/exploracion.md").write_text("\n".join(lineas_md) + "\n", encoding="utf-8")
print("\n-> guardado en docs/exploracion.md")