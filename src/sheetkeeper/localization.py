"""Language hints never alter CSV values or machine-readable receipts."""
import json
from pathlib import Path
CATALOG = json.loads((Path(__file__).resolve().parents[2] / "web" / "i18n.json").read_text())

def language(locale):
    base = str(locale).lower().split("-")[0]
    return base if base in CATALOG else "en"

def translate(message, locale):
    return CATALOG[language(locale)]["messages"].get(message, message)
