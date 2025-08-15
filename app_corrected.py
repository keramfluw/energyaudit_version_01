
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Erhebungsbogen & Sanierungs-ROI", layout="wide")

# ------------------------------
# Helper: Baupreisindex (Destatis, 2021=100) - Instandhaltung Wohngebäude (ohne Schönheitsreparaturen)
# Quelle: Destatis, Konjunkturindikator bpr210, Stand 10.07.2025
# ------------------------------
BAUPREISINDEX_INST = {
    "2021": {"I": 95.1, "II": 98.7, "III": 102.0, "IV": 104.3},
    "2022": {"I": 109.0, "II": 114.4, "III": 118.0, "IV": 121.3},
    "2023": {"I": 124.8, "II": 126.7, "III": 127.7, "IV": 128.5},
    "2024": {"I": 130.4, "II": 131.4, "III": 132.4, "IV": 133.1},
    "2025": {"I": 135.2, "II": 136.4}
}
INDEX_BASE = 100.0  # 2021 Jahresdurchschnitt = 100

# ------------------------------
# Default Emissionsfaktoren (kg CO2/kWh) & CO2-Preis
# Quellenhinweis im README (UBA/BMWK/BAFA)
# ------------------------------
DEFAULT_EF = {
    "strom": 0.363,    # UBA Strommix 2024 ~ 363 g/kWh
    "erdgas": 0.20088, # BMWK/BEHG-Richtwert
    "heizoel": 0.2664, # BMWK/BAFA
    "fernwaerme": 0.2  # Platzhalter, standortabhängig – bitte anpassen
}
DEFAULT_CO2_PRICE_EUR_T = 55.0  # 2025 (BEHG) – kann angepasst werden

