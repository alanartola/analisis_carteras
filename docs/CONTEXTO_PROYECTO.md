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

- El usuario todavía no marcó ninguna empresa con `x` en el Excel real (las pruebas se hicieron en
  una copia en memoria). El primer paso para "usar" el proyecto es que él las marque y pushee.
- Ideas no implementadas porque no se pidieron: ajuste por inflación/CER, tasa libre de riesgo
  real (ej. LECAP), restricciones de concentración máxima por activo o por sector, backtesting de
  la cartera resultante, exportar resultados a un archivo aparte. No agregar esto sin que el
  usuario lo pida explícitamente.
