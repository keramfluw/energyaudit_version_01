
# Energetische Sanierung – Erhebungsbogen & ROI-App (Streamlit)

Diese App liefert:
- **Erhebungsbogen** für Gebäudedaten mit automatischen **Kennzahlen** (Kosten, Emissionen).
- Einen **Maßnahmenkatalog** (bearbeitbar) mit **Investitionskosten** (via **Baupreisindex** skaliert), **Einsparungen** und **Lebensdauern**.
- **Szenario-Rechnung** inkl. **CO₂-Preis**, **Umlage auf Mieter (§559/§559e BGB, vereinfacht)**, **Amortisation**, **PV-Eigenverbrauch** sowie **Kombinationseffekten** (multiplikative Einsparungen, Brennstoffwechsel bei Wärmepumpe).

> **Hinweis/Disclaimer:** Rechtliche Parameter (Umlage, Kappungsgrenzen, Förderanrechnung etc.) sind **vereinfacht** abgebildet. Die App ersetzt **keine** Rechtsberatung. Eingangsgrößen (Energiepreise, Emissionsfaktoren, PV-Erträge etc.) sind **projektspezifisch** zu validieren.

---

## Installation

```bash
# 1) virtuelles Umfeld (empfohlen)
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2) Pakete
pip install -r requirements.txt

# 3) Start
streamlit run app.py
```

---

## Eingaben – Erhebungsbogen (Auswahl)
- Fläche [m²], Wohneinheiten, Fensterflächenanteil
- Energieverbräuche (Strom, Heizung) und **Energiepreise**
- **Emissionsfaktoren** (Voreinstellungen: UBA/BMWK/BAFA – anpassbar)
- **CO₂-Preis** (BEHG), Anwendbarkeit je Energieträger
- **Baupreisindex** (*Destatis Instandhaltung, 2021=100*, Quartal wählbar) zur **Skalierung der CAPEX**
- **PV-Parameter** (kWp, spezifischer Ertrag, Eigenverbrauch, Einspeisevergütung)
- **Umlageparameter** (Vereinfachung der §§ 559 & 559e BGB inkl. Kappungsgrenzen)

---

## Maßnahmenkatalog (editierbar)
Voreingestellt (typische Richtwerte, **bitte objektbezogen prüfen**):
- **Hülle:** Dach-/Außenwand-/Kellerdecken-Dämmung, Fenstertausch (3-fach)
- **Heizung/Regelung:** Hydraulischer Abgleich, Hocheffizienzpumpen, TWW-Zirkulationsoptimierung
- **Lüftung:** Dezentrale Lüftung mit WRG
- **Digital:** Gebäudeautomation/EMS-Optimierung
- **Erzeugung:** PV-Anlage (Eigenverbrauch & Einspeisung)
- **Systemwechsel:** Luft/Wasser-Wärmepumpe (SCOP, Abdeckungsgrad)

Jede Maßnahme besitzt:
- **Menge** (Einheit je Maßnahme), **Capex/Einheit** (Basis *Index=100*), **Lebensdauer**
- **Einsparannahmen** (separat für Heizung/Strom) oder **Spezial-Parameter** (z. B. SCOP, PV-Ertrag/Eigenverbrauch)
- **Umlage-Typ** (allgemein vs. Heizungstausch)

**Kombinationseffekte:** Einsparungen werden **multiplikativ** angewandt; Wärmepumpe verschiebt Rest-Wärmebedarf in **Strom** (kWh\_el = kWh\_th / SCOP) und wird nach Hüll-/Betriebsmaßnahmen berechnet. PV reduziert **Netto-Strombezug**, Überschuss wird mit der Vergütung saldiert.

---

## Kennzahlen & Auswertungen
- **Vorher/Nachher**: Energie [kWh/a], Kosten [€/a], Emissionen [t/a], **CO₂-Kosten**
- **CAPEX** (Index-skaliert) & **vereinfachte Umlage** (jährl. Umlage begrenzt durch **Kappungsgrenzen je 6 Jahre**; Heizung §559e: 0,50 €/m² in 6 J.)
- **Amortisation** (vereinfachte) für Vermieter: CAPEX / (Energie- & CO₂-Einsparungen + Umlage)
- **Charts**: Balkendiagramme und Waterfall

---

## Datenvalidierung
- Nicht-negative Eingaben, Ranges in Editoren (0–100 % etc.)
- Index-Skalierung: **Faktor = Index(Zielquartal) / 100**
- Heizlast-Heuristik: **Vollbenutzungsstunden** (Standard 2 000 h/a) → kW\_th ≈ Jahreswärme / VBZ

---

## Quellen (Stand: 15.08.2025)
- **Baupreisindex (Instandhaltung, 2021=100)** – Destatis, Konjunkturindikator *bpr210*, Quartalswerte (z. B. 2025 Q2: 136,4).  
  Siehe: https://www.destatis.de/DE/Themen/Wirtschaft/Konjunkturindikatoren/Preise/bpr210.html
- **Neubau-Index (Wohngebäude)** – Destatis Pressemitteilungen (z. B. 10.07.2025: +3,2 % ggü. Mai 2024).
- **CO₂-Preis (BEHG)** – DEHSt/Bundesregierung: 2024 = 45 €/t, 2025 = 55 €/t; ab 2026 Versteigerung.
- **Emissionsfaktor Strommix** – UBA: 2024 = 363 g CO₂/kWh (Inlandsverbrauch).
- **Emissionsfaktoren Brennstoffe** – BMWK/BAFA (z. B. Erdgas 0,20088 kg CO₂/kWh; Heizöl 0,2664 kg CO₂/kWh).
- **Umlage Recht** – § 559 BGB (8 % p. a. + Kappungsgrenzen 3/2 €/m² in 6 J.), § 559e BGB (Heizung, Sonderkappungsgrenze 0,50 €/m² in 6 J.) – **juristisch prüfen**.

> Für belastbare Förder-/Steuer-Effekte (KfW/BEG, AfA/Sonder-AfA) erweitern Sie das Modell um Cashflows & Diskontierung (WACC).

---

## Anpassungsideen
- Import eigener **Maßnahmenbibliotheken** (CSV)
- **DIN V 18599**-basierte Bilanzierung und Kalibrierung mit 15-min-Lastgängen
- Einbindung realer **Baupreisindex-Zeitreihen** per API/CSV
- **NPV/IRR** je Maßnahme & Portfolio
- **Tarifsimulation** (HT/NT, dynamische Preise), **Demand Response**

Viel Erfolg!
