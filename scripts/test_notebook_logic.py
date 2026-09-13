"""Standalone smoke test that replicates the notebook's logic against the
local Excel file (marking a handful of tickers with 'x'), to catch bugs
before the notebook is pushed and run for real from Colab.

Mirrors every section of cartera_eficiente.ipynb (descriptive stats, risk
metrics, the six portfolio-construction methods, the efficient frontier,
the walk-forward backtest and the bootstrap robustness check) but with much
smaller parameters (fewer Monte Carlo draws, fewer bootstrap resamples,
1 year of history) so it runs in seconds instead of minutes. Run this after
editing the notebook's logic.
"""
import matplotlib
matplotlib.use("Agg")  # headless: no window needed for this smoke test

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from scipy import stats
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import squareform

RISK_FREE_RATE = 0.0
BENCHMARK_TICKER = "^MERV"
BENCHMARK_NOMBRE = "Merval"
ALLOW_SHORT = False
MAX_WEIGHT_PER_ASSET = None
VAR_CONFIDENCE_LEVELS = [0.95, 0.99]
BACKTEST_TRAIN_WINDOW = 100
BACKTEST_REBALANCE_EVERY = 20
N_PORTFOLIOS = 500
N_BOOTSTRAP = 20
DIAS_HABILES = 252

# --- 1. Selección ------------------------------------------------------------------
universo = pd.read_excel("empresas_byma.xlsx", sheet_name="Universo BYMA")
universo["Analizar (x)"] = universo["Analizar (x)"].astype(object)
test_tickers = {"YPFD", "GGAL", "PAMP", "BMA", "ALUA"}
universo.loc[universo["Ticker"].isin(test_tickers), "Analizar (x)"] = "x"

marca = universo["Analizar (x)"].astype(str).str.strip().str.lower()
seleccion = universo[marca.isin(["x", "si", "sí"])].copy()
assert not seleccion.empty, "seleccion vacia"
print("Seleccionadas:", seleccion["Ticker"].tolist())

# --- 2. Precios (acciones + benchmark) ---------------------------------------------
tickers = seleccion["Ticker Yahoo Finance"].tolist()
nombres = dict(zip(seleccion["Ticker Yahoo Finance"], seleccion["Ticker"]))

raw = yf.download(tickers, period="1y", auto_adjust=True, progress=False)
precios = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].rename(columns={"Close": tickers[0]})
precios = precios.dropna(axis=1, thresh=int(len(precios) * 0.7))
faltantes = set(tickers) - set(precios.columns)
if faltantes:
    print(f"Aviso: sin datos para {sorted(faltantes)}")
precios = precios.rename(columns=nombres).dropna().sort_index()
assert precios.shape[1] >= 2, "menos de 2 activos con datos"
print("Precios shape:", precios.shape)

try:
    bench_raw = yf.download(BENCHMARK_TICKER, period="1y", auto_adjust=True, progress=False)
    bench_precios = bench_raw["Close"]
    if isinstance(bench_precios, pd.DataFrame):
        bench_precios = bench_precios.iloc[:, 0]
    bench_precios = bench_precios.dropna().sort_index()
    tiene_benchmark = len(bench_precios) > 0
except Exception as e:
    print(f"Aviso: sin benchmark ({e})")
    bench_precios = None
    tiene_benchmark = False

# --- 3. Retornos y estadistica descriptiva ------------------------------------------
retornos_diarios = precios.pct_change().dropna()
retornos_anuales = retornos_diarios.mean() * DIAS_HABILES
cov_anual = retornos_diarios.cov() * DIAS_HABILES
vol_anual = pd.Series(np.sqrt(np.diag(cov_anual)), index=cov_anual.index)


def max_drawdown(serie_precios):
    acumulado = serie_precios / serie_precios.iloc[0]
    pico = acumulado.cummax()
    return (acumulado / pico - 1.0).min()


max_dd_por_activo = precios.apply(max_drawdown)
asimetria = retornos_diarios.skew()
curtosis_exceso = retornos_diarios.kurt()
jb_pvalor = {col: stats.jarque_bera(retornos_diarios[col].values)[1] for col in retornos_diarios.columns}

