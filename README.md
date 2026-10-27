# DataMart S.A.S. — Pipeline ETL con Apache Airflow y PostgreSQL

Dos CSV de Kaggle → limpieza con pandas → repositorio analítico en PostgreSQL, orquestado por
Apache Airflow 2.10. Todo corre en Docker.

- Decisiones técnicas: [docs/DECISIONES_TECNICAS.md](docs/DECISIONES_TECNICAS.md)
- Diagrama del modelo: [docs/modelo_datos.png](docs/modelo_datos.png) ([DBML para dbdiagram.io](docs/modelo_datos.dbml))
- Exploración de las fuentes: [docs/exploracion.md](docs/exploracion.md)
- Consultas de negocio: [sql/preguntas_negocio.sql](sql/preguntas_negocio.sql)

## Requisitos
Docker Desktop y Git.

## Puesta en marcha (menos de 10 minutos)

**1. Clonar el repositorio**
```bash
git clone <url-del-repositorio>
cd <carpeta-del-repositorio>
```

**2. Crear el `.env`** desde la plantilla:
```bash
cp .env.example .env            # en PowerShell: Copy-Item .env.example .env
```
Cambia las contraseñas y pega en `AIRFLOW_FERNET_KEY` la llave que genera este comando:
```bash
python -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

**3. Levantar todo** (la primera vez descarga las imágenes: 3-8 minutos):
```bash
docker compose up -d
```

**4. Comprobar que arrancó**
```bash
docker compose ps -a
```
`airflow-init` debe decir `Exited (0)` y los otros cuatro servicios `Up`.

**5. Validar la Connection y las Variables** (se crean solas al iniciar):
```bash
docker compose exec airflow-scheduler airflow connections test datamart_dw
docker compose exec airflow-scheduler airflow variables list
```
El primero responde `Connection success!`. El segundo lista las 7 variables `datamart_*`.
También puedes verlas en http://localhost:8080 (usuario y clave del `.env`): **Admin → Connections** y **Admin → Variables**.

**6. Ejecutar el pipeline.** El DAG `datamart_etl_diario` queda activo y hace su primera ejecución solo.
Para lanzarlo a mano:
```bash
docker compose exec airflow-scheduler airflow dags trigger datamart_etl_diario
```
En la interfaz: **DAGs → datamart_etl_diario → Grid**. Las 6 tareas deben quedar en verde (1-3 minutos).

**7. Verificar que los datos llegaron**
```bash
docker compose exec postgres-dw psql -U datamart -d datamart_dw -c "SELECT count(*) AS ventas, round(sum(revenue_bruto), 2) AS revenue_bruto FROM dw.fact_ventas;"
docker compose exec postgres-dw psql -U datamart -d datamart_dw -f /sql/preguntas_negocio.sql
```
El segundo comando responde todas las preguntas de negocio.

## Otros comandos
| Qué | Comando |
|---|---|
| Explorar las fuentes (genera `docs/exploracion.md`) | `docker compose exec airflow-scheduler python /opt/airflow/scripts/explorar_fuentes.py` |
| Apagar (conserva los datos) | `docker compose down` |
| Borrar todo y empezar de cero | `docker compose down -v` |

## Datos
En `data/raw/`, tal como se descargan de Kaggle:
- `data.csv` — https://www.kaggle.com/datasets/carrie1/ecommerce-data
- `Sales Transaction v.4a.csv` — https://www.kaggle.com/datasets/gabrielramos87/an-online-shop-business

## Estructura
```
dags/datamart_etl_diario.py   el DAG: tareas y orden
dags/transformaciones.py      reglas de limpieza con pandas
dags/carga_dw.py              carga en PostgreSQL (una transacción)
sql/01_crear_tablas.sql       tablas del repositorio analítico (se crean al iniciar)
sql/preguntas_negocio.sql     consultas de las preguntas de negocio
config/variables.json         Airflow Variables
docker/                       Dockerfile de Airflow y script de arranque
scripts/explorar_fuentes.py   exploración de calidad de las fuentes
docs/                         decisiones, diagrama y exploración
```
