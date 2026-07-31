"""
Curated military aerodrome lists.

Kept separate from the classifier so the *data* can be reviewed and diffed
without touching the *logic*. Every entry carries its justification.

Entries are added by hand, from the artifact produced by
``tools/review_military_candidates.py`` in flyfun-apps. That tool generates
candidates from aerodrome naming ("Air Base", "Fliegerhorst", "(BA 118)") and
cross-checks each one against AIP evidence, but it never writes here: naming
alone is not enough to assert that a field is military *today*.

Why naming is not enough — the two failure modes that motivated this split:

1. A name is not revoked when a base closes. Five Belgian Air Force bases
   deactivated in the 1990s are still published as "X Air Base" while operating
   as civil gliding sites. See ``FORMER_MILITARY``.
2. Aerodrome *keywords* are worse still: they retain wartime identities, so
   ``EGSU`` Duxford carries "RAF Duxford" and ``EDDF`` Frankfurt carries
   "Rhein-Main Air Base". Keywords are never consulted, anywhere.

The AIP cross-check is what promotes a candidate. The AIP has no military field,
so the usable markers are indirect and concentrated in the fuel fields: NATO
oil/hydraulic codes (``O-150``, ``H-515``), military-only fuels (``F-18`` avgas,
``F-44`` JP-5), and military wording in a field that describes the aerodrome.

Two markers that look decisive and are not, both rejected after testing against
the corpus:

* ``MIL:``/``CIV:`` splits — a routine presentational convention in the French
  and Spanish AIPs, firing on Le Touquet, Bordeaux, Limoges, Málaga and Palma.
* ``F-34`` alone — merely Jet A-1 with FSII, advertised by civil UK fields such
  as Sleap and Cumbernauld.

German ``ET`` and UK military ``EG`` aerodromes are intentionally absent: the
ICAO prefix rules already cover every one of them, so listing a handful here
would imply the rest are civil.
"""

from typing import Dict

