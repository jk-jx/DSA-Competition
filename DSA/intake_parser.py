"""Email/pasted-message classification and structured master-data extraction.

No LLM calls are made unless an explicit API key/endpoint is configured
and the user clicks the extraction button. Rules always work offline.
"""
import json
import os
import re

import requests

COUNTRY_CODES = {
    "singapore": "SG", "malaysia": "MY", "indonesia": "ID",
    "thailand": "TH", "vietnam": "VN",
}
DOMAINS = ("Customer", "Item", "Vendor", "Cost Center")
RECORD_TYPES = ("PO", "Customer Request", "Enquiry", "MDM Setup")


def setting(name, default=""):
    if os.getenv(name):
        return os.environ[name]
    try:
        import streamlit as st
        return st.secrets.get(name, default)
    except Exception:
        return default


def classify_message(text):
    t = text.lower()
    if re.search(r"\b(create|set ?up|register|onboard|update|change|amend)\b.{0,85}\b(customer|vendor|supplier|item|material|cost cent(?:re|er)|master data)\b", t, re.S) or re.search(
        r"\b(new customer|new vendor|new supplier|new item|mdm request)\b", t
    ):
        return "MDM Setup"
    if re.search(r"\b(purchase order|po\s*[#:]?\s*\d{3,}|attached\s+po)\b", t):
        return "PO"
    if re.search(r"\b(quotation|quote|enquiry|inquiry|price check|availability)\b", t):
        return "Enquiry"
    if re.search(r"\b(would like to (buy|purchase|order)|planning to order|purchase request|request to purchase)\b", t):
        return "Customer Request"
    return "Enquiry"


def _domain(text):
    t = text.lower()
    if re.search(r"\b(cost cent(?:re|er))\b", t):
        return "Cost Center"
    if re.search(r"\b(vendor|supplier)\b", t):
        return "Vendor"
    if re.search(r"\b(item|material|sku)\b", t):
        return "Item"
    return "Customer"


def rule_extract(text):
    if not text or not text.strip():
        raise ValueError("Paste a request first.")
    domain = _domain(text)
    found = {}
    entity = re.search(r"\b(SPD|QTS|QTG)\b", text, re.I)
    if entity:
        found["entity"] = entity.group(1).upper()
    for word, code in COUNTRY_CODES.items():
        if re.search(r"\b" + word + r"\b", text, re.I):
            found["country"] = code
            break
    if "country" not in found:
        iso = re.search(r"\b(?:country|market)\s*[:=]\s*(SG|MY|ID|TH|VN)\b", text, re.I)
        if iso:
            found["country"] = iso.group(1).upper()
    reg = re.search(
        r"\b(?:registration(?:\s+(?:number|no\.?))?|business\s+id|reg\s*(?:no\.?)?|uen)\s*[:=#-]?\s*([A-Z]{1,5}[-\w]{2,})",
        text, re.I
    )
    if reg:
        found["registration_number"] = reg.group(1).upper().strip(".,;")
    mail = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    if mail:
        found["contact_email"] = mail.group()
    item_category = re.search(r"\b(?:item category|category)\s*[:=]\s*([^,;\n.]+)", text, re.I)
    if item_category:
        found["item_category"] = item_category.group(1).strip()
    name = re.search(r"\b(?:customer|vendor|supplier|item)\s+name\s*[:=]\s*([^\n;,\.]+)", text, re.I)
    if not name:
        name = re.search(
            r"\b(?:create|set\s*up|register|onboard)\s+(?:a\s+)?(?:new\s+)?(?:customer|vendor|supplier|item)\s*[,:\-]?\s*"
            r"(.+?)(?=\s+(?:under|in|for|with|registration|reg\s+no)\b|[,.;\n]|$)",
            text, re.I
        )
    if name:
        found["name"] = name.group(1).strip(" :-,")
    return {"record_type": classify_message(text), "domain": domain, "fields": found, "method": "rules"}


def _normalize_llm(data, fallback):
    allowed = {"name", "country", "entity", "registration_number", "contact_email", "item_category", "regulatory_class"}
    parsed = dict(fallback)
    record_type = str(data.get("record_type", ""))
    domain = str(data.get("domain", ""))
    if record_type in RECORD_TYPES:
        parsed["record_type"] = record_type
    if domain in DOMAINS:
        parsed["domain"] = domain
    fields = data.get("fields", {})
    if isinstance(fields, dict):
        merged = dict(fallback["fields"])
        for k, v in fields.items():
            if k in allowed and isinstance(v, str) and v.strip():
                merged[k] = v.strip()
        if merged.get("country", "").lower() in COUNTRY_CODES:
            merged["country"] = COUNTRY_CODES[merged["country"].lower()]
        if merged.get("country") not in COUNTRY_CODES.values():
            merged.pop("country", None)
        if merged.get("entity"):
            merged["entity"] = merged["entity"].upper()
        parsed["fields"] = merged
    parsed["method"] = "Azure OpenAI"
    return parsed


def extract_message(text, use_llm=False):
    """Return typed data; network calls only with an explicitly configured Azure endpoint."""
    fallback = rule_extract(text)
    if not use_llm:
        return fallback
    endpoint = setting("AZURE_OPENAI_ENDPOINT").rstrip("/")
    deployment = setting("AZURE_OPENAI_DEPLOYMENT")
    api_key = setting("AZURE_OPENAI_API_KEY")
    version = setting("AZURE_OPENAI_API_VERSION", "2024-10-21")
    if not all((endpoint, deployment, api_key)):
        raise ValueError("Azure OpenAI is not configured; use rules-first extraction.")
    if not endpoint.startswith("https://"):
        raise ValueError("Azure OpenAI endpoint must use HTTPS.")
    url = endpoint + "/openai/deployments/" + deployment + "/chat/completions"
    prompt = (
        "Return JSON only with keys record_type (PO, Customer Request, Enquiry, MDM Setup), "
        "domain (Customer, Item, Vendor, Cost Center), fields (name, country SG/MY/ID/TH/VN, "
        "entity SPD/QTS/QTG, registration_number, contact_email, item_category, regulatory_class). "
        "Do not guess missing values. Customer purchasing requests are not confirmed purchase orders; "
        "MDM setup requests are not sales orders. Extract only explicit information."
    )
    resp = requests.post(
        url, params={"api-version": version},
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json={"messages": [{"role": "system", "content": prompt},
                           {"role": "user", "content": text[:6000]}],
              "temperature": 0, "max_tokens": 450, "response_format": {"type": "json_object"}},
        timeout=16,
    )
    resp.raise_for_status()
    answer = resp.json()["choices"][0]["message"]["content"]
    return _normalize_llm(json.loads(answer), fallback)
