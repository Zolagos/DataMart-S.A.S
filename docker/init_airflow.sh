set -e

echo "[init] 1/4 base de metadatos de Airflow"
airflow db migrate

echo "[init] 2/4 usuario administrador"
airflow users create --role Admin --username "$AIRFLOW_ADMIN_USER" --password "$AIRFLOW_ADMIN_PASSWORD" \
  --firstname Admin --lastname DataMart --email admin@datamart.local \
  || airflow users reset-password --username "$AIRFLOW_ADMIN_USER" --password "$AIRFLOW_ADMIN_PASSWORD"

echo "[init] 3/4 Connection datamart_dw (repositorio analítico)"
airflow connections delete datamart_dw || true
airflow connections add datamart_dw --conn-type postgres --conn-host postgres-dw --conn-port 5432 \
  --conn-schema "$DW_DB" --conn-login "$DW_USER" --conn-password "$DW_PASSWORD"

echo "[init] 4/4 Variables"
airflow variables import /opt/airflow/config/variables.json

echo "[init] LISTO"
