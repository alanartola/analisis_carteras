# Contexto del proyecto

Este documento es la "memoria" del proyecto: por qué se tomó cada decisión, qué se probó, y qué
falta. Está pensado para que cualquier sesión de Claude Code (u otra persona) pueda retomar el
trabajo desde otra PC sin perder contexto. Para instrucciones de uso del día a día ver
[README.md](../README.md); para arquitectura de archivos ver [CLAUDE.md](../CLAUDE.md).

## Objetivo del proyecto

Herramienta para que el usuario (Alan) elija acciones del mercado de capitales argentino (BYMA)
marcándolas en un Excel, y obtenga automáticamente en Google Colab la cartera eficiente de
Markowitz (mínima varianza y máximo Sharpe ratio) para esas acciones.

## Setup del entorno (PC #1, Windows 11, sept. 2026)

En la primera sesión, la PC no tenía Git ni Claude Code CLI instalados:

- **Git**: no estaba instalado. Se instaló con `winget install --id Git.Git`.
- **Claude Code CLI**: se encontró una instalación previa de npm (`@anthropic-ai/claude-code`)
  incompleta/rota (de abril 2026, sin el binario `claude.exe`), que además tenía shims (`claude`,
  `claude.ps1`) tomando prioridad en el PATH. Se borraron esos restos y se instaló la versión
  buena con `winget install Anthropic.ClaudeCode`.