# ------------------------------
# Measures library (editable in-app)
# capex_unit at index=100 (Jahresdurchschnitt 2021), scaled by selected Destatis-Index
# savings_% are default expectation; user can override per measure
# affects: dict of vectors ('heating', 'electricity') with percentage savings (0..1) or special flags
# ------------------------------
MEASURES = [
    {
        "code": "roof_ins",
        "name": "Dach-Dämmung",
        "category": "Hülle",
        "unit": "m² Dachfläche",
        "default_qty_from": "area",  # use building area as proxy unless user overrides
        "capex_unit_2021": 140.0,
        "lifetime_y": 30,
        "affects": {"heating_pct": 0.08, "electricity_pct": 0.0}
    },
    {
        "code": "wall_wdvs",
        "name": "Außenwand-Dämmung (WDVS)",
        "category": "Hülle",
        "unit": "m² Fassadenfläche",
        "default_qty_from": "area",  # proxy; anpassen empfohlen
        "capex_unit_2021": 220.0,
        "lifetime_y": 30,
        "affects": {"heating_pct": 0.15}
    },
    {
        "code": "basement_ins",
        "name": "Kellerdecken-Dämmung",
        "category": "Hülle",
        "unit": "m² Deckenfläche",
        "default_qty_from": "area",
        "capex_unit_2021": 80.0,
        "lifetime_y": 25,
        "affects": {"heating_pct": 0.05}
    },
    {
        "code": "windows_triple",
        "name": "Fenstertausch (3-fach)",
        "category": "Hülle",
        "unit": "m² Fensterfläche",
        "default_qty_from": "window_ratio",  # area * window_ratio
        "capex_unit_2021": 750.0,
        "lifetime_y": 30,
        "affects": {"heating_pct": 0.10}
    },
    {
        "code": "hydraulic_balance",
        "name": "Hydraulischer Abgleich + Heizkurve",
        "category": "Heizung/Regelung",
        "unit": "m² Wohn-/Nutzfläche",
        "default_qty_from": "area",
        "capex_unit_2021": 15.0,
        "lifetime_y": 15,
        "affects": {"heating_pct": 0.08, "electricity_pct": 0.01}
    },
    {
        "code": "pump_vfd",
        "name": "Hocheffizienz-Heizungs-/Zirkulationspumpen",
        "category": "Heizung/Regelung",
        "unit": "m² Wohn-/Nutzfläche",
        "default_qty_from": "area",
        "capex_unit_2021": 8.0,
        "lifetime_y": 12,
        "affects": {"electricity_pct": 0.02}
    },
    {
        "code": "vent_wrg",
        "name": "Dezentrale Lüftung mit WRG",
        "category": "Lüftung",
        "unit": "Wohneinheiten",
        "default_qty_from": "units",
        "capex_unit_2021": 2500.0,
        "lifetime_y": 20,
        "affects": {"heating_pct": 0.08, "electricity_extra_kwh_per_unit": 50.0}
    },
    {
        "code": "led_lighting",
        "name": "LED + Präsenz-/Tageslichtregelung (Allgemeinbereiche)",
        "category": "Strom",
        "unit": "m² Allgemeinflächen",
        "default_qty_from": "common_area",
        "capex_unit_2021": 15.0,
        "lifetime_y": 12,
        "affects": {"electricity_pct_of_share": 0.5, "electricity_share_of_total": 0.15}
    },
    {
        "code": "bms_opt",
        "name": "Gebäudeautomation / EMS-Optimierung",
        "category": "Digital",
        "unit": "m² Wohn-/Nutzfläche",
        "default_qty_from": "area",
        "capex_unit_2021": 8.0,
        "lifetime_y": 10,
        "affects": {"heating_pct": 0.05, "electricity_pct": 0.05}
    },
    {
        "code": "pv_system",
        "name": "PV-Anlage (Dach)",
        "category": "Erzeugung",
        "unit": "kWp",
        "default_qty_from": "pv_kwp",
        "capex_unit_2021": 1200.0,
        "lifetime_y": 25,
        "affects": {"pv_specific_yield": 950.0, "self_consumption_share": 0.6, "feed_in_tariff_eur_kwh": 0.08}
    },
    {
        "code": "dhw_circ_opt",
        "name": "TWW-Zirkulation: Dämmung/Zeiten/Regelung",
        "category": "Heizung/Regelung",
        "unit": "Wohneinheiten",
        "default_qty_from": "units",
        "capex_unit_2021": 150.0,
        "lifetime_y": 12,
        "affects": {"heating_pct": 0.03, "electricity_pct": 0.005}
    },
    {
        "code": "heat_pump_aw",
        "name": "Heizungstausch: Luft/Wasser-Wärmepumpe",
        "category": "Heizungssystem",
        "unit": "kW_th (abgeleitet)",
        "default_qty_from": "derived_heat_load",
        "capex_unit_2021": 2000.0,
        "lifetime_y": 20,
        "affects": {"fuel_switch_to_hp": True, "scop": 3.0, "coverage_share": 1.0}
    }
]

# Utility: get index value
def get_index_value(year: str, quarter: str) -> float:
    try:
        return BAUPREISINDEX_INST[year][quarter]
    except KeyError:
        # fallback to closest available
        y = max(BAUPREISINDEX_INST.keys())
        q = list(BAUPREISINDEX_INST[y].keys())[-1]
        return BAUPREISINDEX_INST[y][q]

st.sidebar.header("Allgemeine Parameter")
colA, colB = st.sidebar.columns(2)
area_m2 = colA.number_input("Gebäudenutzfläche [m²]", min_value=0.0, value=2500.0, step=10.0)
units = colB.number_input("Wohneinheiten [Anz.]", min_value=0, value=40, step=1)
common_area_m2 = st.sidebar.number_input("Allgemeinflächen (Beleuchtung) [m²]", min_value=0.0, value=max(0.0, area_m2*0.1), step=5.0, help="Flächen in Treppenhaus, Technik, TG etc.")

window_ratio = st.sidebar.slider("Fensterflächenanteil an Nutzfläche [%]", 0, 80, 25) / 100.0

