import pandas as pd

COLUMNAS = {
    "ventas_diarias": {   
        "InvoiceNo": "factura", "StockCode": "codigo", "Description": "descripcion", "Quantity": "cantidad",
        "InvoiceDate": "fecha", "UnitPrice": "precio", "CustomerID": "cliente", "Country": "pais",
    },
    "historial": {        
        "TransactionNo": "factura", "ProductNo": "codigo", "ProductName": "descripcion", "Quantity": "cantidad",
        "Date": "fecha", "Price": "precio", "CustomerNo": "cliente", "Country": "pais",
    },
}

PATRON_PRODUCTO = r"^\d{5}[A-Z]{0,2}$"

PAISES = {"EIRE": "Ireland", "RSA": "South Africa", "USA": "United States", "Unspecified": "Sin especificar"}

CATEGORIAS = [
    ("Hogar", ["T-LIGHT", "CANDLE", "LANTERN"]),
    ("Electrónica", ["LIGHT", "LIGHTS", "LED", "LAMP", "CLOCK", "RADIO", "TORCH", "CALCULATOR", "ALARM", "TIMER"]),
    ("Deportes", ["BALL", "GAME", "GAMES", "SKITTLES", "SPORT", "TENNIS", "FOOTBALL", "KITE", "DOMINOES",
                  "PLAYING CARDS", "PICNIC", "SPACEBOY", "TOY", "TOYS", "JIGSAW", "BLOCKS"]),
    ("Ropa", ["BAG", "BAGS", "PURSE", "SCARF", "GLOVES", "APRON", "HAT", "NECKLACE", "BRACELET", "EARRINGS",
              "HAIR", "SOCKS", "SLIPPERS", "UMBRELLA", "PARASOL", "JEWELLERY", "WALLET"]),
    ("Papelería", ["CARD", "CARDS", "PAPER", "NOTEBOOK", "PEN", "PENCIL", "PENCILS", "WRAP", "STICKER",
                   "STICKERS", "ENVELOPE", "TAPE", "CALENDAR", "DIARY", "TAGS", "RIBBON", "BOOK", "CHALK"]),
    ("Hogar", ["MUG", "CUP", "PLATE", "BOWL", "HOLDER", "CUSHION", "FRAME", "JAR", "TIN", "BOTTLE", "TOWEL",
               "BOX", "DOORMAT", "KITCHEN", "TEA", "CAKE", "CAKESTAND", "VASE", "HOOK", "SIGN", "BASKET",
               "BUNTING", "DECORATION", "ORNAMENT", "HEART", "GLASS", "CERAMIC", "TRAY", "SPOON", "STORAGE",
               "COASTER", "NAPKINS", "CHRISTMAS", "GARLAND", "CASES", "DISH", "JUG", "WARMER", "BLANKET"]),
]


def leer_csv(ruta, fuente):
    try:
        df = pd.read_csv(ruta, dtype=str, encoding="utf-8", keep_default_na=False)
    except UnicodeDecodeError:          
        df = pd.read_csv(ruta, dtype=str, encoding="latin-1", keep_default_na=False)
    faltan = set(COLUMNAS[fuente]) - set(df.columns)
    if faltan:
        raise ValueError(f"{ruta} no trae las columnas {faltan}. Trae: {list(df.columns)}")
    df = df[list(COLUMNAS[fuente])].rename(columns=COLUMNAS[fuente])
    df = df.apply(lambda col: col.str.strip()).replace("", None)
    df.insert(0, "fila_origen", range(2, len(df) + 2))   
    df.insert(0, "fuente", fuente)
    return df