- **Execution Policy de PowerShell**: bloqueaba `claude.ps1` por política de seguridad
  (`Restricted` por defecto). El usuario corrió él mismo (no Claude, por ser un cambio de
  configuración de seguridad del sistema):
  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
  ```
- **Terminales nuevas**: después de instalar algo que modifica el PATH (Git, Claude Code), hace
  falta abrir una terminal *nueva* — la sesión de PowerShell activa no lo ve hasta reiniciarse.

Si esto se retoma en otra PC, hay que repetir estas instalaciones si no están ya (Python 3.x,
Node.js no es necesario para este proyecto puntual, Git, y opcionalmente Claude Code CLI).

## Acceso de push a GitHub (SSH)

El remoto del repo usa SSH, no HTTPS:
```
git@github.com:alanartola/analisis_carteras.git
```
Se eligió SSH porque el entorno donde corre Claude Code tiene `GIT_TERMINAL_PROMPT=0` (bloquea
cualquier prompt interactivo de login), así que HTTPS con login por navegador (Git Credential
Manager) no funciona desde una sesión de Claude Code no interactiva.

Para poder pushear desde una **PC nueva**, hay que repetir esto (Claude puede hacerlo solo):
```powershell
ssh-keygen -t ed25519 -C "alan.artola90@gmail.com - analisis_carteras" -f "$env:USERPROFILE\.ssh\id_ed25519_analisis_carteras" -N '""'
```
y agregar un bloque `Host github.com` en `~/.ssh/config` apuntando a esa `IdentityFile`. Después
el usuario tiene que pegar la clave pública (el archivo `.pub`, nunca la privada) en
https://github.com/settings/keys. La clave usada en la PC original ya está agregada ahí con el
nombre "analisis_carteras - Claude Code" — si esa PC ya no se va a usar, se puede borrar esa clave
desde GitHub por prolijidad.

## Metodología de datos: por qué 80 empresas y no 100

El pedido original era "las 100 empresas con más capitalización del mercado de capitales de
Argentina". Antes de inventar una lista, se verificó la fuente oficial:
[Empresas Listadas — BYMA](https://www.byma.com.ar/financiarse/para-emisoras/empresas-listadas/),
que al 13/09/2026 mostraba "Mostrando 82 de 82 ítems" — **BYMA solo tiene 82 empresas con acciones
listadas en total**. No existen 100 sin inventar datos o sin incluir empresas argentinas que
cotizan *solo* en el exterior (MercadoLibre, Globant, Despegar — que no son parte del mercado de
capitales local). Se decidió usar el universo completo de BYMA (82) en vez de forzar el número
100, y así se lo comunicó al usuario.

De esas 82:
- 2 tienen la negociación de sus acciones interrumpida (`COMO` - Cía. Argentina de Comodoro
  Rivadavia, `OVOP` - Ovoprot International) → se excluyeron directamente, no tienen precio de
  mercado. Quedan **80**.
- De esas 80, **68 tienen capitalización de mercado** obtenida de Yahoo Finance vía `yfinance`
  (campo `marketCap`, con fallback a `fast_info` y a `precio × shares outstanding`).
- Las otras **12** (`URBA`, `EMAC`, `DSUR`, `EDN`, `HSAT`, `IEB`, `IEBA`, `INVJ`, `NCON`, `PREN1`,
  `PATR`, `ZOND`) no tienen ese dato disponible en Yahoo Finance (acciones muy poco líquidas). Se
  decidió **no inventarles un número**: quedan al final del ranking, en orden alfabético,
  marcadas `N/D` en la columna `Market Cap (ARS)`.

Este razonamiento (no inventar datos faltantes, ser transparente sobre limitaciones) es una
instrucción explícita del usuario ("no cometas errores") y debería mantenerse si se actualiza el
archivo en el futuro.

### Caso especial: CEPU2 → CEPU.BA

El ticker oficial de BYMA para Central Puerto es `CEPU2`, pero en Yahoo Finance esa acción
específica no tiene datos bajo `CEPU2.BA` — el ticker correcto ahí es `CEPU.BA`. Se verificó
manualmente antes de aplicar el override (no es una suposición). Está documentado en el diccionario
`YF_OVERRIDES` de `scripts/fetch_market_caps.py`. Si en el futuro aparecen más casos así, hay que
verificarlos a mano de la misma manera antes de agregarlos ahí.

## Diseño del notebook (`cartera_eficiente.ipynb`)

- Lee el Excel **desde GitHub** (raw URL), no desde un archivo subido a Colab — así el usuario no
  tiene que subir nada manualmente cada vez, solo editar y pushear el Excel.
- Retornos y volatilidad se calculan sobre precios **nominales en ARS** (no ajustados por
  inflación). Se decidió no meterse con ajuste por inflación/CER porque no lo pidió el usuario y
  agrega una fuente más de error/supuestos; queda documentado como limitación en el notebook y en
  el README, no como algo resuelto.
- `RISK_FREE_RATE = 0.0` por defecto porque no hay una fuente confiable y simple de la tasa libre
  de riesgo en pesos para hardcodear sin verificar — se dejó como parámetro editable por el
  usuario en la celda de configuración, con una nota para que la ajuste.
- Sin ventas en corto por defecto (`ALLOW_SHORT = False`), pesos entre 0% y 100% por activo.
- Antes de pushear el notebook se corrió `scripts/test_notebook_logic.py` (misma lógica, contra el
  Excel local con algunas empresas marcadas a mano) para confirmar que la optimización con
  `scipy.optimize.minimize` converge (`success: True`) y no tira errores, sin depender de que el
  archivo ya esté publicado en GitHub.

## Estado actual / próximos pasos posibles (no pedidos aún)

- El usuario ya marcó con `x` 21 empresas en `empresas_byma.xlsx` y las subió él mismo a GitHub
  (commit `43a531f`, directo, sin pasar por Claude) — ver ese commit para la lista exacta si hace
  falta. El notebook ya está en condiciones de correrse en Colab con esa selección.
- Ideas no implementadas porque no se pidieron (estado *antes* de la ampliación de sept. 2026, ver
  más abajo): ajuste por inflación/CER, tasa libre de riesgo real (ej. LECAP), restricciones de
  concentración máxima por activo o por sector, backtesting de la cartera resultante, exportar
  resultados a un archivo aparte.

## Ampliación del notebook a análisis financiero completo (13/09/2026)

El usuario pidió explícitamente ("Inclui todo el analisis financiero que un equipo de los mejores
expertos de finanzas deberia saber... lo mas completo y detallado posible") ampliar
`cartera_eficiente.ipynb` mucho más allá de min-varianza/máx-Sharpe + frontera eficiente. Se agregó
(11 secciones en total; ver el resumen en [CLAUDE.md](../CLAUDE.md)):

- Estadística descriptiva extendida (asimetría, curtosis, test de normalidad Jarque-Bera) y
  drawdown máximo por activo.
- Matriz de correlación (heatmap) y clustering jerárquico (dendrograma).
- Métricas de riesgo por activo: VaR histórico y paramétrico, CVaR/Expected Shortfall, Sortino
  ratio, Calmar ratio, Beta y Alpha (CAPM) vs el Merval (`^MERV`, nuevo benchmark descargado vía
  `yfinance` junto con las acciones).
- Cuatro métodos de optimización adicionales a los dos que ya había: máxima diversificación, risk
  parity (equal risk contribution) y **HRP** (Hierarchical Risk Parity, López de Prado 2016) — más
  1/N como baseline de referencia. En total son 6 carteras comparadas lado a lado.
- Tabla de contribución al riesgo por activo, para cada una de las 6 carteras.
- Backtest walk-forward (re-optimización periódica sobre una ventana móvil, sin look-ahead) de
  mínima varianza y máximo Sharpe, comparado contra 1/N y el Merval.
- Análisis de robustez por bootstrap: remuestrea los retornos históricos N veces y re-optimiza la
  cartera de máximo Sharpe en cada uno, para visualizar (boxplot) cuánto varían los pesos óptimos
  solo por ruido muestral.
- `MAX_WEIGHT_PER_ASSET` como límite de concentración opcional (config, default `None` = sin
  límite) — aplica solo a las 4 carteras que se resuelven vía `scipy.optimize` (no a HRP ni a 1/N,
  documentado como limitación explícita en el notebook).

**Cómo se construyó y validó** (para no repetir el proceso desde cero si hace falta tocarlo de
nuevo): no hay `nbformat`/`jupyter` instalado en `.venv`, así que en vez de escribir el JSON del
`.ipynb` a mano se armó con un script generador descartable (lista de celdas markdown/código en
Python, serializadas a JSON nbformat-4). Antes de escribir el notebook final, se extrajo *todo* el
código de las celdas y se corrió de punta a punta contra el Excel local real (con las 21 empresas
ya marcadas por el usuario) usando el backend `Agg` de matplotlib, verificando explícitamente:
que las 4 optimizaciones de `scipy` convergen (`success: True`), que los pesos de las 6 carteras
suman ~100% y no tienen negativos, que HRP suma exactamente 1.0, que no aparecen `NaN` inesperados
en las tablas de métricas, y que el límite `MAX_WEIGHT_PER_ASSET` efectivamente lo respetan las 4
carteras optimizadas (no HRP/1-N, como se documentó). Recién después de esa validación completa se
generó el `.ipynb` final y se confirmó, celda por celda, que su contenido es idéntico al código que
se había probado. `scripts/test_notebook_logic.py` quedó reescrito para reflejar toda esta lógica
(con parámetros chicos: 1 año de historia, pocos remuestreos bootstrap, Monte Carlo reducido) —
correrlo de nuevo (`.\.venv\Scripts\python.exe scripts\test_notebook_logic.py`) es la forma rápida
de detectar una regresión antes de tocar el notebook a mano.

**HRP, un detalle a tener en cuenta si se retoca:** la implementación (`_orden_quasi_diagonal` +
`_biparticion_recursiva` dentro del notebook) sigue el algoritmo de bisección recursiva de López de
Prado casi al pie de la letra (clustering jerárquico sobre una matriz de distancia basada en
correlación, cuasi-diagonalización del orden de hojas, reparto recursivo por varianza inversa de
cada mitad). Usa `pd.concat` en vez de `Series.append` (removido en pandas moderno) — si se
reescribe, no volver a `.append`.

Nada de lo anterior toca el pedido de "no cometas errores": no se inventó ningún dato ni supuesto
sin marcarlo como tal (por ejemplo, `RISK_FREE_RATE` sigue siendo un parámetro que el usuario debe
ajustar, no un valor inventado) y toda simplificación metodológica (bootstrap i.i.d. sin
autocorrelación, backtest sin costos de transacción, etc.) quedó documentada explícitamente en la
sección de "Notas y limitaciones" del propio notebook.
