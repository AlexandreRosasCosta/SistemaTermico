import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter

# =======================
# CONFIG
# =======================
arquivo = "../data/processed/delay_tratado.csv"
t_ini = 186
t_fim = 1400

# parâmetros do tratamento
WINDOW_SG = 21      # Savitzky-Golay (ímpar)
POLY_SG = 2
STEP_MIN = 2.0      # degrau mínimo em potência (%), evita pegar microvariações
PRE_SEC = 120       # janela (s) para média antes do degrau
POST_SEC = 240      # janela (s) para média depois do degrau (para estimar T∞)
SEARCH_SEC = 240    # janela (s) após degrau onde procuramos a maior inclinação

# =======================
# LOAD
# =======================
df = pd.read_csv(arquivo, sep=",", decimal=",", encoding="latin1")

df["Tempo"] = (
    df["Tempo"].astype(str)
    .str.replace(r"[+-]\d\d:\d\d$", "", regex=True)
)
df["Tempo"] = pd.to_datetime(df["Tempo"])

t_all = (df["Tempo"] - df["Tempo"].iloc[0]).dt.total_seconds().values
T_all = df["Temperatura"].values.astype(float)
u_all = df["Potencia"].values.astype(float)

# recorte
mask = (t_all >= t_ini) & (t_all <= t_fim)
t = t_all[mask]
T = T_all[mask]
u = u_all[mask]

# amostragem média
Ts = np.median(np.diff(t))

# =======================
# 1) encontrar degrau de potência (subida) dentro do recorte
# =======================
du = np.diff(u)
# candidatos: subidas maiores que STEP_MIN
cands = np.where(du >= STEP_MIN)[0] + 1  # índice do ponto depois do degrau

if len(cands) == 0:
    raise RuntimeError("Não encontrei degrau de subida de potência no recorte. "
                       "Ajuste t_ini/t_fim ou reduza STEP_MIN.")

# escolhe o maior degrau de subida
k0 = cands[np.argmax(du[cands - 1])]
t0 = t[k0]
du_step = u[k0] - u[k0 - 1]

# =======================
# 2) definir baseline (T0,u0) e final (Tinf, u1) por médias em janelas
# =======================
pre_mask = (t >= t0 - PRE_SEC) & (t < t0)
post_mask = (t >= t0 + POST_SEC/2) & (t <= t0 + POST_SEC)  # pega uma janela mais “depois”

if pre_mask.sum() < 5:
    raise RuntimeError("Poucos pontos antes do degrau para estimar T0. Aumente PRE_SEC ou ajuste recorte.")
if post_mask.sum() < 5:
    raise RuntimeError("Poucos pontos depois do degrau para estimar T∞. Aumente POST_SEC ou ajuste recorte.")

T0 = T[pre_mask].mean()
u0 = u[pre_mask].mean()

Tinf = T[post_mask].mean()
u1 = u[post_mask].mean()

dT = Tinf - T0
dU = u1 - u0

if abs(dU) < 1e-6:
    raise RuntimeError("Δu ~ 0. O degrau não ficou bem definido no trecho escolhido.")

K = dT / dU  # ganho °C por %

# =======================
# 3) suavizar e achar ponto de inflexão (maior inclinação) APÓS o degrau
# =======================
# trabalhar em ΔT
dT_series = T - T0
dT_s = savgol_filter(dT_series, window_length=WINDOW_SG, polyorder=POLY_SG)

# derivada
ddt = np.gradient(dT_s, t)

# procurar máximo da derivada apenas numa janela após o degrau
search_mask = (t >= t0) & (t <= t0 + SEARCH_SEC)
if search_mask.sum() < 5:
    raise RuntimeError("Poucos pontos na janela de busca. Aumente SEARCH_SEC ou ajuste recorte.")

idx_candidates = np.where(search_mask)[0]
idx = idx_candidates[np.argmax(ddt[idx_candidates])]

t_inf = t[idx]
T_inf = dT_s[idx]          # já é ΔT
slope = ddt[idx]           # d(ΔT)/dt

if slope <= 0:
    raise RuntimeError("A derivada máxima ficou <= 0. Verifique o degrau escolhido e o trecho.")

# =======================
# 4) método da reta tangente (interseções)
# =======================
# reta tangente: y = slope*(t - t_inf) + T_inf   (em ΔT)
# interseção com ΔT=0  -> t = t_inf - T_inf/slope  (isso dá L relativo ao t=0 do recorte)
t_L = t_inf - T_inf / slope

# interseção com ΔT = dT -> t = t_inf + (dT - T_inf)/slope
t_Ltau = t_inf + (dT - T_inf) / slope

L = t_L - t0           # atraso a partir do degrau
tau = t_Ltau - t_L     # constante de tempo

# sanidade
if L < 0:
    # em dados reais pode dar ligeiramente negativo por ruído; clamp
    L = 0.0
if tau <= 0:
    raise RuntimeError("τ <= 0. Ajuste janelas/trecho. (Isso normalmente indica escolha errada do degrau/ponto.)")

# =======================
# 5) PI IMC (sugestão)
# =======================
lam = 0.5 * tau  # mais robusto; use 0.5*tau para mais rápido

Kp = tau / (K * (lam + L))
Ki = 1 / (lam + L)

print("=== Degrau escolhido ===")
print(f"t0 = {t0:.1f} s, Δu ≈ {dU:.3f} %, ΔT ≈ {dT:.3f} °C, K ≈ {K:.6f} °C/%")
print("\n=== FOPDT (reta tangente) ===")
print(f"L ≈ {L:.1f} s")
print(f"τ ≈ {tau:.1f} s")
print("\n=== PI (IMC) ===")
print(f"λ = {lam:.1f} s")
print(f"Kp = {Kp:.6f}")
print(f"Ki = {Ki:.6f}  1/s")

# =======================
# PLOT
# =======================
plt.figure(figsize=(10,5))
plt.plot(t, dT_series, label="Temperatura (ΔT)")
plt.plot(t, dT_s, label="Temperatura suavizada (ΔT)")

# reta tangente no eixo ΔT
t_line = np.array([t[0], t[-1]])
T_line = slope*(t_line - t_inf) + T_inf
plt.plot(t_line, T_line, "--", label="Reta tangente")

plt.axvline(t0, color="k", linestyle=":", label="Degrau (t0)")
plt.axvline(t0 + L, color="r", linestyle=":", label="t0 + L")
plt.axvline(t0 + L + tau, color="g", linestyle=":", label="t0 + L + τ")

plt.grid(True)
plt.xlabel("Tempo [s]")
plt.ylabel("ΔT [°C]")
plt.title("Identificação FOPDT por reta tangente (trecho selecionado)")
plt.legend()
plt.tight_layout()
plt.show()

# potência para conferir degrau escolhido
plt.figure(figsize=(10,3))
plt.step(t, u, where="post", label="Potência (%)")
plt.axvline(t0, color="k", linestyle=":", label="Degrau (t0)")
plt.grid(True)
plt.xlabel("Tempo [s]")
plt.ylabel("Potência (%)")
plt.title("Potência no trecho (confirmar degrau escolhido)")
plt.legend()
plt.tight_layout()
plt.show()
