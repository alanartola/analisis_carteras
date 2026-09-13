"""Fetch real market cap data for all companies listed on BYMA using yfinance.

Source of company list: https://www.byma.com.ar/financiarse/para-emisoras/empresas-listadas/
(82 companies, fetched 2026-09-13). Suspended tickers excluded.
"""
import json
import time
import yfinance as yf

# (ticker, company name, sector) as published by BYMA. Suspended-trading names
# (COMO, OVOP) are excluded because there is no current market price for them.
COMPANIES = [
    ("A3", "A3 Mercados S.A.", "Finanzas"),
    ("AGRO", "Agrometal S.A.", "Industrial"),
    ("ALUA", "Aluar Aluminio Argentino S.A.", "Materiales"),
    ("AUSO", "Autopistas del Sol S.A.", "Industrial"),
    ("BBAR", "Banco BBVA Argentina S.A.", "Finanzas"),
    ("VALO", "Banco de Valores S.A.", "Finanzas"),
    ("BHIP", "Banco Hipotecario S.A.", "Finanzas"),
    ("BMA", "Banco Macro S.A.", "Finanzas"),
    ("BPAT", "Banco Patagonia S.A.", "Finanzas"),
    ("GAMI", "B Gaming S.A.", "Tecnologia"),
    ("BOLT", "Boldt S.A.", "Consumo Discrecional"),
    ("BYMA", "Bolsas y Mercados Argentinos S.A.", "Finanzas"),
    ("CVH", "Cablevision Holding S.A.", "Comunicaciones"),
    ("CGPA2", "Camuzzi Gas Pampeana S.A.", "Servicios Publicos"),
    ("CAPX", "Capex S.A.", "Energia"),
    ("CARC", "Carboclor S.A.", "Industrial"),
    ("CADO", "Carlos Casado S.A.", "Consumo Basico"),
    ("CELU", "Celulosa Argentina S.A.", "Materiales"),
    ("CECO2", "Central Costanera S.A.", "Servicios Publicos"),
    ("CEPU2", "Central Puerto S.A.", "Servicios Publicos"),
    ("URBA", "Central Urbana S.A.", "Finanzas"),
    ("INTR", "Compania Introductora de Buenos Aires S.A.", "Consumo Basico"),
    ("CTIO", "Consultatio S.A.", "Bienes Inmobiliarios"),
    ("COUR", "Continental Urbana S.A.I.", "Bienes Inmobiliarios"),
    ("CRES", "Cresud S.A.", "Consumo Basico"),
    ("DGCU2", "Distribuidora de Gas Cuyana S.A.", "Servicios Publicos"),
    ("DOME", "Domec S.A.", "Consumo Discrecional"),
    ("ECOG", "Ecogas Inversiones S.A.", "Servicios Publicos"),
    ("EDSH", "Edesa Holding S.A.", "Servicios Publicos"),
    ("EDLH", "Edesal Holding S.A.", "Servicios Publicos"),
    ("EMAC", "Electromac S.A.", "Industrial"),
    ("DSUR", "Empresa Distribuidora Sur S.A. (Edesur)", "Servicios Publicos"),
    ("EDN", "Edenor S.A.", "Servicios Publicos"),
    ("FERR", "Ferrum S.A.", "Industrial"),
    ("FIPL", "Fiplasto S.A.", "Materiales"),
    ("REGE", "Garcia Reguera S.A.", "Consumo Discrecional"),
    ("GARO", "Garovaglio y Zorraquin S.A.", "Industrial"),
    ("GCDI", "GCDI S.A.", "Consumo Discrecional"),
    ("GRIM", "Grimoldi S.A.", "Consumo Discrecional"),
    ("GCLA", "Grupo Clarin S.A.", "Comunicaciones"),
    ("OEST", "Grupo Concesionario del Oeste S.A.", "Industrial"),
    ("GGAL", "Grupo Financiero Galicia S.A.", "Finanzas"),
    ("SUPV", "Grupo Supervielle S.A.", "Finanzas"),
    ("HAVA", "Havanna Holding S.A.", "Consumo Discrecional"),
    ("HARG", "Holcim (Argentina) S.A.", "Materiales"),
    ("HSAT", "Holdsat S.A.", "Comunicaciones"),
    ("IEB", "IEB Construcciones S.A.", "Industrial"),
    ("PATA", "Importadora y Exportadora de la Patagonia S.A.", "Consumo Basico"),
    ("ROSE", "Instituto Rosenbusch S.A.", "Salud"),
    ("INAG", "Insumos Agroquimicos S.A.", "Industrial"),
    ("IEBA", "Inversora Electrica de Buenos Aires S.A.", "Servicios Publicos"),
    ("INVJ", "Inversora Juramento S.A.", "Consumo Basico"),
    ("IRSA", "IRSA Inversiones y Representaciones S.A.", "Bienes Inmobiliarios"),
    ("RICH", "Laboratorios Richmond S.A.C.I.F.", "Salud"),
    ("LEDE", "Ledesma S.A.", "Consumo Basico"),
    ("LOMA", "Loma Negra C.I.A.S.A.", "Materiales"),
    ("LONG", "Longvie S.A.", "Consumo Discrecional"),
    ("METR", "Metrogas S.A.", "Servicios Publicos"),
    ("MIRG", "Mirgor S.A.", "Consumo Discrecional"),
    ("MOLA", "Molinos Agro S.A.", "Consumo Basico"),
    ("SEMI", "Molinos Juan Semino S.A.", "Consumo Basico"),
    ("MOLI", "Molinos Rio de la Plata S.A.", "Consumo Basico"),
    ("MORI", "Morixe Hermanos S.A.", "Consumo Basico"),
    ("GBAN", "Naturgy Ban S.A.", "Servicios Publicos"),
    ("NCON", "Nuevo Continente S.A.", "Bienes Inmobiliarios"),
    ("PAMP", "Pampa Energia S.A.", "Servicios Publicos"),
    ("PREN1", "Papel Prensa S.A.", "Materiales"),
    ("PATR", "Patricios S.A.I.C.", "Finanzas"),
    ("POLL", "Polledo S.A.", "Industrial"),
    ("RAGH", "Raghsa S.A.", "Bienes Inmobiliarios"),
    ("RIGO", "Rigolleau S.A.", "Materiales"),
    ("SAMI", "S.A. San Miguel A.G.I.C.I. y F.", "Consumo Basico"),
    ("COME", "Sociedad Comercial del Plata S.A.", "Energia"),
    ("TECO2", "Telecom Argentina S.A.", "Comunicaciones"),
    ("TXAR", "Ternium Argentina S.A.", "Materiales"),
    ("TRAN", "Transener S.A.", "Servicios Publicos"),
    ("TGNO4", "Transportadora de Gas del Norte S.A.", "Energia"),
    ("TGSU2", "Transportadora de Gas del Sur S.A.", "Energia"),
    ("YPFD", "YPF S.A.", "Energia"),
    ("ZOND", "Zonda Bitcoin Capital S.A.", "Materiales"),
]

# BYMA ticker -> Yahoo Finance ticker overrides, for cases where Yahoo uses a
# different symbol than the official BYMA code (verified manually).
YF_OVERRIDES = {
    "CEPU2": "CEPU.BA",
}

results = []
for ticker, name, sector in COMPANIES:
    yf_ticker = YF_OVERRIDES.get(ticker, f"{ticker}.BA")
    market_cap = None
    currency = None
    price = None
    try:
        t = yf.Ticker(yf_ticker)
        info = t.info
        market_cap = info.get("marketCap")
        currency = info.get("currency")
        price = info.get("currentPrice") or info.get("regularMarketPrice")
    except Exception as e:
        print(f"ERROR {yf_ticker}: {e}")
    results.append({
        "ticker": ticker,
        "yf_ticker": yf_ticker,
        "name": name,
        "sector": sector,
        "market_cap": market_cap,
        "currency": currency,
        "price": price,
    })
    print(f"{yf_ticker:10s} cap={market_cap} ccy={currency} price={price}")
    time.sleep(0.3)

with open("scripts/market_caps_raw.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\nDone. Saved scripts/market_caps_raw.json")