resumen = pd.DataFrame({
    "Retorno anual esperado": retornos_anuales,
    "Volatilidad anual": vol_anual,
    "Asimetria": asimetria,
    "Curtosis exceso": curtosis_exceso,
    "Jarque-Bera p-valor": pd.Series(jb_pvalor),
    "Drawdown maximo historico": max_dd_por_activo,
})
assert not resumen.isna().any().any(), "NaN inesperado en el resumen descriptivo"
print("Resumen descriptivo OK, shape:", resumen.shape)

if tiene_benchmark:
    bench_precios_alineado = bench_precios.reindex(precios.index).ffill()
    bench_ret = bench_precios_alineado.pct_change().reindex(retornos_diarios.index)
else:
    bench_ret = None

# --- 4. Correlacion y clustering jerarquico -----------------------------------------
corr = retornos_diarios.corr()
distancia_corr = np.sqrt(np.clip((1 - corr.values) / 2, 0, None))
np.fill_diagonal(distancia_corr, 0.0)
condensada = squareform(distancia_corr, checks=False)
enlace = linkage(condensada, method="average")
plt.figure()
dendrogram(enlace, labels=corr.columns.tolist())
plt.close("all")
print("Correlacion y dendrograma OK")

# --- 5. Metricas de riesgo por activo ------------------------------------------------
def var_historico(retornos, confianza):
    return -np.percentile(retornos, (1 - confianza) * 100)


def cvar_historico(retornos, confianza):
    umbral = np.percentile(retornos, (1 - confianza) * 100)
    cola = retornos[retornos <= umbral]
    return -cola.mean() if len(cola) > 0 else np.nan


def var_parametrico(media, desvio, confianza):
    z = stats.norm.ppf(1 - confianza)
    return -(media + z * desvio)


def downside_deviation(retornos, objetivo_minimo=0.0):
    bajo_objetivo = retornos[retornos < objetivo_minimo] - objetivo_minimo
    if len(bajo_objetivo) == 0:
        return 0.0
    return float(np.sqrt((bajo_objetivo ** 2).mean()))


filas_riesgo = []
for col in retornos_diarios.columns:
    r = retornos_diarios[col].values
    fila = {"Activo": col}
    for cl in VAR_CONFIDENCE_LEVELS:
        fila[f"VaR historico {int(cl * 100)}%"] = var_historico(r, cl)
        fila[f"CVaR historico {int(cl * 100)}%"] = cvar_historico(r, cl)
    fila["VaR parametrico 95%"] = var_parametrico(r.mean(), r.std(), 0.95)
    dd_anual = downside_deviation(r) * np.sqrt(DIAS_HABILES)
    ret_anual = retornos_anuales[col]
    fila["Sortino"] = (ret_anual - RISK_FREE_RATE) / dd_anual if dd_anual > 0 else np.nan
    mdd = max_dd_por_activo[col]
    fila["Calmar"] = ret_anual / abs(mdd) if mdd < 0 else np.nan
    filas_riesgo.append(fila)

tabla_riesgo = pd.DataFrame(filas_riesgo).set_index("Activo")

if tiene_benchmark:
    conjunto_capm = retornos_diarios.join(bench_ret.rename(BENCHMARK_NOMBRE), how="inner")
    for col in retornos_diarios.columns:
        datos = conjunto_capm[[col, BENCHMARK_NOMBRE]].dropna()
        beta, alpha_diario = np.polyfit(datos[BENCHMARK_NOMBRE].values, datos[col].values, 1)
        assert np.isfinite(beta) and np.isfinite(alpha_diario)
print("Metricas de riesgo por activo OK, shape:", tabla_riesgo.shape)

# --- 6. Optimizacion: 6 carteras -----------------------------------------------------
activos = list(precios.columns)
n = len(activos)
mu = retornos_anuales.values
cov = cov_anual.values
sigma_individual = vol_anual.values


def rendimiento_cartera(w):
    return float(np.dot(w, mu))


def volatilidad_cartera(w):
    return float(np.sqrt(np.dot(w, np.dot(cov, w))))


def sharpe_negativo(w):
    vol = volatilidad_cartera(w)
    return 0.0 if vol == 0 else -(rendimiento_cartera(w) - RISK_FREE_RATE) / vol


def diversification_ratio(w):
    vol = volatilidad_cartera(w)
    return 0.0 if vol == 0 else float(np.dot(w, sigma_individual)) / vol