st.sidebar.markdown("---")
st.sidebar.subheader("Energie-Basisdaten (jährlich)")
e_el_kwh = st.sidebar.number_input("Strombezug [kWh/a]", min_value=0.0, value=120000.0, step=100.0)
e_heat_kwh = st.sidebar.number_input("Heizenergie (Gas/Öl/FW) [kWh/a]", min_value=0.0, value=450000.0, step=100.0)
carrier = st.sidebar.selectbox("Heizenergieträger", ["Erdgas", "Heizöl", "Fernwärme"])

st.sidebar.subheader("Energiepreise")
p_el = st.sidebar.number_input("Strompreis [€/kWh]", min_value=0.0, value=0.32, step=0.01)
p_heat = st.sidebar.number_input(f"{carrier} Preis [€/kWh]", min_value=0.0, value=0.12 if carrier!="Heizöl" else 0.11, step=0.01)

st.sidebar.subheader("Emissionsfaktoren [kg CO2/kWh]")
ef_el = st.sidebar.number_input("Strom", min_value=0.0, value=DEFAULT_EF["strom"], step=0.01)
ef_gas = st.sidebar.number_input("Erdgas", min_value=0.0, value=DEFAULT_EF["erdgas"], step=0.001)
ef_oil = st.sidebar.number_input("Heizöl", min_value=0.0, value=DEFAULT_EF["heizoel"], step=0.001)
ef_fw = st.sidebar.number_input("Fernwärme (Standortwert)", min_value=0.0, value=DEFAULT_EF["fernwaerme"], step=0.01)

st.sidebar.subheader("CO₂-Preis & Anwendbarkeit")
co2_price = st.sidebar.number_input("CO₂-Preis [€/t]", min_value=0.0, value=DEFAULT_CO2_PRICE_EUR_T, step=1.0)
apply_co2_el = st.sidebar.checkbox("CO₂-Preis auf Strom anwenden?", value=False)
apply_co2_heat = st.sidebar.checkbox(f"CO₂-Preis auf {carrier} anwenden?", value=True)

st.sidebar.markdown("---")
st.sidebar.subheader("Baupreisindex (Skalierung der Investitionskosten)")
colI1, colI2 = st.sidebar.columns(2)
year_target = colI1.selectbox("Zieljahr", list(BAUPREISINDEX_INST.keys()), index=len(BAUPREISINDEX_INST.keys())-1)
quarter_target = colI2.selectbox("Quartal", list(BAUPREISINDEX_INST[year_target].keys()), index=len(BAUPREISINDEX_INST[year_target].keys())-1)
index_target = get_index_value(year_target, quarter_target)
index_factor = index_target / INDEX_BASE
st.sidebar.write(f"**Index (Instandhaltung, {quarter_target}/{year_target}) = {index_target:.1f}** → Kosten-Faktor **{index_factor:.3f}**")

st.sidebar.markdown("---")
st.sidebar.subheader("PV-Parameter (falls PV-Maßnahme ausgewählt)")
pv_kwp = st.sidebar.number_input("PV-Größe [kWp]", min_value=0.0, value=100.0, step=1.0)
pv_yield = st.sidebar.number_input("Spez. Ertrag [kWh/kWp·a]", min_value=0.0, value=950.0, step=10.0)
pv_sc = st.sidebar.slider("Eigenverbrauchsanteil PV [%]", 0, 100, 60) / 100.0
pv_fit = st.sidebar.number_input("Einspeisevergütung [€/kWh]", min_value=0.0, value=0.08, step=0.01)

