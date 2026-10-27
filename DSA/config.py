from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parent
COUNTRIES = {"SG":"Singapore", "MY":"Malaysia", "ID":"Indonesia", "TH":"Thailand", "VN":"Vietnam"}
ENTITIES = ["SPD", "QTS", "QTG"]
ROLE_ACTOR = {"Requestor":"Alex Sales", "Finance Steward":"Wei Jie Finance", "Quality Steward":"Nadia Quality", "BU Steward":"Daniel BU Head", "MDM Steward":"Priya MDM", "Admin":"Marcus Admin"}
DB_PATH = ROOT / 'data' / 'demo.sqlite'

def settings():
    return yaml.safe_load((ROOT/'domains.yaml').read_text(encoding='utf-8'))