# Hand-verified and AIP-confirmed military / joint civil-military aerodromes,
# keyed by ICAO. The value records why the entry is here.
#
# Two provenance styles, both reviewed by hand before landing:
#   "<place> — <role>"       hand-verified joint-use field whose published name
#                            gives nothing away (Aalborg, Thessaloniki)
#   "<name> — AIP: <marker>" name flagged it as a candidate AND the AIP carried a
#                            strong military marker; promoted from the artifact
#                            written by tools/review_military_candidates.py
KNOWN_MILITARY_ICAOS: Dict[str, str] = {
    # Austria
    'LOWG': 'Graz — Fliegerhorst Nittner',
    'LOWL': 'Linz-Hörsching — Fliegerhorst Vogler',
    'LOXA': 'Fiala-Fernbrugg Air Base — AIP: military wording',
    'LOXT': 'Brumowski Air Base — AIP: military wording',
    'LOXZ': 'Hinterstoisser Air Base — AIP: military wording',
    # Belgium
    'EBBE': 'Beauvechain Air Base — AIP: NATO oil/hyd code; military-only fuel',
    'EBBL': 'Kleine Brogel Air Base — AIP: NATO oil/hyd code; military-only fuel',
    'EBFN': 'Koksijde Air Base — AIP: NATO oil/hyd code',
    'EBFS': 'Florennes Air Base — AIP: NATO oil/hyd code; military-only fuel',
    # Czechia
    'LKCV': 'Čáslav Air Base — AIP: military wording',
    'LKKB': 'Prague–Kbely Air Base — AIP: military wording',
    'LKPD': 'Pardubice — 21st Tactical Air Force Base (joint use)',
    # Denmark
    'EKYT': 'Aalborg — Air Transport Wing (joint use)',
    # Spain
    'LEAB': 'Albacete Airport / Los Llanos Air Base — AIP: NATO oil/hyd code',
    'LEGT': 'Getafe Air Base — AIP: NATO oil/hyd code',
    'LEMO': 'Moron Air Base — AIP: NATO oil/hyd code',
    'LERI': 'Alcantarilla Air Base — AIP: NATO oil/hyd code',
    'LETO': 'Madrid–Torrejón Airport / Torrejón Air Base — AIP: NATO oil/hyd code',
    'LEZG': 'Zaragoza — Ala 15 air base (joint use)',
    # Finland
    'EFHA': 'Halli — military flight test',
    'EFJY': 'Jyväskylä/Tikkakoski — Air Force Academy',
    'EFRO': 'Rovaniemi — Lapland Air Command (joint use)',
    'EFTP': 'Tampere-Pirkkala — Satakunta Air Command (joint use)',
    # France
    'LFBC': 'Cazaux (BA 120) Air Base — AIP: NATO oil/hyd code',
    'LFBG': 'Cognac-Châteaubernard (BA 709) Air Base — AIP: NATO oil/hyd code; military-only fuel',
    'LFBM': 'Mont-de-Marsan (BA 118) Air Base — AIP: NATO oil/hyd code',
    'LFKS': 'Solenzara (BA 126) Air Base — AIP: NATO oil/hyd code',
    'LFMI': 'Istres-Le Tubé Air Base — AIP: military-only fuel',
    'LFMO': 'Orange-Caritat (BA 115) Air Base — AIP: NATO oil/hyd code',
    'LFMY': 'Salon-de-Provence (BA 701) Air Base — AIP: military-only fuel',
    'LFOA': 'Avord (BA 702) Air Base — AIP: NATO oil/hyd code; military-only fuel',
    'LFOE': 'Évreux-Fauville (BA 105) Air Base — AIP: NATO oil/hyd code; military-only fuel',
    'LFOJ': 'Orléans-Bricy (BA 123) Air Base — AIP: NATO oil/hyd code',
    'LFPV': 'Vélizy-Villacoublay Air Base — AIP: NATO oil/hyd code',
    'LFQP': 'Phalsbourg-Bourscheid Air Base — AIP: NATO oil/hyd code',
    'LFRJ': 'Landivisiau Air Base — AIP: NATO oil/hyd code',
    'LFRL': 'Lanvéoc-Poulmic Air Base — AIP: NATO oil/hyd code; military-only fuel',
    'LFSI': 'Saint-Dizier – Robinson Air Base — AIP: NATO oil/hyd code',
    'LFSO': 'Nancy-Ochey (BA 133) Air Base — AIP: NATO oil/hyd code',
    'LFSX': 'Luxeuil-Saint-Sauveur (BA 116) Air Base — AIP: NATO oil/hyd code; military-only fuel',
    # Greece
    'LGEL': 'Elefsis Air Base — AIP: military wording',
    'LGKV': 'Kavala/Amygdaleon — air base (joint use)',
    'LGTS': 'Thessaloniki — 113 Combat Wing (joint use)',
    # Iceland
    'BIKF': 'Keflavik — NATO air station (joint use)',
    # Italy
    'LIPY': 'Ancona-Falconara — air force presence (joint use)',
    # Lithuania
    'EYSA': 'Šiauliai — NATO Baltic Air Policing',
    # Netherlands
    'EHGR': 'Gilze Rijen Air Base — AIP: NATO oil/hyd code; military-only fuel',
    'EHKD': 'De Kooy Airfield / Den Helder Naval Air Station — AIP: military wording',
    'EHLW': 'Leeuwarden Air Base — AIP: NATO oil/hyd code',
    'EHVK': 'Volkel Air Base — AIP: NATO oil/hyd code',
    # Norway
    'ENBO': 'Bodø — main air station',
    'ENDU': 'Bardufoss — air station',
    'ENOL': 'Ørland — main air station',
    'ENRY': 'Rygge — air station',
    # Portugal
    'LPAV': 'São Jacinto — Aveiro air base',
    # Romania
    'LRBC': 'Bacău — RoAF 95th Air Base',
    'LRCK': 'Mihail Kogălniceanu — RoAF 57th Air Base',
    'LRTR': 'Timișoara — RoAF 93rd Air Base',
    # Sweden
    'ESCM': 'Ärna Air Base — AIP: military wording',
    'ESPA': 'Luleå/Kallax — F21 wing (joint use)',
    # Slovenia
    'LJCE': 'Cerklje ob Krki Air Base — AIP: military wording',
    # Kosovo
    'BKPR': 'Priština/Slatina — KFOR',
}

# Aerodromes that a rule, or a stale published name, would otherwise flag but
# which are civil today. These win over every other signal in the classifier.
#
# This list is also a record of review decisions: it exists so a future pass
# over aerodrome names does not re-propose fields already rejected once.
FORMER_MILITARY: Dict[str, str] = {
    # Matches the UK military third-letter rule, but civil since 2014
    'EGXG': 'Leeds East — ex-RAF Church Fenton, civil since 2014',
    # Belgian Air Force bases deactivated in the 1990s; civil/gliding today.
    # All still named "Air Base" upstream, none carrying military AIP markers.
    'EBSU': 'Saint Hubert — ex-Belgian AF, civil aerodrome',
    'EBUL': 'Ursel — ex-NATO reserve, civil/events',
    'EBWE': 'Weelde — ex-Belgian AF, civil/gliding',
    'EBBX': 'Jehonville — ex-Belgian AF, civil aeroclub',
    'EBSL': 'Zutendaal — ex-NATO reserve, no longer active',
    # Swiss Air Force airfields decommissioned
    'LSGR': 'Reichenbach — ex-Swiss AF, civil',
    'LSML': 'Lodrino — ex-Swiss AF, civil',
    # Greek, inactive
    'LGSD': 'Sedes — inactive',
    'LGTP': 'Tripolis — inactive',
    # Ex-Soviet / ex-base, civil GA today
    'EYSI': 'Šilute — ex-Soviet, civil',
    'LZPW': 'Prešov — ex-military, civil strip',
    'EPPR': 'Pruszcz Gdański — ex-military, civil aeroclub',
    'LFYR': 'Romorantin Pruniers — ex-BA 273, closed as an air base',
}

# Alias matching the classifier's vocabulary.
KNOWN_CIVIL_ICAOS = FORMER_MILITARY