st.sidebar.markdown("---")
st.sidebar.subheader("Umlage (vereinfachtes Modell)")
rentable_area_m2 = st.sidebar.number_input("Wohnfläche (mietrelevant) [m²]", min_value=0.0, value=area_m2*0.9, step=10.0)
umlage_pct_general = st.sidebar.number_input("Umlageprozentsatz p.a. (§559 BGB) [%]", min_value=0.0, value=8.0, step=0.5) / 100.0
umlage_pct_heating = st.sidebar.number_input("Umlageprozentsatz p.a. (§559e BGB Heizung) [%]", min_value=0.0, value=10.0, step=0.5) / 100.0
cap_modernisierung_eur = st.sidebar.number_input("Kappungsgrenze Modernisierung [€/m² in 6 Jahren]", min_value=0.0, value=3.0, step=0.5)
cap_low_rent_eur = st.sidebar.number_input("Kappungsgrenze bei Miete <7 €/m² [€/m² in 6 Jahren]", min_value=0.0, value=2.0, step=0.5)
cap_heating_special_eur = st.sidebar.number_input("Sonder-Kappungsgrenze Heizung (§559e) [€/m² in 6 Jahren]", min_value=0.0, value=0.5, step=0.1)
avg_rent_eur_m2 = st.sidebar.number_input("Aktuelle Nettokaltmiete [€/m²]", min_value=0.0, value=9.0, step=0.1)

# ------------------------------
# Derived quantities
# ------------------------------
window_area_m2 = area_m2 * window_ratio
derived = {
    "area": area_m2,
    "units": units,
    "common_area": common_area_m2,
    "window_ratio": window_ratio,
    "window_area_m2": window_area_m2,
    "pv_kwp": pv_kwp,
    "pv_specific_yield": pv_yield,
}

# Derive approximate peak heat load from annual heat energy (full-load hours heuristic)
flh = st.sidebar.number_input("Vollbenutzungsstunden Heizung [h/a] (Heuristik)", min_value=500, max_value=4000, value=2000, step=50)
derived_heat_load_kw = e_heat_kwh / max(1, flh)
derived["derived_heat_load"] = derived_heat_load_kw

# ------------------------------
# Baseline KPIs
# ------------------------------
ef_heat = {"Erdgas": ef_gas, "Heizöl": ef_oil, "Fernwärme": ef_fw}[carrier]
co2_el_t = e_el_kwh * ef_el / 1000.0
co2_heat_t = e_heat_kwh * ef_heat / 1000.0
cost_el = e_el_kwh * p_el
cost_heat = e_heat_kwh * p_heat

co2_cost_baseline = 0.0
if apply_co2_el:
    co2_cost_baseline += co2_el_t * co2_price
if apply_co2_heat:
    co2_cost_baseline += co2_heat_t * co2_price

baseline = {
    "Energie Strom [kWh/a]": e_el_kwh,
    "Energie Heizung [kWh/a]": e_heat_kwh,
    "Kosten Strom [€/a]": cost_el,
    "Kosten Heizung [€/a]": cost_heat,
    "Emissionen Strom [tCO2/a]": co2_el_t,
    "Emissionen Heizung [tCO2/a]": co2_heat_t,
    "CO2-Kosten [€/a]": co2_cost_baseline,
    "Gesamtkosten [€/a]": cost_el + cost_heat + co2_cost_baseline
}

# ------------------------------
# Measures editor
# ------------------------------
st.title("Erhebungsbogen & Szenario-App – Energetische Sanierung")

tab1, tab2, tab3 = st.tabs(["1) Erhebungsbogen & Basis", "2) Maßnahmen", "3) Ergebnisse & Szenarien"])

with tab1:
    st.subheader("Basisdaten & Kennzahlen")
    col1, col2, col3 = st.columns(3)
    col1.metric("Nutzfläche [m²]", f"{area_m2:,.0f}".replace(",", "."))
    col2.metric("Wohneinheiten [#]", f"{units}")
    col3.metric("Fensteranteil [%]", f"{window_ratio*100:.0f}")
    st.markdown("**Energie-Basis**")
    df_base = pd.DataFrame.from_dict(baseline, orient="index", columns=["Wert"])
    st.dataframe(df_base)

    st.markdown("**Hinweis:** Emissionsfaktoren, CO₂-Preis und Energiepreise sind Eingangsparameter und sollten projektspezifisch belegt werden.")

