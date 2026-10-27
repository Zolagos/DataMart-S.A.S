from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

import carga_dw
import transformaciones as tf

TRABAJO = Path("/opt/airflow/data/trabajo")


def carpeta(ds):
    ruta = TRABAJO / ds
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def extraer(fuente, ds):
    ruta = Path(Variable.get("datamart_ruta_datos")) / Variable.get(f"datamart_archivo_{fuente}")
    df = tf.leer_csv(ruta, fuente)
    df.to_parquet(carpeta(ds) / f"{fuente}.parquet", index=False)
    print(f"{fuente}: {len(df)} filas leídas de {ruta.name}")
    return len(df)


def transformar(ds):
    zona = Variable.get("datamart_zona_horaria")
    validas, rechazos, resumen = {}, [], {}
    for fuente in ("ventas_diarias", "historial"):
        crudo = pd.read_parquet(carpeta(ds) / f"{fuente}.parquet")
        formato = Variable.get(f"datamart_formato_fecha_{fuente}")
        validas[fuente], r, resumen[fuente] = tf.limpiar_fuente(crudo, formato, zona)
        rechazos.append(r)

    lineas, duplicadas = tf.quitar_duplicados_entre_fuentes(validas["ventas_diarias"], validas["historial"])
    resumen["ventas_diarias"]["duplicadas_entre_fuentes"] = 0
    resumen["historial"]["duplicadas_entre_fuentes"] = duplicadas
    for fuente in resumen:
        resumen[fuente]["validas"] = int((lineas["fuente"] == fuente).sum())

    lineas["tipo"] = tf.clasificar(lineas)
    lineas["cliente_identificado"] = lineas["cliente"].notna()
    productos = tf.construir_productos(lineas)

    columnas = ["fuente", "fila_origen", "factura", "fecha_utc", "codigo", "cliente", "cliente_identificado",
                "pais", "cantidad", "precio"]
    ventas = lineas.loc[lineas["tipo"] == "venta", columnas].copy()
    ventas["revenue_bruto"] = ventas["cantidad"] * ventas["precio"]
    devoluciones = lineas.loc[lineas["tipo"] != "venta", columnas + ["tipo"]].copy()
    devoluciones["monto_devuelto"] = -devoluciones["cantidad"] * devoluciones["precio"]

    for nombre, df in [("productos", productos), ("ventas", ventas), ("devoluciones", devoluciones),
                       ("rechazos", pd.concat(rechazos, ignore_index=True))]:
        df.to_parquet(carpeta(ds) / f"{nombre}.parquet", index=False)
    resumen["totales"] = {"productos": len(productos), "ventas": len(ventas), "devoluciones": len(devoluciones),
                          "rechazos": sum(r["rechazadas"] for r in list(resumen.values())[:2])}
    print(resumen)
    return resumen                                 


def validar_calidad(ti):
    resumen = ti.xcom_pull(task_ids="transformar")
    umbral = float(Variable.get("datamart_umbral_rechazo"))
    errores = []
    for fuente in ("ventas_diarias", "historial"):
        r = resumen[fuente]
        suma = r["duplicadas_mismo_archivo"] + r["rechazadas"] + r["duplicadas_entre_fuentes"] + r["validas"]
        if suma != r["leidas"]:
            errores.append(f"{fuente}: leídas {r['leidas']} pero suman {suma}")
        tasa = r["rechazadas"] / r["leidas"]
        print(f"{fuente}: tasa de rechazo {tasa:.2%} (umbral {umbral:.0%})")
        if tasa > umbral:
            errores.append(f"{fuente}: tasa de rechazo {tasa:.2%} supera el umbral {umbral:.0%}")
    if resumen["totales"]["ventas"] == 0:
        errores.append("no quedó ninguna venta")
    if errores:
        raise ValueError("Calidad NO aprobada: " + "; ".join(errores))
    print("Calidad aprobada")


def cargar_repositorio(ds):
    engine = PostgresHook(postgres_conn_id="datamart_dw").get_sqlalchemy_engine()
    leer = lambda nombre: pd.read_parquet(carpeta(ds) / f"{nombre}.parquet")   # noqa: E731
    carga_dw.cargar_todo(engine, leer("productos"), leer("ventas"), leer("devoluciones"), leer("rechazos"))


def verificar_carga(ti):
    totales = ti.xcom_pull(task_ids="transformar")["totales"]
    en_base = carga_dw.contar(PostgresHook(postgres_conn_id="datamart_dw").get_sqlalchemy_engine())
    print("en la base:", en_base)
    esperado = {"dw.dim_producto": totales["productos"], "dw.fact_ventas": totales["ventas"],
                "dw.fact_devoluciones": totales["devoluciones"], "audit.rechazos": totales["rechazos"]}
    distintos = {t: (n, en_base[t]) for t, n in esperado.items() if en_base[t] != n}
    if distintos:
        raise ValueError(f"La base no cuadra con la transformación (esperado, en base): {distintos}")
    print("Carga verificada: la base cuadra con la transformación")


with DAG(
    dag_id="datamart_etl_diario",
    start_date=datetime(2026, 10, 1),
    schedule="@daily",
    catchup=False,                 # no rellena días pasados: cada run procesa los archivos completos
    max_active_runs=1,             # nunca dos cargas a la vez sobre las mismas tablas
    default_args={"retries": 3, "retry_delay": timedelta(minutes=1), "retry_exponential_backoff": True},
    tags=["datamart"],
) as dag:
    t_ventas = PythonOperator(task_id="extraer_ventas_diarias", python_callable=extraer,
                              op_kwargs={"fuente": "ventas_diarias"})
    t_historial = PythonOperator(task_id="extraer_historial", python_callable=extraer,
                                 op_kwargs={"fuente": "historial"})
    t_transformar = PythonOperator(task_id="transformar", python_callable=transformar)
    t_validar = PythonOperator(task_id="validar_calidad", python_callable=validar_calidad,
                               retries=0)          # un dato malo no se arregla reintentando
    t_cargar = PythonOperator(task_id="cargar_repositorio", python_callable=cargar_repositorio)
    t_verificar = PythonOperator(task_id="verificar_carga", python_callable=verificar_carga)

    [t_ventas, t_historial] >> t_transformar >> t_validar >> t_cargar >> t_verificar