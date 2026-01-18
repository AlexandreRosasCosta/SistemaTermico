import numpy as np
import matplotlib.pyplot as plt

# modelo identificado
K = 3.0826
tau = 118.9

# PI
Kp = 0.3244
Ki = 0.008414

Ts = 1.0
Tsim = np.zeros(4000)
u = np.zeros(4000)
I = 0.0

SP = 80.0
Tsim[0] = 25.0

for k in range(1, len(Tsim)):
    e = SP - Tsim[k-1]
    I_candidate = I + e*Ts

    u_unsat = Kp*e + Ki*I_candidate
    u[k] = np.clip(u_unsat, 0, 100)

    if u[k] == u_unsat:
        I = I_candidate

    # modelo térmico (Euler)
    Tsim[k] = Tsim[k-1] + Ts*((K*u[k] - Tsim[k-1]) / tau)

t = np.arange(len(Tsim))*Ts

plt.figure(figsize=(9,4))
plt.plot(t, Tsim, label="Temperatura simulada")
plt.axhline(SP, linestyle="--", label="Setpoint")
plt.plot(t, u, label="Potência (%)")
plt.legend()
plt.grid()
plt.show()