# Build editable measures dataframe
def build_measures_df():
    rows = []
    for m in MEASURES:
        qty = 0.0
        if m["default_qty_from"] == "area":
            qty = area_m2
        elif m["default_qty_from"] == "units":
            qty = units
        elif m["default_qty_from"] == "common_area":
            qty = common_area_m2
        elif m["default_qty_from"] == "window_ratio":
            qty = window_area_m2
        elif m["default_qty_from"] == "pv_kwp":
            qty = pv_kwp
        elif m["default_qty_from"] == "derived_heat_load":
            qty = derived_heat_load_kw
        rows.append({
            "Aktiv": False,
            "Code": m["code"],
            "Maßnahme": m["name"],
            "Kategorie": m["category"],
            "Einheit": m["unit"],
            "Menge": float(qty),
            "Capex/Einheit @Index100 [€]": float(m["capex_unit_2021"]),
            "Lebensdauer [a]": int(m["lifetime_y"]),
            # defaults for savings and specifics
            "Einsparung Heizung [%]": float(m["affects"].get("heating_pct", 0.0) * 100.0),
            "Einsparung Strom [%]": float(m["affects"].get("electricity_pct", 0.0) * 100.0),
            "Stromanteil für LED [% vom Strom]": float(m["affects"].get("electricity_share_of_total", 0.0) * 100.0),
            "LED-Reduktion [% dieses Anteils]": float(m["affects"].get("electricity_pct_of_share", 0.0) * 100.0),
            "WRG-Zusatzstrom [kWh/Wohneinheit]": float(m["affects"].get("electricity_extra_kwh_per_unit", 0.0)),
            "HP SCOP": float(m["affects"].get("scop", 0.0)),
            "HP Abdeckung Wärme [%]": float(m["affects"].get("coverage_share", 0.0) * 100.0),
            "PV-spez. Ertrag [kWh/kWp]": float(m["affects"].get("pv_specific_yield", pv_yield) ),
            "PV-EV-Anteil [%]": float(m["affects"].get("self_consumption_share", pv_sc) * 100.0),
            "PV-Einspeise [€/kWh]": float(m["affects"].get("feed_in_tariff_eur_kwh", pv_fit))
        })
    return pd.DataFrame(rows)

if "measures_df" not in st.session_state:
    st.session_state["measures_df"] = build_measures_df()

with tab2:
    st.subheader("Maßnahmenkatalog (bearbeitbar)")
    st.markdown("Aktivieren Sie Maßnahmen, passen Sie Mengen, Einsparannahmen und Capex an. Investitionskosten werden mit dem ausgewählten **Baupreisindex (Instandhaltung)** skaliert.")
    edited_df = st.data_editor(
        st.session_state["measures_df"],
        num_rows="fixed",
        key="measures_editor",
        hide_index=True,
        column_config={
            "Aktiv": st.column_config.CheckboxColumn(),
            "Menge": st.column_config.NumberColumn(format="%.2f", min_value=0),
            "Einsparung Heizung [%]": st.column_config.NumberColumn(format="%.2f", min_value=0, max_value=100),
            "Einsparung Strom [%]": st.column_config.NumberColumn(format="%.2f", min_value=0, max_value=100),
            "Stromanteil für LED [% vom Strom]": st.column_config.NumberColumn(format="%.1f", min_value=0, max_value=100),
            "LED-Reduktion [% dieses Anteils]": st.column_config.NumberColumn(format="%.1f", min_value=0, max_value=100),
            "WRG-Zusatzstrom [kWh/Wohneinheit]": st.column_config.NumberColumn(format="%.1f", min_value=0),
            "HP SCOP": st.column_config.NumberColumn(format="%.2f", min_value=0.1, max_value=8.0, help="Saisonale Leistungszahl"),
            "HP Abdeckung Wärme [%]": st.column_config.NumberColumn(format="%.1f", min_value=0, max_value=100),
            "PV-spez. Ertrag [kWh/kWp]": st.column_config.NumberColumn(format="%.1f", min_value=0),
            "PV-EV-Anteil [%]": st.column_config.NumberColumn(format="%.1f", min_value=0, max_value=100),
            "PV-Einspeise [€/kWh]": st.column_config.NumberColumn(format="%.3f", min_value=0)
        },
        use_container_width=True
    )
    st.session_state["measures_df"] = edited_df