def limpiar_fuente(df, formato_fecha, zona_horaria):
    leidas = len(df)

    repetidas = df.duplicated(subset=list(df.columns[2:]), keep="first")
    df = df[~repetidas].copy()

    out = df[["fuente", "fila_origen"]].copy()
    out["factura"] = df["factura"].str.upper()
    out["codigo"] = df["codigo"].str.upper().str.replace(" ", "", regex=False)   # regla: mayúsculas sin espacios
    out["descripcion"] = df["descripcion"]
    out["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce")
    out["precio"] = pd.to_numeric(df["precio"], errors="coerce").round(4)
    fecha_local = pd.to_datetime(df["fecha"], format=formato_fecha, errors="coerce")
    if "%H" in formato_fecha:
        
        out["fecha_utc"] = (fecha_local.dt.tz_localize(zona_horaria, ambiguous="NaT", nonexistent="NaT")
                            .dt.tz_convert("UTC"))
    else:
        out["fecha_utc"] = fecha_local.dt.tz_localize("UTC")
    out["cliente"] = pd.to_numeric(df["cliente"], errors="coerce").astype("Int64").astype(str).replace("<NA>", None)
    out["pais"] = df["pais"].replace(PAISES).fillna("Sin especificar")

    reglas = [
        ("sin_factura_o_codigo", out["factura"].isna() | out["codigo"].isna()),
        ("cantidad_invalida", out["cantidad"].isna()),
        ("precio_invalido", out["precio"].isna()),
        ("fecha_invalida", out["fecha_utc"].isna()),
        ("precio_negativo", out["precio"] < 0),
        ("venta_con_precio_cero", (out["cantidad"] > 0) & (out["precio"] == 0)),
        ("codigo_no_es_producto", ~out["codigo"].fillna("").str.match(PATRON_PRODUCTO)),
    ]
    out["motivo"] = None
    for motivo, condicion in reversed(reglas):        
        out.loc[condicion.fillna(False), "motivo"] = motivo

    rechazadas = out["motivo"].notna()
    rechazos = df[rechazadas.values].copy()
    rechazos["motivo"] = out.loc[rechazadas, "motivo"].values
    validas = out[~rechazadas].drop(columns="motivo")
    validas["cantidad"] = validas["cantidad"].astype(int)

    resumen = {
        "leidas": leidas,
        "duplicadas_mismo_archivo": int(repetidas.sum()),
        "rechazadas": int(rechazadas.sum()),
        "rechazos_por_motivo": {k: int(v) for k, v in rechazos["motivo"].value_counts().items()},
    }
    return validas, rechazos, resumen


def quitar_duplicados_entre_fuentes(ventas, historial):
    clave = ["factura", "codigo", "cantidad"]
    # 'n' numera repeticiones legítimas dentro de una factura (1.ª con 1.ª, 2.ª con 2.ª)
    ventas = ventas.assign(n=ventas.groupby(clave, dropna=False).cumcount())
    historial = historial.assign(n=historial.groupby(clave, dropna=False).cumcount())
    cruce = historial.merge(ventas[clave + ["n"]], on=clave + ["n"], how="left", indicator=True)
    es_duplicado = (cruce["_merge"] == "both").values
    unidas = pd.concat([ventas, historial[~es_duplicado]], ignore_index=True).drop(columns="n")
    return unidas, int(es_duplicado.sum())


def clasificar(df):
    tipo = pd.Series("ajuste_inventario", index=df.index)
    tipo[df["cantidad"] > 0] = "venta"
    tipo[(df["cantidad"] <= 0) & df["factura"].str.startswith("C")] = "devolucion"
    return tipo


def categoria_de(descripcion):
    palabras = set(str(descripcion).upper().replace("/", " ").split())
    texto = " " + str(descripcion).upper() + " "
    for categoria, claves in CATEGORIAS:
        for clave in claves:
            if (" " in clave and f" {clave} " in texto) or clave in palabras:
                return categoria
    return "Otros"


def construir_productos(lineas):
    d = lineas.loc[lineas["precio"] > 0, ["codigo", "descripcion"]].dropna()
    d["normalizada"] = d["descripcion"].str.upper().str.split().str.join(" ")
    conteo = d.groupby(["codigo", "normalizada"]).size().reset_index(name="veces")
    conteo = conteo.sort_values(["codigo", "veces", "normalizada"], ascending=[True, False, True])
    productos = conteo.drop_duplicates("codigo").rename(columns={"normalizada": "descripcion"})[["codigo", "descripcion"]]
    variantes = d.groupby("codigo").agg(variantes_escritura=("descripcion", "nunique"),
                                        variantes_descripcion=("normalizada", "nunique")).reset_index()
    productos = productos.merge(variantes, on="codigo")
    faltan = pd.DataFrame({"codigo": sorted(set(lineas["codigo"]) - set(productos["codigo"]))})
    faltan["descripcion"], faltan["variantes_escritura"], faltan["variantes_descripcion"] = "SIN DESCRIPCION", 0, 0
    productos = pd.concat([productos, faltan], ignore_index=True)
    productos["categoria"] = productos["descripcion"].map(categoria_de)
    return productos