def diversification_ratio_negativo(w):
    return -diversification_ratio(w)


def contribuciones_riesgo(w):
    vol = volatilidad_cartera(w)
    if vol == 0:
        return np.zeros_like(w)
    marginal = np.dot(cov, w) / vol
    return w * marginal


def objetivo_risk_parity(w):
    vol = volatilidad_cartera(w)
    if vol == 0:
        return 1e6
    contrib_pct = contribuciones_riesgo(w) / vol
    return float(np.sum((contrib_pct - contrib_pct.mean()) ** 2))


cota_superior = 1.0 if MAX_WEIGHT_PER_ASSET is None else min(1.0, MAX_WEIGHT_PER_ASSET)
cota_inferior = -1.0 if ALLOW_SHORT else 0.0
bounds = tuple((cota_inferior, cota_superior) for _ in range(n))
bounds_largo_solo = tuple((0.0, cota_superior) for _ in range(n))
restricciones = ({"type": "eq", "fun": lambda w: np.sum(w) - 1.0},)
w0 = np.repeat(1.0 / n, n)

opt_min_var = minimize(volatilidad_cartera, w0, method="SLSQP", bounds=bounds, constraints=restricciones)
opt_max_sharpe = minimize(sharpe_negativo, w0, method="SLSQP", bounds=bounds, constraints=restricciones)
opt_max_div = minimize(diversification_ratio_negativo, w0, method="SLSQP", bounds=bounds_largo_solo, constraints=restricciones)
opt_risk_parity = minimize(objetivo_risk_parity, w0, method="SLSQP", bounds=bounds_largo_solo, constraints=restricciones)

assert opt_min_var.success and opt_max_sharpe.success and opt_max_div.success and opt_risk_parity.success, \
    "alguna optimizacion no convergio"

pesos_min_var = opt_min_var.x
pesos_max_sharpe = opt_max_sharpe.x
pesos_max_div = opt_max_div.x
pesos_risk_parity = opt_risk_parity.x / opt_risk_parity.x.sum()
print("Las 4 optimizaciones con scipy convergieron OK")


def _orden_quasi_diagonal(enlace_link):
    enlace_link = enlace_link.astype(int)
    n_items = enlace_link[-1, 3]
    orden = pd.Series([enlace_link[-1, 0], enlace_link[-1, 1]])
    while orden.max() >= n_items:
        orden.index = range(0, orden.shape[0] * 2, 2)
        es_cluster = orden[orden >= n_items]
        idx = es_cluster.index
        fila_enlace = es_cluster.values - n_items
        orden[idx] = enlace_link[fila_enlace, 0]
        hijos = pd.Series(enlace_link[fila_enlace, 1], index=idx + 1)
        orden = pd.concat([orden, hijos]).sort_index()
        orden.index = range(orden.shape[0])
    return orden.tolist()


def _varianza_cluster(cov_df, items):
    cov_sub = cov_df.loc[items, items].values
    ivp = 1.0 / np.diag(cov_sub)
    ivp = ivp / ivp.sum()
    return float(ivp @ cov_sub @ ivp)