# ------------------------------
# Simulation engine
# ------------------------------
def simulate(measures_df: pd.DataFrame):
    # Start with baseline
    el = e_el_kwh
    heat = e_heat_kwh
    # cumulative multiplicative reductions
    heat_factor = 1.0
    el_factor = 1.0
    extra_el_kwh = 0.0
    pv_self_kwh = 0.0
    pv_feed_kwh = 0.0
    hp_active = False
    hp_scop = 3.0
    hp_coverage = 0.0
    total_capex = 0.0
    ann_capex_general = 0.0
    ann_capex_heating = 0.0

    for _, row in measures_df.iterrows():
        if not bool(row.get("Aktiv", False)):
            continue
        code = row["Code"]
        qty = float(row["Menge"] or 0.0)
        capex_unit_base = float(row["Capex/Einheit @Index100 [€]"] or 0.0)
        capex = qty * capex_unit_base * (index_factor)
        total_capex += capex

        # Umlage-Typ identifizieren (vereinfacht)
        if code == "heat_pump_aw":
            ann_capex_heating += capex * umlage_pct_heating
        else:
            ann_capex_general += capex * umlage_pct_general

        # Savings modeling
        if code == "led_lighting":
            share = (row["Stromanteil für LED [% vom Strom]"] or 0.0) / 100.0
            red = (row["LED-Reduktion [% dieses Anteils]"] or 0.0) / 100.0
            el_factor *= (1.0 - share * red)
        elif code == "vent_wrg":
            heat_factor *= (1.0 - (row["Einsparung Heizung [%]"] or 0.0) / 100.0)
            extra_el_kwh += float(row["WRG-Zusatzstrom [kWh/Wohneinheit]"] or 0.0) * qty
        elif code == "pv_system":
            spec = float(row["PV-spez. Ertrag [kWh/kWp]"] or pv_yield)
            sc = (row["PV-EV-Anteil [%]"] or 0.0) / 100.0
            pv_prod = spec * qty
            pv_self_kwh += pv_prod * sc
            pv_feed_kwh += pv_prod * (1.0 - sc)
            # keine direkte Veränderung von el_factor, wir ziehen später ab
        elif code == "heat_pump_aw":
            hp_active = True
            hp_scop = float(row["HP SCOP"] or 3.0)
            hp_coverage = (row["HP Abdeckung Wärme [%]"] or 0.0) / 100.0
        else:
            # generic percentage savings
            h_pct = (row["Einsparung Heizung [%]"] or 0.0) / 100.0
            e_pct = (row["Einsparung Strom [%]"] or 0.0) / 100.0
            heat_factor *= (1.0 - h_pct)
            el_factor *= (1.0 - e_pct)

    # Apply multiplicative reductions
    heat_after = heat * heat_factor
    el_after = el * el_factor

    # Apply heat pump fuel switch after envelope/optimization effects
    hp_el_kwh = 0.0
    if hp_active and hp_coverage > 0.0 and hp_scop > 0.1:
        covered_heat = heat_after * hp_coverage
        hp_el_kwh = covered_heat / hp_scop
        heat_after = heat_after * (1.0 - hp_coverage)  # Rest ggf. mit altem Carrier
        el_after += hp_el_kwh

    # Apply PV self-consumption to reduce purchased electricity
    el_after = max(0.0, el_after - pv_self_kwh)

    # Add extra electricity consumption (e.g. WRG)
    el_after += extra_el_kwh

    # Costs & emissions after
    cost_el_after = el_after * p_el - pv_feed_kwh * float(measures_df.loc[measures_df["Code"]=="pv_system", "PV-Einspeise [€/kWh]"].values[0] if "pv_system" in measures_df["Code"].values else 0.0)
    cost_heat_after = heat_after * p_heat
    co2_el_after_t = el_after * ef_el / 1000.0
    co2_heat_after_t = heat_after * ef_heat / 1000.0

    co2_cost_after = 0.0
    if apply_co2_el:
        co2_cost_after += co2_el_after_t * co2_price
    if apply_co2_heat:
        co2_cost_after += co2_heat_after_t * co2_price

    totals = {
        "capex_total": total_capex,
        "ann_capex_general": ann_capex_general,
        "ann_capex_heating": ann_capex_heating,
        "el_after": el_after,
        "heat_after": heat_after,
        "hp_el_kwh": hp_el_kwh,
        "pv_self_kwh": pv_self_kwh,
        "pv_feed_kwh": pv_feed_kwh,
        "cost_el_after": cost_el_after,
        "cost_heat_after": cost_heat_after,
        "co2_el_after_t": co2_el_after_t,
        "co2_heat_after_t": co2_heat_after_t,
        "co2_cost_after": co2_cost_after
    }
    return totals

