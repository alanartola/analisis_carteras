"""Standalone smoke test that replicates the notebook's logic against the
local Excel file (marking a handful of tickers with 'x'), to catch bugs
before the notebook is pushed and run for real from Colab."""
import numpy as np
import pandas as pd
import yfinance as yf
from scipy.optimize import minimize

universo = pd.read_excel("empresas_byma.xlsx", sheet_name="Universo BYMA")
universo["Analizar (x)"] = universo["Analizar (x)"].astype(object)
test_tickers = {"YPFD", "GGAL", "PAMP", "BMA", "ALUA"}
universo.loc[universo["Ticker"].isin(test_tickers), "Analizar (x)"] = "x"

marca = universo["Analizar (x)"].astype(str).str.strip().str.lower()
seleccion = universo[marca.isin(["x", "si", "sí"])].copy()
assert not seleccion.empty, "seleccion vacia"
print("Seleccionadas:", seleccion["Ticker"].tolist())

tickers = seleccion["Ticker Yahoo Finance"].tolist()
nombres = dict(zip(seleccion["Ticker Yahoo Finance"], seleccion["Ticker"]))

raw = yf.download(tickers, period="1y", auto_adjust=True, progress=False)
precios = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].rename(columns={"Close": tickers[0]})
precios = precios.dropna(axis=1, thresh=int(len(precios) * 0.7))
faltantes = set(tickers) - set(precios.columns)
if faltantes:
    print(f"Aviso: sin datos para {sorted(faltantes)}")
precios = precios.rename(columns=nombres).dropna()
assert precios.shape[1] >= 2, "menos de 2 activos con datos"
print("Precios shape:", precios.shape)

retornos_diarios = precios.pct_change().dropna()
DIAS_HABILES = 252
retornos_anuales = retornos_diarios.mean() * DIAS_HABILES
cov_anual = retornos_diarios.cov() * DIAS_HABILES

activos = list(precios.columns)
n = len(activos)
mu = retornos_anuales.values
cov = cov_anual.values
RISK_FREE_RATE = 0.0


def rendimiento_cartera(w):
    return float(np.dot(w, mu))


def volatilidad_cartera(w):
    return float(np.sqrt(np.dot(w, np.dot(cov, w))))


def sharpe_negativo(w):
    vol = volatilidad_cartera(w)
    return 0.0 if vol == 0 else -(rendimiento_cartera(w) - RISK_FREE_RATE) / vol


bounds = tuple((0.0, 1.0) for _ in range(n))
restricciones = ({"type": "eq", "fun": lambda w: np.sum(w) - 1.0},)
w0 = np.repeat(1.0 / n, n)

opt_min_var = minimize(volatilidad_cartera, w0, method="SLSQP", bounds=bounds, constraints=restricciones)
opt_max_sharpe = minimize(sharpe_negativo, w0, method="SLSQP", bounds=bounds, constraints=restricciones)

print("min_var success:", opt_min_var.success, "weights:", np.round(opt_min_var.x, 3), "sum:", opt_min_var.x.sum())
print("max_sharpe success:", opt_max_sharpe.success, "weights:", np.round(opt_max_sharpe.x, 3), "sum:", opt_max_sharpe.x.sum())

rng = np.random.default_rng(42)
N = 2000
resultados = np.zeros((N, 3))
for i in range(N):
    w = rng.random(n)
    w = w / np.sum(w)
    ret = rendimiento_cartera(w)
    vol = volatilidad_cartera(w)
    sharpe = (ret - RISK_FREE_RATE) / vol if vol > 0 else 0.0
    resultados[i] = [vol, ret, sharpe]
print("Simulacion OK, ejemplo fila:", resultados[0])

print("\nTODO OK - la logica del notebook funciona sin errores.")