def _biparticion_recursiva(cov_df, items_ordenados):
    pesos = pd.Series(1.0, index=items_ordenados)
    clusters = [items_ordenados]
    while len(clusters) > 0:
        clusters = [c[i:j] for c in clusters
                    for i, j in ((0, len(c) // 2), (len(c) // 2, len(c)))
                    if len(c) > 1]
        for i in range(0, len(clusters), 2):
            c0, c1 = clusters[i], clusters[i + 1]
            var0 = _varianza_cluster(cov_df, c0)
            var1 = _varianza_cluster(cov_df, c1)
            alfa = 1 - var0 / (var0 + var1)
            pesos[c0] *= alfa
            pesos[c1] *= (1 - alfa)
    return pesos


def pesos_hrp(retornos):
    corr_hrp = retornos.corr()
    cov_hrp = retornos.cov()
    dist = np.sqrt(np.clip((1 - corr_hrp.values) / 2, 0, None))
    np.fill_diagonal(dist, 0.0)
    enlace_hrp = linkage(squareform(dist, checks=False), method="single")
    orden = _orden_quasi_diagonal(enlace_hrp)
    etiquetas = [retornos.columns[i] for i in orden]
    serie_pesos = _biparticion_recursiva(cov_hrp, etiquetas)
    return serie_pesos.reindex(retornos.columns).values


pesos_hrp_valores = pesos_hrp(retornos_diarios)
assert abs(pesos_hrp_valores.sum() - 1.0) < 1e-6, "HRP no suma 1"
print("HRP OK, suma:", round(pesos_hrp_valores.sum(), 6))

carteras = {
    "Minima varianza": pesos_min_var,
    "Maximo Sharpe": pesos_max_sharpe,
    "Max. diversificacion": pesos_max_div,
    "Risk parity": pesos_risk_parity,
    "HRP": pesos_hrp_valores,
    "Igual ponderacion (1/N)": w0,
}
for nombre, w in carteras.items():
    assert abs(w.sum() - 1.0) < 1e-3, f"{nombre} no suma 1: {w.sum()}"
    if not ALLOW_SHORT:
        assert (w >= -1e-9).all(), f"{nombre} tiene pesos negativos"

# --- 7. Frontera eficiente (Monte Carlo reducido) ------------------------------------
rng = np.random.default_rng(42)
resultados = np.zeros((N_PORTFOLIOS, 3))
for i in range(N_PORTFOLIOS):
    w = rng.normal(size=n) if ALLOW_SHORT else rng.random(n)
    w = w / np.sum(w)
    ret = rendimiento_cartera(w)
    vol = volatilidad_cartera(w)
    sharpe = (ret - RISK_FREE_RATE) / vol if vol > 0 else 0.0
    resultados[i] = [vol, ret, sharpe]
plt.figure()
plt.scatter(resultados[:, 0], resultados[:, 1], c=resultados[:, 2])
plt.close("all")
print("Simulacion Monte Carlo OK, ejemplo fila:", resultados[0])

# --- 8. Comparacion de carteras -------------------------------------------------------
def metricas_cartera(w):
    ret = rendimiento_cartera(w)
    vol = volatilidad_cartera(w)
    sharpe = (ret - RISK_FREE_RATE) / vol if vol > 0 else np.nan
    ret_diarios_cartera = retornos_diarios.values @ w
    serie_ret_cartera = pd.Series(ret_diarios_cartera, index=retornos_diarios.index)
    dd_anual = downside_deviation(ret_diarios_cartera) * np.sqrt(DIAS_HABILES)
    sortino = (ret - RISK_FREE_RATE) / dd_anual if dd_anual > 0 else np.nan
    valor_cartera = (1 + serie_ret_cartera).cumprod()
    mdd = (valor_cartera / valor_cartera.cummax() - 1.0).min()
    calmar = ret / abs(mdd) if mdd < 0 else np.nan
    fila = {
        "Retorno": ret, "Vol": vol, "Sharpe": sharpe, "Sortino": sortino, "Calmar": calmar,
        "VaR95": var_historico(ret_diarios_cartera, 0.95),
        "CVaR95": cvar_historico(ret_diarios_cartera, 0.95),
        "MaxDD": mdd, "DivRatio": diversification_ratio(w),
    }
    if tiene_benchmark:
        conjunto = pd.concat([serie_ret_cartera.rename("cartera"), bench_ret.rename(BENCHMARK_NOMBRE)], axis=1).dropna()
        beta_c, alpha_c = np.polyfit(conjunto[BENCHMARK_NOMBRE].values, conjunto["cartera"].values, 1)
        fila["Beta"] = beta_c
        fila["Alpha"] = alpha_c * DIAS_HABILES
    return fila


tabla_metricas = pd.DataFrame({nombre: metricas_cartera(w) for nombre, w in carteras.items()}).T
assert not tabla_metricas.isna().any().any(), "NaN inesperado en tabla_metricas"
print("Tabla de metricas de las 6 carteras OK:")
print(tabla_metricas.round(3))

tabla_contribucion = pd.DataFrame({
    nombre: (contribuciones_riesgo(w) / volatilidad_cartera(w) * 100) if volatilidad_cartera(w) > 0 else np.zeros(n)
    for nombre, w in carteras.items()
}, index=activos).round(2)
for nombre in carteras:
    assert abs(tabla_contribucion[nombre].sum() - 100) < 0.5, f"contribucion al riesgo de {nombre} no suma 100%"
print("Tabla de contribucion al riesgo OK")

# --- 10. Backtest walk-forward --------------------------------------------------------
def _optimizar_ventana(mu_ventana, cov_ventana, objetivo):
    n_local = len(mu_ventana)
    bounds_local = tuple((cota_inferior, cota_superior) for _ in range(n_local))
    restricciones_local = ({"type": "eq", "fun": lambda w: np.sum(w) - 1.0},)
    w0_local = np.repeat(1.0 / n_local, n_local)

    def vol_local(w):
        return float(np.sqrt(np.dot(w, np.dot(cov_ventana, w))))

    def objetivo_local(w):
        if objetivo == "min_var":
            return vol_local(w)
        v = vol_local(w)
        return 0.0 if v == 0 else -(float(np.dot(w, mu_ventana)) - RISK_FREE_RATE) / v

    res = minimize(objetivo_local, w0_local, method="SLSQP", bounds=bounds_local, constraints=restricciones_local)
    return res.x if res.success else w0_local


retornos_bt = retornos_diarios
fechas_bt_totales = retornos_bt.index
inicio = BACKTEST_TRAIN_WINDOW
assert inicio < len(fechas_bt_totales), "no hay suficiente historia para el backtest de prueba"

estrategias = ["min_var", "max_sharpe"]
pesos_actuales = {estr: np.repeat(1.0 / n, n) for estr in estrategias}
filas_bt = {estr: [] for estr in estrategias}
filas_bt["Igual ponderacion (1/N)"] = []
fechas_out = []

for t in range(inicio, len(fechas_bt_totales)):
    if (t - inicio) % BACKTEST_REBALANCE_EVERY == 0:
        ventana = retornos_bt.iloc[t - BACKTEST_TRAIN_WINDOW:t]
        mu_ventana = ventana.mean().values * DIAS_HABILES
        cov_ventana = ventana.cov().values * DIAS_HABILES
        for estr in estrategias:
            pesos_actuales[estr] = _optimizar_ventana(mu_ventana, cov_ventana, estr)
    r_dia = retornos_bt.iloc[t].values
    for estr in estrategias:
        filas_bt[estr].append(float(np.dot(pesos_actuales[estr], r_dia)))
    filas_bt["Igual ponderacion (1/N)"].append(float(np.mean(r_dia)))
    fechas_out.append(fechas_bt_totales[t])

bt_retornos = pd.DataFrame(filas_bt, index=fechas_out)
if tiene_benchmark:
    bt_retornos[BENCHMARK_NOMBRE] = bench_ret.reindex(bt_retornos.index)
bt_valor = (1 + bt_retornos.fillna(0.0)).cumprod()
assert bt_valor.notna().all().all() or tiene_benchmark, "NaN inesperado en el backtest"
plt.figure()
for col in bt_valor.columns:
    plt.plot(bt_valor.index, bt_valor[col])
plt.close("all")
print(f"Backtest walk-forward OK: {len(bt_retornos)} ruedas fuera de muestra")

# --- 11. Bootstrap de robustez ---------------------------------------------------------
rng_bootstrap = np.random.default_rng(123)
n_obs = len(retornos_diarios)
retornos_matriz = retornos_diarios.values
pesos_bootstrap = np.zeros((N_BOOTSTRAP, n))
for b in range(N_BOOTSTRAP):
    idx = rng_bootstrap.integers(0, n_obs, size=n_obs)
    muestra = retornos_matriz[idx]
    mu_b = muestra.mean(axis=0) * DIAS_HABILES
    cov_b = np.cov(muestra, rowvar=False) * DIAS_HABILES
    pesos_bootstrap[b] = _optimizar_ventana(mu_b, cov_b, "max_sharpe")
    assert abs(pesos_bootstrap[b].sum() - 1.0) < 1e-3

plt.figure()
plt.boxplot([pesos_bootstrap[:, i] * 100 for i in range(n)], tick_labels=activos)
plt.close("all")
print(f"Bootstrap de robustez OK ({N_BOOTSTRAP} remuestreos)")

print("\nTODO OK - la logica completa del notebook funciona sin errores.")
