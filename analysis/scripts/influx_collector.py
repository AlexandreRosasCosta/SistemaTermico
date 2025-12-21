#!/usr/bin/env python3
import re
import time
import threading
from datetime import datetime, timezone

import serial                     # pip install pyserial
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS


# ===== CONFIGURAÇÕES =====
SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200

INFLUX_URL = "http://localhost:8086"
INFLUX_ORG = "mestrado"
INFLUX_BUCKET = "mecatronica"
INFLUX_TOKEN = "BIy2hBGmm8HTr3vXc6XjMSHj6kvDB_ACn3IiU6omXANoOJKU8AX5FUxC69f4PUWvErtF7XxdgiW84GzDC527qg=="

# Filtros simples de sanidade
TEMP_MIN = -20.0
TEMP_MAX = 200.0
ADC_MIN = 0.0
ADC_MAX = 4095.0


def thread_envio_potencia(ser: serial.Serial):
    """
    Thread que fica lendo valores do teclado e mandando para o ESP32.
    """
    print("\n=== Controle de potência ===")
    print("Digite um valor de 0 a 100 e pressione Enter.")
    print("Digite 'q' e Enter para sair.\n")

    while True:
        try:
            cmd = input("Potência [%]: ").strip()
        except EOFError:
            # terminal fechado
            break

        if not cmd:
            continue

        if cmd.lower() == "q":
            print("Saindo por comando do usuário...")
            # encerra o programa todo
            raise SystemExit

        # validação simples
        try:
            val = float(cmd.replace(",", "."))
        except ValueError:
            print("Valor inválido, digite um número entre 0 e 100.")
            continue

        if not (0.0 <= val <= 100.0):
            print("Valor fora da faixa (0–100).")
            continue

        # envia para o ESP32, com \n
        try:
            ser.write((f"{val}\n").encode("utf-8"))
            ser.flush()
            print(f"Enviado para o ESP32: {val}%")
        except Exception as e:
            print(f"[ERRO AO ENVIAR NA SERIAL] {e}")


def main():
    # Conecta no InfluxDB
    client = InfluxDBClient(
        url=INFLUX_URL,
        token=INFLUX_TOKEN,
        org=INFLUX_ORG,
        timeout=10_000,
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)

    # Conecta na serial
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print(f"Lendo de {SERIAL_PORT} @ {BAUD_RATE} e enviando para o InfluxDB...")

    # limpa qualquer lixo inicial
    ser.reset_input_buffer()

    # Inicia thread que envia potência
    t_writer = threading.Thread(target=thread_envio_potencia, args=(ser,), daemon=True)
    t_writer.start()

    # Para calcular tempo de execução (uptime do coletor)
    start_monotonic = time.monotonic()

    # Últimos valores válidos de ADC/Temperatura
    last_adc = None
    last_temp = None

    try:
        while True:
            try:
                line_bytes = ser.readline()
            except serial.SerialException as e:
                print(f"[ERRO SERIAL] {e}")
                time.sleep(1)
                continue

            if not line_bytes:
                continue

            try:
                line = line_bytes.decode("utf-8", errors="ignore").strip()
            except Exception:
                continue

            if not line:
                continue

            # ---------- 1) Linha ADC / Temp ----------
            m_adc = re.match(r"ADC:\s*([0-9.]+)\s*\|\s*Temp:\s*([-0-9.]+)", line)
            if m_adc:
                adc = float(m_adc.group(1))
                temp_c = float(m_adc.group(2))

                if (ADC_MIN <= adc <= ADC_MAX) and (TEMP_MIN <= temp_c <= TEMP_MAX):
                    last_adc = adc
                    last_temp = temp_c
                else:
                    print(f"[WARN] Ignorando ADC/Temp fora da faixa: {adc}, {temp_c}")
                continue

            # ---------- 2) Linha ZC / Potência / Delay ----------
            m_zc = re.match(
                r"ZC:\s*([0-9]+)\s*\|\s*Potência:\s*([0-9.]+)%\s*\|\s*Delay_us:\s*([0-9]+)",
                line
            )
            if m_zc:
                zc = int(m_zc.group(1))
                power = float(m_zc.group(2))
                delay = int(m_zc.group(3))

                uptime_s = time.monotonic() - start_monotonic
                ts = datetime.now(timezone.utc)

                p = (
                    Point("sistema_termico")
                    .tag("host", "esp32")
                    .field("zc", zc)
                    .field("power_percent", power)
                    .field("delay_us", delay)
                    .field("uptime_s", uptime_s)
                    .time(ts)
                )

                if last_adc is not None:
                    p = p.field("adc", last_adc)
                if last_temp is not None:
                    p = p.field("temp_c", last_temp)

                write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=p)

                print(
                    f"[OK] ZC={zc}, Pot={power}%, Delay={delay}us, "
                    f"ADC={last_adc}, Temp={last_temp}, Uptime={uptime_s:0.1f}s"
                )
                continue

            # Outras linhas do ESP32 (se tiver) você pode logar ou ignorar:
            # print("[ESP32]", line)

            time.sleep(0.01)

    except SystemExit:
        pass
    except KeyboardInterrupt:
        print("\nEncerrando (Ctrl+C)...")
    finally:
        try:
            ser.close()
        except Exception:
            pass
        client.close()


if __name__ == "__main__":
    main()