with tab3:
    st.subheader("Ergebnisse & Szenarien")
    results = simulate(st.session_state["measures_df"])

    # Summaries
    cost_after_total = results["cost_el_after"] + results["cost_heat_after"] + results["co2_cost_after"]
    savings_eur_pa = baseline["Gesamtkosten [€/a]"] - cost_after_total
    co2_savings_t = (baseline["Emissionen Strom [tCO2/a]"] + baseline["Emissionen Heizung [tCO2/a]"]) - (results["co2_el_after_t"] + results["co2_heat_after_t"])

    # Umlage – vereinfachte Abbildung §559 / §559e (Kappungsgrenzen je 6 Jahre)
    cap_limit = cap_low_rent_eur if avg_rent_eur_m2 < 7.0 else cap_modernisierung_eur
    # jährliche Obergrenze pro m²: Cap / 6
    annual_cap_per_m2 = cap_limit / 6.0
    annual_cap_heating_per_m2 = cap_heating_special_eur / 6.0

    ann_umlage_general = min(results["ann_capex_general"] / max(1.0, rentable_area_m2), annual_cap_per_m2) * rentable_area_m2
    ann_umlage_heating = min(results["ann_capex_heating"] / max(1.0, rentable_area_m2), annual_cap_heating_per_m2) * rentable_area_m2
    ann_umlage_total = ann_umlage_general + ann_umlage_heating

    landlord_net_savings = savings_eur_pa + ann_umlage_total
    simple_payback_y = results["capex_total"] / max(1e-9, landlord_net_savings) if landlord_net_savings > 0 else np.inf

    cols = st.columns(4)
    cols[0].metric("CAPEX gesamt [€]", f"{results['capex_total']:,.0f}".replace(",", "."))
    cols[1].metric("Einsparung p.a. [€]", f"{savings_eur_pa:,.0f}".replace(",", "."))
    cols[2].metric("CO₂-Einsparung [t/a]", f"{co2_savings_t:,.2f}".replace(",", "."))
    cols[3].metric("Amortisation (vereinfachte) [a]", "∞" if np.isinf(simple_payback_y) else f"{simple_payback_y:,.1f}".replace(",", "."))

    st.markdown("### Kosten & Emissionen – Vorher/Nachher")
    df_comp = pd.DataFrame({
        "Kategorie": ["Stromkosten", "Heizkosten", "CO₂-Kosten", "Gesamt"],
        "Vorher [€/a]": [baseline["Kosten Strom [€/a]"], baseline["Kosten Heizung [€/a]"], baseline["CO2-Kosten [€/a]"], baseline["Gesamtkosten [€/a]"]],
        "Nachher [€/a]": [results["cost_el_after"], results["cost_heat_after"], results["co2_cost_after"], cost_after_total]
    })
    st.dataframe(df_comp, use_container_width=True)

    st.markdown("### Strom- und Heizenergie – Vorher/Nachher [kWh/a]")
    df_energy = pd.DataFrame({
        "Energie": ["Strom", "Heizung"],
        "Vorher": [e_el_kwh, e_heat_kwh],
        "Nachher": [results["el_after"], results["heat_after"]]
    })
    fig1 = px.bar(df_energy, x="Energie", y=["Vorher", "Nachher"], barmode="group", title="Energieverbrauch [kWh/a]")
    st.plotly_chart(fig1, use_container_width=True)

    st.markdown("### Waterfall: Jährliche Netto-Wirkung [€]")
    wf = pd.DataFrame({
        "Stufe": ["Baseline-Kosten", "– Einsparungen Energie/CO₂", "+ Umlage (Mieter)", "Gesamt Nachher"],
        "Wert": [baseline["Gesamtkosten [€/a]"], -savings_eur_pa, ann_umlage_total, cost_after_total]
    })
    
