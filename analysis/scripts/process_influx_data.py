import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"

def carregar_influx_csv(caminho_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(
        caminho_csv,
        skiprows=3,
        names=['result', 'table', '_start', '_stop', '_time',
               '_value', '_field', '_measurement', 'host']
    )
    df = df[df['_field'] != '_field']
    df['_time'] = pd.to_datetime(df['_time'])
    df['_value'] = pd.to_numeric(df['_value'], errors='coerce')

    wide = (
        df
        .pivot_table(index='_time', columns='_field', values='_value')
        .reset_index()
    )

    return wide

def main():
    delay_csv = DATA_RAW / "delay.csv"
    df = carregar_influx_csv(delay_csv)

    df_final = (
        df[['_time', 'power_percent', 'temp_c', 'adc', 'delay_us']]
        .rename(columns={
            '_time': 'tempo',
            'power_percent': 'potencia',
            'temp_c': 'temperatura',
        })
    )

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    output = DATA_PROCESSED / "delay_tratado.csv"
    df_final.to_csv(output, index=False)
    print(f"Ficheiro salvo em: {output}")

if __name__ == "__main__":
    main()

