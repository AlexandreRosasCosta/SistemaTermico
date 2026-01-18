import os
from datetime import datetime, timezone, timedelta
import time

import pandas as pd
import streamlit as st
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# ===== ENV =====
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_ORG = os.getenv("INFLUX_ORG", "mestrado")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "mYTCYJHKgJufArCOXusMJYlmuWNOOgeoWf7G5XfAHCGx_iKUHbXrBx6F6FFEP3VlILpa56_qQZ7Ht277G9K_yQ==")

DEVICE_ID = os.getenv("DEVICE_ID", "esp32-heater-5403ad2e")
MODE = os.getenv("MODE", "sim").lower()

INFLUX_BUCKET_REAL = os.getenv("INFLUX_BUCKET_REAL", "mecatronica_interface")
INFLUX_BUCKET_TEST = os.getenv("INFLUX_BUCKET_TEST", "mecatronica_test")

MEAS_TELEMETRY = "heater_telemetry"
MEAS_CONTROLLER = "heater_controller"
MEAS_COMMAND = "heater_command"

def bucket_for_mode():
    return INFLUX_BUCKET_TEST if MODE == "sim" else INFLUX_BUCKET_REAL

def influx_client():
    return InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, timeout=20_000)

def write_setpoint(sp: float):
    bucket = bucket_for_mode()
    now = datetime.now(timezone.utc)
    with influx_client() as client:
        write_api = client.write_api(write_options=SYNCHRONOUS)
        p = (
            Point(MEAS_COMMAND)
            .tag("device", DEVICE_ID)
            .field("setpoint_c", float(sp))
            .time(now)
        )
        write_api.write(bucket=bucket, org=INFLUX_ORG, record=p)

def query_range(measurement: str, field: str, minutes: int = 30) -> pd.DataFrame:
    bucket = bucket_for_mode()
    start = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()

    flux = f"""
    from(bucket: "{bucket}")
      |> range(start: {start})
      |> filter(fn: (r) => r._measurement == "{measurement}")
      |> filter(fn: (r) => r.device == "{DEVICE_ID}")
      |> filter(fn: (r) => r._field == "{field}")
      |> keep(columns: ["_time","_value"])
      |> sort(columns: ["_time"])
    """
    with influx_client() as client:
        query_api = client.query_api()
        tables = query_api.query(flux, org=INFLUX_ORG)

    rows = []
    for t in tables:
        for r in t.records:
            rows.append({"time": r.get_time(), "value": r.get_value()})

    if not rows:
        return pd.DataFrame(columns=["time", "value"])

    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df

st.set_page_config(page_title="Sistema Térmico - Controle", layout="wide")
st.title("Sistema Térmico: gráfico em tempo real + setpoint")

st.caption(f"MODE={MODE} | device={DEVICE_ID} | bucket={bucket_for_mode()}")

# refresh automático
st.sidebar.header("Atualização")
refresh_s = st.sidebar.slider("Refresh (s)", 1, 10, 2)
window_min = st.sidebar.slider("Janela (min)", 5, 120, 30)

# Setpoint control
st.subheader("Setpoint")
col1, col2 = st.columns([1, 1])
with col1:
    sp = st.number_input("Temperatura desejada (°C)", value=39.0, step=0.5)
with col2:
    if st.button("Apply setpoint"):
        write_setpoint(float(sp))
        st.success(f"Setpoint enviado: {sp:.2f} °C")

# Charts
st.subheader("Telemetria")
df_temp = query_range(MEAS_TELEMETRY, "temperature_c", minutes=window_min)
df_u = query_range(MEAS_CONTROLLER, "u_cmd_percent", minutes=window_min)

c1, c2 = st.columns(2)
with c1:
    st.write("Temperatura (°C)")
    if df_temp.empty:
        st.warning("Sem dados de temperatura ainda (telemetry).")
    else:
        st.line_chart(df_temp.set_index("time")["value"])

with c2:
    st.write("Potência enviada pelo controlador (%)")
    if df_u.empty:
        st.warning("Sem dados do controlador ainda.")
    else:
        st.line_chart(df_u.set_index("time")["value"])

# auto-refresh
st.text(f"Atualizando a cada {refresh_s}s...")
time.sleep(refresh_s)
st.rerun()
