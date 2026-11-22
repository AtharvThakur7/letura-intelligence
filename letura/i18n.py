"""Minimal English/German UI translation layer.

Call ``t("Some English UI text")`` anywhere a user-facing string is built.
It returns the German translation when the active language is "de", and the
original English text otherwise (including when no translation exists yet).

Dataframe/column keys that the code also uses internally (e.g. to index a
DataFrame) are intentionally left untranslated so translating the UI never
changes program logic; only display-only labels, headers, captions, help
text and messages are covered here.
"""
from __future__ import annotations

import streamlit as st

LANGUAGES = {"en": "English", "de": "Deutsch"}

TRANSLATIONS: dict[str, str] = {
    # ---- navigation / page titles
    "Home": "Start",
    "Market": "Markt",
    "Neighbourhoods": "Stadtteile",
    "Properties": "Immobilien",
    "Official rents": "Offizielle Mieten",
    "Letura AI": "Letura AI",

    # ---- sidebar / filters
    "Filters": "Filter",
    "Period": "Zeitraum",
    "Neighbourhood": "Stadtteil",
    "Property type": "Immobilientyp",
    "Rooms": "Zimmer",
    "Living area (m²)": "Wohnfläche (m²)",
    "Year built": "Baujahr",
    "Must have": "Ausstattung",
    "Clear filters": "Filter zurücksetzen",
    "Dark mode": "Dunkelmodus",
    "Language": "Sprache",
    "All": "Alle",
    "Any": "Beliebig",
    "Demo version · AI answers are pre-generated.": "Demoversion · KI-Antworten sind vorab generiert.",
    "Showing **{shown}** of {total} listings · {desc}":
        "Zeige **{shown}** von {total} Anzeigen · {desc}",
    "Capped at {max} m²; drag to the far right to include larger flats.":
        "Begrenzt auf {max} m²; zum Einschließen größerer Wohnungen ganz nach rechts ziehen.",
    "Only flats with a known year are kept when this is narrowed.":
        "Beim Eingrenzen werden nur Wohnungen mit bekanntem Baujahr berücksichtigt.",
    "Letura Intelligence · Historical asking rents 2018–2020 and official 2025 reference data · "
    "Not current prices and not a legal rent determination.":
        "Letura Intelligence · Historische Angebotsmieten 2018–2020 und offizielle Referenzdaten 2025 · "
        "Keine aktuellen Preise und keine rechtsverbindliche Mietfestsetzung.",

    # ---- amenities
    "Balcony": "Balkon",
    "Garden": "Garten",
    "Lift": "Aufzug",
    "Fitted kitchen": "Einbauküche",
    "New construction": "Neubau",
    "Cellar": "Keller",
    "With": "Mit",
    "Without": "Ohne",

    # ---- filter describe()
    "No filters (all 3,759 Hamburg listings)": "Keine Filter (alle 3.759 Hamburger Anzeigen)",
    "Snapshot": "Zeitpunkt",
    "Type": "Typ",
    "Area": "Fläche",
    "Built": "Baujahr",
    "Amenities": "Ausstattung",

    # ---- shared components
    "No listings match the current filters. Widen or reset the filters.":
        "Keine Anzeigen entsprechen den aktuellen Filtern. Filter erweitern oder zurücksetzen.",
    "Download CSV": "CSV herunterladen",
    "Listings": "Anzeigen",
    "Not stated": "Nicht angegeben",
    "Historical advertised cold rents (ImmoScout24 snapshots, Sep 2018 – Feb 2020). "
    "Independent snapshots – not the same properties tracked over time and not current 2026 rents.":
        "Historische Angebots-Kaltmieten (ImmoScout24-Zeitpunkte, Sep. 2018 – Feb. 2020). "
        "Unabhängige Zeitpunkte – nicht dieselben Objekte über die Zeit verfolgt und keine aktuellen Mieten von 2026.",
    "These datasets differ in reference period, population and methodology. This comparison is contextual, "
    "not a same-period market premium or legal rent determination.":
        "Diese Datensätze unterscheiden sich in Referenzzeitraum, Grundgesamtheit und Methodik. Dieser Vergleich "
        "dient dem Kontext und ist kein zeitgleicher Marktaufschlag und keine rechtsverbindliche Mietfestsetzung.",

    # ---- p0 home
    "Hamburg's rental market, made simple.": "Hamburgs Mietmarkt, einfach erklärt.",
    "See what flats cost in every neighbourhood, compare with official reference rents, "
    "and ask questions in plain English.":
        "Sehen Sie, was Wohnungen in jedem Stadtteil kosten, vergleichen Sie mit offiziellen Referenzmieten "
        "und stellen Sie Fragen in einfacher Sprache.",
    "Hamburg rental market intelligence": "Hamburgs Mietmarkt-Intelligenz",
    "The rental market intelligence platform for Hamburg real estate.":
        "Die Mietmarkt-Intelligenzplattform für Hamburger Immobilien.",
    "Letura Intelligence turns raw listing data into pricing benchmarks, neighbourhood comparisons "
    "and official-rent compliance checks — so landlords, investors and analysts can price with "
    "confidence and back every decision with evidence.":
        "Letura Intelligence verwandelt rohe Anzeigendaten in Preis-Benchmarks, Stadtteilvergleiche und "
        "Abgleiche mit dem offiziellen Mietenspiegel — damit Vermieter, Investoren und Analysten mit "
        "Sicherheit kalkulieren und jede Entscheidung mit Daten belegen können.",
    "What Letura Intelligence gives you": "Das bietet Ihnen Letura Intelligence",
    "Six tools, one dataset — each one answers a different question a landlord, investor or analyst would ask.":
        "Sechs Werkzeuge, ein Datensatz — jedes beantwortet eine andere Frage, die Vermieter, Investoren "
        "oder Analysten stellen.",
    "One executive view of the whole market: headline KPIs, trend sparklines and auto-generated insights.":
        "Eine Übersicht für den gesamten Markt: zentrale Kennzahlen, Trend-Sparklines und automatisch "
        "generierte Erkenntnisse.",
    "The city-wide picture: price trends, distribution and property mix at a glance.":
        "Der stadtweite Überblick: Preistrends, Verteilung und Immobilienmix auf einen Blick.",
    "Rank, compare and benchmark every Hamburg neighbourhood and district.":
        "Jeden Hamburger Stadtteil und Bezirk einordnen, vergleichen und bewerten.",
    "See how size, age, type and features move the price per m².":
        "Sehen Sie, wie Größe, Alter, Typ und Ausstattung den Preis pro m² beeinflussen.",
    "Benchmark advertised rents against Hamburg's official 2025 Mietenspiegel.":
        "Angebotsmieten mit Hamburgs offiziellem Mietenspiegel 2025 vergleichen.",
    "Get a straight answer in plain language, backed by the real numbers behind it.":
        "Erhalten Sie eine klare Antwort in einfacher Sprache, belegt mit den echten Zahlen dahinter.",
    "Open": "Öffnen",
    "Hamburg listings": "Hamburger Anzeigen",
    "Median asking rent": "Median-Angebotsmiete",
    "Periods covered 2018–2020": "Erfasste Zeiträume 2018–2020",
    "See the market overview": "Zur Marktübersicht",
    "Compare neighbourhoods": "Stadtteile vergleichen",
    "Ask the AI analyst": "Die KI-Analystin fragen",
    "Try a question": "Eine Frage ausprobieren",
    "Question": "Frage",
    "Thinking…": "Denke nach…",
    "Hamburg at a glance": "Hamburg auf einen Blick",
    "Bigger box = more listings · darker = higher rent. Click a district to zoom in.":
        "Größeres Feld = mehr Anzeigen · dunkler = höhere Miete. Bezirk anklicken, um hineinzuzoomen.",
    "Based on historical asking rents (2018–2020) and official 2025 reference rents. "
    "Not current prices and not a legal rent determination.":
        "Basierend auf historischen Angebotsmieten (2018–2020) und offiziellen Referenzmieten 2025. "
        "Keine aktuellen Preise und keine rechtsverbindliche Mietfestsetzung.",

    # ---- p6 dashboard
    "Dashboard": "Dashboard",
    "The Hamburg rental market at a glance — the numbers that matter most, in one view.":
        "Der Hamburger Mietmarkt auf einen Blick — die wichtigsten Kennzahlen in einer Ansicht.",
    "Median Asking Rent": "Median-Angebotsmiete",
    "The core pricing benchmark: the midpoint of advertised cold rent per square metre "
    "across listings in view. The change compares the first to the last snapshot shown.":
        "Der zentrale Preis-Benchmark: der Mittelwert der Angebots-Kaltmiete pro Quadratmeter über die "
        "angezeigten Anzeigen. Die Veränderung vergleicht den ersten mit dem letzten gezeigten Zeitpunkt.",
    "Active Listings": "Aktive Anzeigen",
    "Live inventory matching your current filters — the size of the market you're viewing.":
        "Aktueller Bestand gemäß Ihren Filtern — die Größe des Marktausschnitts, den Sie betrachten.",
    "Avg. Unit Size": "Ø Wohnungsgröße",
    "Average living area across listings in view — a quick read on typical unit size in this market.":
        "Durchschnittliche Wohnfläche der angezeigten Anzeigen — ein schneller Blick auf die typische "
        "Wohnungsgröße in diesem Markt.",
    "Neighbourhoods Covered": "Abgedeckte Stadtteile",
    "Distinct Hamburg neighbourhoods represented in view — breadth of market coverage.":
        "Verschiedene Hamburger Stadtteile in der aktuellen Ansicht — Breite der Marktabdeckung.",
    "Location-Quality Match Rate": "Lagequalität-Zuordnungsrate",
    "Share of listings matched to Hamburg's official street-level location-quality register — "
    "data reliability for location-based pricing.":
        "Anteil der Anzeigen, die der offiziellen straßengenauen Lagequalitätsliste Hamburgs zugeordnet "
        "wurden — Datenverlässlichkeit für lagebasierte Preisbildung.",
    "Premium vs. Official Benchmark": "Aufschlag ggü. offiziellem Benchmark",
    "Median gap between advertised asking rents and the 2025 Mietenspiegel reference for "
    "matching construction periods — how the market prices above or below the official "
    "benchmark. Contextual only — different periods and methods.":
        "Mediane Differenz zwischen Angebotsmieten und der Mietenspiegel-Referenz 2025 für übereinstimmende "
        "Baualtersklassen — zeigt, ob der Markt über oder unter dem offiziellen Benchmark liegt. Nur zur "
        "Einordnung — unterschiedliche Zeiträume und Methoden.",
    "What the data tells us": "Was die Daten zeigen",
    "Median rent moved **{delta:+.1f}%** from {first} to {last}.":
        "Die Median-Miete veränderte sich um **{delta:+.1f}%** von {first} bis {last}.",
    "**{top}** is the most expensive neighbourhood in view at {top_v}; "
    "**{bottom}** is the most affordable at {bottom_v}.":
        "**{top}** ist der teuerste Stadtteil in der Ansicht mit {top_v}; "
        "**{bottom}** ist am günstigsten mit {bottom_v}.",
    "Advertised rents run **{gap} €/m² {direction}** the official 2025 reference rent for "
    "comparable flats, on average.":
        "Angebotsmieten liegen im Schnitt **{gap} €/m² {direction}** der offiziellen Referenzmiete 2025 "
        "für vergleichbare Wohnungen.",
    "above": "über",
    "below": "unter",
    "The market, combined": "Der Markt im Überblick",
    "Most expensive neighbourhoods (€/m²)": "Teuerste Stadtteile (€/m²)",
    "Historical rents vs. official 2025 reference": "Historische Mieten vs. offizielle Referenz 2025",
    "Historical asking rent (2018–20)": "Historische Angebotsmiete (2018–20)",
    "Official reference (2025)": "Offizielle Referenz (2025)",
    "Official reference data is unavailable right now.": "Offizielle Referenzdaten sind derzeit nicht verfügbar.",
    "Explore further": "Weiter erkunden",

    # ---- p1 market overview
    "Market overview": "Marktübersicht",
    "How advertised rents look across Hamburg.": "Wie Angebotsmieten in ganz Hamburg aussehen.",
    "Median rent": "Median-Miete",
    "Average rent": "Durchschnittsmiete",
    "Typical size": "Typische Größe",
    "{n} neighbourhoods": "{n} Stadtteile",
    "cold rent per m²": "Kaltmiete pro m²",
    "pulled up by luxury flats": "durch Luxuswohnungen nach oben verzerrt",
    "{n} rooms": "{n} Zimmer",
    "Number of listings matching your filters.": "Anzahl der Anzeigen, die Ihren Filtern entsprechen.",
    "Middle value of advertised base rent ÷ living area. Excludes service charges and heating.":
        "Mittelwert aus Angebots-Grundmiete ÷ Wohnfläche. Ohne Nebenkosten und Heizung.",
    "Average; a few expensive listings raise it above the median.":
        "Durchschnitt; einige teure Anzeigen heben ihn über den Median.",
    "Median living area and number of rooms.": "Median der Wohnfläche und Zimmerzahl.",
    "Median rent over time (€/m²)": "Median-Miete über die Zeit (€/m²)",
    "How rents are spread (€/m²)": "Verteilung der Mieten (€/m²)",
    "Flat sizes (m²)": "Wohnungsgrößen (m²)",
    "Property types": "Immobilientypen",
    "Advertised cold rents from four snapshots between Sep 2018 and Feb 2020. Each snapshot has different "
    "listings, so this is not the same flats over time, and not current prices.":
        "Angebots-Kaltmieten aus vier Zeitpunkten zwischen Sep. 2018 und Feb. 2020. Jeder Zeitpunkt enthält "
        "andere Anzeigen – also nicht dieselben Wohnungen über die Zeit und keine aktuellen Preise.",

    # ---- p3 neighbourhoods
    "Which parts of Hamburg are expensive, and how they compare.":
        "Welche Teile Hamburgs teuer sind und wie sie sich vergleichen.",
    "Normal location": "Normale Lage",
    "Good location": "Gute Lage",
    "Rank by": "Sortieren nach",
    "Options": "Optionen",
    "Hide neighbourhoods with fewer listings than": "Stadtteile mit weniger Anzeigen als ausblenden",
    "Medians based on very few listings are unreliable, so small neighbourhoods are hidden by default.":
        "Mediane aus sehr wenigen Anzeigen sind unzuverlässig, daher werden kleine Stadtteile standardmäßig ausgeblendet.",
    "No neighbourhood has enough listings. Lower the minimum in Options.":
        "Kein Stadtteil hat genug Anzeigen. Senken Sie das Minimum in den Optionen.",
    "Ranking": "Rangliste",
    "Compare": "Vergleich",
    "Districts": "Bezirke",
    "Location quality": "Lagequalität",
    "Most expensive": "Am teuersten",
    "Most affordable": "Am günstigsten",
    "Most listings": "Meiste Anzeigen",
    "{n} listings": "{n} Anzeigen",
    "Full table": "Vollständige Tabelle",
    "{n} neighbourhoods with fewer than {min_n} listings are hidden.":
        "{n} Stadtteile mit weniger als {min_n} Anzeigen sind ausgeblendet.",
    "Choose neighbourhoods": "Stadtteile auswählen",
    "Rent range (€/m²)": "Mietspanne (€/m²)",
    "Median over time (€/m²)": "Median über die Zeit (€/m²)",
    "Pick at least one neighbourhood.": "Wählen Sie mindestens einen Stadtteil.",
    "Some points rest on fewer than 10 listings and are only indicative.":
        "Einige Punkte beruhen auf weniger als 10 Anzeigen und sind nur ein Richtwert.",
    "Median rent by district (€/m²)": "Median-Miete pro Bezirk (€/m²)",
    "Hamburg's official 2025 list marks streets as normal or good residential locations. "
    "A listing gets a class only when its street and house number match the list exactly. "
    "The list is from 2025; the listings are 2018–2020.":
        "Hamburgs offizielle Liste von 2025 klassifiziert Straßen als normale oder gute Wohnlage. "
        "Eine Anzeige erhält nur dann eine Klasse, wenn Straße und Hausnummer exakt mit der Liste übereinstimmen. "
        "Die Liste stammt von 2025; die Anzeigen sind von 2018–2020.",
    "Listings with a location class": "Anzeigen mit Lageklasse",
    "{pct}% of listings in view": "{pct}% der angezeigten Anzeigen",
    "Without one": "Ohne Klasse",
    "no street or number, or no exact match": "keine Straße/Nummer oder keine exakte Übereinstimmung",
    "Not enough matched listings in view to compare good and normal locations.":
        "Nicht genug zugeordnete Anzeigen, um gute und normale Lagen zu vergleichen.",
    "Rent by location quality (€/m²)": "Miete nach Lagequalität (€/m²)",
    "No map is shown because the data has no exact coordinates.":
        "Es wird keine Karte angezeigt, da die Daten keine genauen Koordinaten enthalten.",

    # ---- p4 properties
    "How rent per m² differs by size, age, type and features, and the listings behind it.":
        "Wie die Miete pro m² nach Größe, Alter, Typ und Ausstattung variiert, inklusive der zugrunde liegenden Anzeigen.",
    "Size & rooms": "Größe & Zimmer",
    "Building age": "Baualter",
    "Type & features": "Typ & Ausstattung",
    "Browse listings": "Anzeigen durchsuchen",
    "Rent per m² vs flat size": "Miete pro m² vs. Wohnungsgröße",
    "Size (m²)": "Größe (m²)",
    "Rent per m² by rooms": "Miete pro m² nach Zimmerzahl",
    "Rank correlation between size and rent per m²: {rho} (0 = no pattern). "
    "Differences shown are associations, not causes.":
        "Rangkorrelation zwischen Größe und Miete pro m²: {rho} (0 = kein Muster). "
        "Gezeigte Unterschiede sind Zusammenhänge, keine Ursachen.",
    "Numbers by size band": "Zahlen nach Größenklasse",
    "Not enough listings with a year built in this selection.":
        "Nicht genug Anzeigen mit Baujahr in dieser Auswahl.",
    "Rent per m² by year built": "Miete pro m² nach Baujahr",
    "Year built": "Baujahr",
    "Rent per m² by period built": "Miete pro m² nach Bauperiode",
    "{n} listings have no usable year built and are not shown here.":
        "{n} Anzeigen haben kein verwertbares Baujahr und werden hier nicht angezeigt.",
    "Rent per m² by property type": "Miete pro m² nach Immobilientyp",
    "Median rent with / without each feature": "Median-Miete mit / ohne jede Ausstattung",
    "Flats with a lift or balcony are often newer or bigger, so these gaps are not the price "
    "effect of the feature itself.":
        "Wohnungen mit Aufzug oder Balkon sind oft neuer oder größer, daher sind diese Unterschiede "
        "nicht der Preiseffekt der Ausstattung selbst.",

    # ---- p5 mietenspiegel
    "Hamburg's official 2025 reference rents, shown next to the historical asking rents. "
    "They measure different things, so use them for context.":
        "Hamburgs offizielle Referenzmieten 2025, gezeigt neben den historischen Angebotsmieten. "
        "Sie messen unterschiedliche Dinge – zur Einordnung, nicht zum direkten Vergleich.",
    "Mietenspiegel analytics table unavailable. Run `python scripts/run_pipeline.py`.":
        "Mietenspiegel-Analysetabelle nicht verfügbar. `python scripts/run_pipeline.py` ausführen.",
    "About this data": "Über diese Daten",
    "Publisher:": "Herausgeber:",
    "Title:": "Titel:",
    "Reference date:": "Stichtag:",
    "Official note (German, verbatim):": "Offizieller Hinweis (deutsch, wörtlich):",
    "All 88 cells share the equipment class 'mit Bad und Sammelheizung'. Reference rent = mean (Mittelwert); "
    "range = published Spanne (min–max).":
        "Alle 88 Zellen teilen die Ausstattungsklasse „mit Bad und Sammelheizung“. Referenzmiete = Mittelwert; "
        "Spanne = veröffentlichte Spanne (Min–Max).",
    "Look up a rent": "Miete nachschlagen",
    "Compare locations": "Lagen vergleichen",
    "Official vs asking rents": "Offizielle vs. Angebotsmieten",
    "Pick a flat type": "Wohnungstyp wählen",
    "Location quality": "Lagequalität",
    "Flat size": "Wohnungsgröße",
    "Equipment": "Ausstattung",
    "Only one equipment class is published.": "Es ist nur eine Ausstattungsklasse veröffentlicht.",
    "The Mietenspiegel does not publish a value for this combination (e.g. 'ab 131m²' × 1961–1967 in a "
    "Gute Wohnlage). No value is estimated.":
        "Für diese Kombination veröffentlicht der Mietenspiegel keinen Wert (z. B. „ab 131m²“ × 1961–1967 "
        "in guter Wohnlage). Es wird kein Wert geschätzt.",
    "Official reference rent": "Offizielle Referenzmiete",
    "Minimum": "Minimum",
    "Maximum": "Maximum",
    "Range width": "Spannbreite",
    "average": "Durchschnitt",
    "lower end of published range": "unteres Ende der veröffentlichten Spanne",
    "upper end of published range": "oberes Ende der veröffentlichten Spanne",
    "{n} source records": "{n} Quelldatensätze",
    "source record count not published": "Anzahl der Quelldatensätze nicht veröffentlicht",
    "**Historical listings mapped to the same characteristics (2018–2020, contextual):** {n}":
        "**Historische Anzeigen mit denselben Merkmalen (2018–2020, zur Einordnung):** {n}",
    "Historical median": "Historischer Median",
    "Historical mean": "Historischer Durchschnitt",
    "Difference of medians": "Differenz der Mediane",
    "advertised, cold": "Angebot, kalt",
    "contextual – different periods & methods": "zur Einordnung – unterschiedliche Zeiträume & Methoden",
    "Mietenspiegel 2025 range": "Mietenspiegel-2025-Spanne",
    "Only {n} historical listings map to this combination (Wohnlage requires a matched address and "
    "construction year). No comparison is drawn from so few observations.":
        "Nur {n} historische Anzeigen passen zu dieser Kombination (die Wohnlage erfordert eine zugeordnete "
        "Adresse und ein Baujahr). Aus so wenigen Beobachtungen wird kein Vergleich gezogen.",
    "Benchmark range comparison": "Vergleich der Referenzspannen",
    "Official reference mean with min–max range for the selected location and living-area category.":
        "Offizieller Referenz-Mittelwert mit Min–Max-Spanne für die gewählte Lage und Wohnflächenklasse.",
    "Published range (min–max)": "Veröffentlichte Spanne (Min–Max)",
    "Reference rent (mean)": "Referenzmiete (Mittelwert)",
    "Selected": "Ausgewählt",
    "Construction period": "Baualtersklasse",
    "€/m² (net cold)": "€/m² (netto kalt)",
    "Reference rent by period × area": "Referenzmiete nach Baualter × Fläche",
    "Normal vs good residential location": "Normale vs. gute Wohnlage",
    "Median reference rent across area categories": "Median-Referenzmiete über alle Flächenklassen",
    "Median across the published living-area categories in each period (good-location cells include "
    "two additional size classes).":
        "Median über alle veröffentlichten Wohnflächenklassen je Zeitraum (Zellen guter Lage enthalten "
        "zwei zusätzliche Größenklassen).",
    "Historical listings vs Mietenspiegel by construction period":
        "Historische Anzeigen vs. Mietenspiegel nach Baualtersklasse",
    "Listings are mapped by construction year to the nearest published period; unmappable years "
    "(e.g. 1948) are excluded.":
        "Anzeigen werden über das Baujahr dem nächsten veröffentlichten Zeitraum zugeordnet; nicht "
        "zuordenbare Jahre (z. B. 1948) sind ausgeschlossen.",
    "Full benchmark table": "Vollständige Vergleichstabelle",

    # ---- p7 ask AI
    "Ask about Hamburg rents in plain English. Every answer shows the numbers it is based on.":
        "Fragen Sie in einfacher Sprache nach Hamburger Mieten. Jede Antwort zeigt die Zahlen, auf denen sie beruht.",
    "Live AI is switched off in this demo to manage API costs and credit usage. The suggested questions "
    "show real answers the AI analyst generated from this data in advance. Questions you type are "
    "answered by the built-in analysis, which uses the same data.":
        "Die Live-KI ist in dieser Demo deaktiviert, um API-Kosten und Guthaben zu schonen. Die vorgeschlagenen "
        "Fragen zeigen echte Antworten, die die KI-Analystin im Voraus aus diesen Daten erstellt hat. "
        "Selbst eingegebene Fragen werden von der integrierten Analyse beantwortet, die dieselben Daten nutzt.",
    "Use my filters ({desc})": "Meine Filter verwenden ({desc})",
    "Try one of these": "Eine davon ausprobieren",
    "More questions": "Weitere Fragen",
    "Ask about rents, neighbourhoods, property types or the official 2025 rents…":
        "Fragen Sie nach Mieten, Stadtteilen, Immobilientypen oder den offiziellen Mieten 2025…",
    "Looking at the data…": "Schaue mir die Daten an…",
    "Start over": "Neu starten",

    # ---- listing table (used from the Properties page)
    "Search": "Suche",
    "Neighbourhood, street, type or postcode, e.g. Eppendorf": "Stadtteil, Straße, Typ oder Postleitzahl, z. B. Eppendorf",
    "Only unusual listings (very high prices or odd values)": "Nur ungewöhnliche Anzeigen (sehr hohe Preise oder auffällige Werte)",
    "{n} listings shown. Click a column header to sort.": "{n} Anzeigen angezeigt. Spaltenkopf anklicken, um zu sortieren.",
    "Download as CSV": "Als CSV herunterladen",
}


def lang() -> str:
    return st.session_state.get("lang", "en")


def set_lang(code: str) -> None:
    st.session_state.lang = code


def t(text: str, **kwargs) -> str:
    """Translate a UI string to the active language, falling back to the English original."""
    if lang() == "de":
        text = TRANSLATIONS.get(text, text)
    return text.format(**kwargs) if kwargs else text
