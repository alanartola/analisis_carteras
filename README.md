# analisis_carteras

Proyecto para analizar inversiones. Cartera eficiente (Markowitz) sobre acciones del mercado de capitales argentino (BYMA).

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/alanartola/analisis_carteras/blob/main/cartera_eficiente.ipynb)

## Cómo usar este repo

1. Abrí [`empresas_byma.xlsx`](empresas_byma.xlsx) en Excel y marcá con **x** la columna `Analizar (x)` en las empresas que querés incluir en el análisis (al menos 2).
2. Guardá el archivo y subí el cambio a GitHub (commit + push a la rama `main`).
3. Hacé clic en el botón **Open in Colab** de arriba (o el link de abajo). Se va a abrir el notebook `cartera_eficiente.ipynb` en Google Colab.
4. En Colab, andá a `Entorno de ejecución -> Ejecutar todas` (`Runtime -> Run all`). El notebook lee el Excel directamente desde este repositorio de GitHub, toma solo las empresas marcadas y hace un análisis completo:
   - Estadística descriptiva de retornos (asimetría, curtosis, test de normalidad Jarque-Bera) y drawdown máximo histórico por acción.
   - Matriz de correlación y clustering jerárquico de activos (qué acciones se mueven parecido).
   - Métricas de riesgo por acción: VaR histórico y paramétrico, CVaR (Expected Shortfall), Sortino ratio, Calmar ratio, Beta y Alpha (CAPM) vs el índice Merval.
   - **Seis carteras optimizadas** con criterios distintos: mínima varianza, máximo Sharpe, máxima diversificación, risk parity, HRP (jerárquica) e igual ponderación (1/N) como referencia — con la **frontera eficiente de Markowitz** (nube de Monte Carlo) marcando las seis.
   - Comparación de las seis carteras (retorno, volatilidad, Sharpe, Sortino, Calmar, VaR/CVaR, drawdown máximo, Beta) y cuánto aporta cada activo al riesgo total de cada una.
   - Un **backtest walk-forward** (fuera de muestra, sin look-ahead) de las estrategias re-optimizadas periódicamente, comparadas contra 1/N y el Merval.
   - Un análisis de **robustez por bootstrap**, para visualizar cuánto dependen los pesos óptimos de la muestra histórica usada.

Link directo al notebook: https://colab.research.google.com/github/alanartola/analisis_carteras/blob/main/cartera_eficiente.ipynb

## Contenido

- [`empresas_byma.xlsx`](empresas_byma.xlsx) — universo de empresas y columna para marcar cuáles analizar.
- [`cartera_eficiente.ipynb`](cartera_eficiente.ipynb) — notebook de optimización de cartera (Colab).
- [`scripts/`](scripts/) — scripts usados para construir el Excel (descarga de capitalización de mercado vía `yfinance` y armado del archivo).
- [`requirements.txt`](requirements.txt) — dependencias de Python para correr los scripts localmente.
- [`CLAUDE.md`](CLAUDE.md) — guía técnica del repo para continuar el desarrollo (arquitectura, comandos, entorno).
- [`docs/CONTEXTO_PROYECTO.md`](docs/CONTEXTO_PROYECTO.md) — historial de decisiones y motivos detrás de cada una, para retomar el proyecto sin perder contexto.

## Sobre el universo de empresas

BYMA (Bolsas y Mercados Argentinos) lista oficialmente **82 empresas** con acciones negociables (no 100 — el mercado de capitales argentino es chico y no llega a esa cantidad). El Excel incluye las 82, ordenadas de mayor a menor capitalización bursátil, con 2 excepciones:

- Se excluyeron 2 empresas con la negociación de sus acciones interrumpida (sin precio de mercado).
- 12 empresas no tienen capitalización de mercado publicada en Yahoo Finance (acciones muy poco líquidas); se listan al final marcadas como `N/D` en vez de inventarles un número.

No se incluyen compañías de origen argentino que cotizan solo en el exterior (ej. MercadoLibre, Globant, Despegar), porque no forman parte del mercado de capitales local.

Fuente del listado: [Empresas Listadas — BYMA](https://www.byma.com.ar/financiarse/para-emisoras/empresas-listadas/). Capitalización de mercado y precios: Yahoo Finance, al 13/09/2026.

## Notas

- Los precios son en pesos argentinos (ARS) nominales, sin ajustar por inflación.
- El notebook no permite ventas en corto por defecto, usa una tasa libre de riesgo configurable (0% por defecto) y opcionalmente un techo de concentración por activo — ver la celda de configuración.
- El backtest walk-forward no modela costos de transacción ni impuestos; el bootstrap de robustez remuestrea días de forma independiente (no captura autocorrelación). Ambas simplificaciones están documentadas en la última sección del notebook.
- Esto es una herramienta de análisis exploratorio, no asesoramiento financiero.
