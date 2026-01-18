import pandas as pd
import matplotlib.pyplot as plt

# ===== CONFIGURAÇÃO =====
arquivo = "../data/processed/delay_tratado.csv"   # ajuste o caminho se necessário
sep = ","                       # separador do CSV
col_tempo = "Tempo"
col_temp = "Temperatura"
col_pot  = "Potencia"

# ===== LER CSV =====
df = pd.read_csv(
    arquivo,
    sep=sep,
    decimal=",",
    parse_dates=[col_tempo]
)

# tempo em segundos desde o início
t = (df[col_tempo] - df[col_tempo].iloc[0]).dt.total_seconds()

T = df[col_temp]
u = df[col_pot]

# ===== PLOT =====
fig, ax1 = plt.subplots()

ax1.plot(t, T, label="Temperatura (°C)", color="black")
ax1.set_xlabel("Tempo [s]")
ax1.set_ylabel("Temperatura [°C]")
ax1.grid(True)

# eixo secundário para potência
ax2 = ax1.twinx()
ax2.step(t, u, label="Potência (%)", color="tab:orange", where="post")
ax2.set_ylabel("Potência (%)")

# legendas
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="best")

plt.title("Resposta térmica ao degrau de potência")
plt.tight_layout()
plt.show()