import plotly.graph_objects as go

wf = pd.DataFrame({
    "Stufe": ["Baseline-Kosten", "– Einsparungen Energie/CO₂", "+ Umlage (Mieter)", "Gesamt Nachher"],
    "Wert": [baseline["Gesamtkosten [€/a]"], -savings_eur_pa, ann_umlage_total, cost_after_total]
})

fig2 = go.Figure(go.Waterfall(
    name="Kostenwirkung",
    orientation="v",
    measure=["absolute", "relative", "relative", "total"],
    x=wf["Stufe"],
    y=wf["Wert"],
    connector={"line": {"color": "rgb(63, 63, 63)"}}
))

fig2.update_layout(title="Kostenwirkung p.a.", waterfallgap=0.3)
st.plotly_chart(fig2, use_container_width=True)

    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### Detail: Umlage (vereinfachtes Modell)")
    st.write(f"Allg. Umlage (§559, {umlage_pct_general*100:.1f}% p.a.) begrenzt auf {annual_cap_per_m2:.2f} €/m²·a, Heizung (§559e, {umlage_pct_heating*100:.1f}% p.a.) begrenzt auf {annual_cap_heating_per_m2:.2f} €/m²·a.")
    df_umlage = pd.DataFrame({
        "Komponente": ["Umlage allg.", "Umlage Heizung", "Umlage gesamt"],
        "€/a": [ann_umlage_general, ann_umlage_heating, ann_umlage_total],
        "€/m²·a": [ann_umlage_general/max(1.0, rentable_area_m2), ann_umlage_heating/max(1.0, rentable_area_m2), ann_umlage_total/max(1.0, rentable_area_m2)]
    })
    st.dataframe(df_umlage, use_container_width=True)

    st.markdown("### Hinweise")
    st.info(
        "• Investitionskosten werden anhand des Destatis **Baupreisindex (Instandhaltung, 2021=100)** skaliert.\n"
        "• Einsparannahmen sind Richtwerte und müssen objektbezogen validiert werden (DIN EN 16247/DIN V 18599).\n"
        "• Umlage-Berechnungen bilden §559/§559e BGB als **vereinfachte** Obergrenzen ab – rechtliche Prüfung erforderlich.\n"
        "• PV-Logik: Eigenverbrauch reduziert Strombezug; Überschuss wird mit der angegebenen Vergütung saldiert."
    )

st.markdown("---")
with st.expander("Quellen (Kurzüberblick)"):
    st.markdown("""
- **Baupreisindex (Instandhaltung, 2021=100)**: Destatis, Konjunkturindikator *bpr210* (Stand 10.07.2025).
- **CO₂-Preis (BEHG)**: DEHSt/Bundesregierung – 2024: 45 €/t, 2025: 55 €/t.
- **Emissionsfaktor Strommix**: UBA – 2024: 363 g CO₂/kWh (Inlandsverbrauch).
- **Erdgas/Heizöl Emissionsfaktoren**: BMWK/BAFA Richtwerte.
    """)
