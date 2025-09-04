# ee_init.py — robuste Earth Engine Initialisierung (Service Account bevorzugt)
import os
import json
import base64
from typing import Optional, Tuple

import streamlit as st
import ee

try:
    import geemap  # optional; nur wenn explizit gewünscht
except Exception:
    geemap = None

_GCP_SCOPES = [
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/devstorage.full_control",
]

def _preview(s: str, n: int = 120) -> str:
    s = (s or "").strip().replace("\n", "\\n")
    return (s[:n] + ("…" if len(s) > n else "")) or "(leer)"

def _load_from_secrets_or_env(key: str) -> Optional[str]:
    # st.secrets kann in manchen Umgebungen fehlen; defensiv lesen
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key)

def _parse_service_account_json(raw: str) -> dict:
    """Akzeptiert mehrere Formate:
    1) Direktes JSON
    2) Base64-encodetes JSON
    3) Pfad zu einer JSON-Datei
    4) Python-Dict-String mit '...' → sicher in JSON konvertieren
    """
    if not raw or not isinstance(raw, str):
        raise ValueError("EE_PRIVATE_KEY ist leer oder kein String.")

    s = raw.strip()

    # 3) Dateipfad?
    if len(s) < 512 and (s.endswith(".json") or os.path.sep in s):
        if not os.path.exists(s):
            raise FileNotFoundError(f"EE_PRIVATE_KEY verweist auf einen Pfad, der nicht existiert: {s}")
        with open(s, "r", encoding="utf-8") as f:
            s = f.read().strip()

    # 1) Direktes JSON?
    if s.startswith("{") and s.endswith("}"):
        try:
            return json.loads(s)
        except json.JSONDecodeError as e:
            raise ValueError(f"EE_PRIVATE_KEY sieht aus wie JSON, konnte aber nicht geparst werden: {e}")

    # 2) Base64?
    # Heuristik: Base64 ist oft länger, enthält nur zulässige Zeichen und decodiert zu JSON.
    b64_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n\r"
    if all(c in b64_chars for c in s):
        try:
            decoded = base64.b64decode(s, validate=False).decode("utf-8", errors="strict").strip()
            if decoded.startswith("{") and decoded.endswith("}"):
                return json.loads(decoded)
        except Exception:
            pass  # weiterprobieren

    # 4) Python-Dict-String (mit einfachen Anführungszeichen)
    # Vorsichtig normalisieren: nur das Äußere ersetzen, keine Keys/Values zerstören.
    # Sehr simple Heuristik: wenn mindestens zwei Vorkommen von "': " und keine doppelten Quotes, konvertieren.
    looks_like_py_dict = s.startswith("{") and s.endswith("}") and ("':" in s or "': " in s) and ('"' not in s)
    if looks_like_py_dict:
        try:
            s_jsonish = s.replace("'", '"')
            return json.loads(s_jsonish)
        except Exception as e:
            raise ValueError(
                "EE_PRIVATE_KEY scheint ein Python-Dict-String zu sein (mit einfachen Quotes). "
                "Bitte echtes JSON verwenden oder Base64/Dateipfad angeben."
            ) from e

    # Nur private_key ohne Rest?
    if "BEGIN PRIVATE KEY" in s and "client_email" not in s:
        raise ValueError(
            "EE_PRIVATE_KEY enthält offenbar nur den 'private_key' Block. "
            "Erforderlich ist das **vollständige** Service-Account-JSON (mit type, project_id, client_email, token_uri, …)."
        )

    # Letzte Chance: klarer Fehler mit Vorschlägen
    raise ValueError(
        "EE_PRIVATE_KEY ist in einem unbekannten Format.\n"
        f"Vorschau: { _preview(s) }\n\n"
        "Erlaubte Formen:\n"
        "  • Direktes JSON (beginnend mit '{')\n"
        "  • Base64-encodetes JSON (als String)\n"
        "  • Pfad zu einer JSON-Datei\n"
        "  • KEIN Python-Dict mit einfachen Quotes — bitte echtes JSON verwenden"
    )

def _build_credentials(svc_info: dict):
    try:
        from google.oauth2 import service_account
    except Exception as e:
        raise RuntimeError(
            "google-auth ist nicht installiert. Bitte 'google-auth>=2' in requirements aufnehmen."
        ) from e
    # Minimalprüfung der Schlüssel
    for k in ("type", "project_id", "private_key", "client_email", "token_uri"):
        if not svc_info.get(k):
            raise ValueError(f"Service-Account-JSON unvollständig: Feld '{k}' fehlt oder ist leer.")
    if svc_info.get("type") != "service_account":
        raise ValueError("Service-Account-JSON: 'type' muss 'service_account' sein.")
    return service_account.Credentials.from_service_account_info(svc_info, scopes=_GCP_SCOPES)

def _geemap_allowed() -> bool:
    val = _load_from_secrets_or_env("ALLOW_GEEMAP_FALLBACK")
    if val is None:
        return False  # Standard: KEIN OAuth-Fallback in Headless-Umgebungen
    return str(val).strip().lower() in ("1", "true", "yes", "on")

@st.cache_resource(show_spinner=False)
def ee_client_init() -> str:
    """Initialisiert EE einmal pro Session. Rückgabe: Text über die Quelle."""
    # Bereits initialisiert?
    try:
        ee.Number(1).getInfo()
        return "ok:already_initialized"
    except Exception:
        pass

    # Keys laden
    raw_key = _load_from_secrets_or_env("EE_PRIVATE_KEY")
    ee_project = _load_from_secrets_or_env("EE_PROJECT")
    # EE_SERVICE_ACCOUNT ist optional/informativ
    _ = _load_from_secrets_or_env("EE_SERVICE_ACCOUNT")

    # Service-Account bevorzugen
    if raw_key:
        try:
            svc_info = _parse_service_account_json(raw_key)
            creds = _build_credentials(svc_info)
            if ee_project:
                ee.Initialize(credentials=creds, project=ee_project)
            else:
                ee.Initialize(credentials=creds)
            # Testcall
            ee.Number(1).getInfo()
            return f"ok:service_account_json{'_with_project' if ee_project else ''}"
        except Exception as e:
            st.error(
                "Earth Engine Initialisierung via Service-Account-JSON fehlgeschlagen.\n"
                f"EE_PRIVATE_KEY Vorschau: { _preview(raw_key) }\n\n"
                "Bitte sicherstellen:\n"
                "• EE_PRIVATE_KEY enthält das **vollständige** JSON (nicht nur den private_key)\n"
                "• Format ist JSON, Base64-JSON oder ein gültiger Datei-Pfad\n"
                "• Service Account ist für EE freigeschaltet (https://earthengine.google.com/ → IAM) und dem Projekt zugeordnet\n"
                "• Optional: EE_PROJECT korrekt gesetzt"
            )
            st.exception(e)
            # kein sofortiges Stop — evtl. geemap-Fallback, wenn explizit erlaubt

    # Optionaler Fallback über geemap (nur wenn ausdrücklich erlaubt)
    if _geemap_allowed():
        try:
            if geemap is None:
                raise RuntimeError("geemap nicht installiert")
            token_name = _load_from_secrets_or_env("EARTHENGINE_TOKEN") or "EARTHENGINE_TOKEN"
            geemap.ee_initialize(token_name=str(token_name))
            ee.Number(1).getInfo()
            return "ok:geemap_token"
        except Exception as e:
            st.error(
                "geemap-Fallback fehlgeschlagen (OAuth-Token nicht vorhanden oder unvollständig). "
                "Für Server/Headless-Betrieb wird Service-Account empfohlen."
            )
            st.exception(e)

    st.error(
        "Earth Engine ist nicht initialisiert.\n\n"
        "Bitte EE_PRIVATE_KEY (vollständiges Service-Account-JSON) und optional EE_PROJECT setzen.\n"
        "Tipps für Streamlit secrets.toml:\n"
        "  EE_PROJECT = \"ee-deinprojekt\"\n"
        "  EE_PRIVATE_KEY = '''{ ... JSON ... }'''\n"
        "Oder EE_PRIVATE_KEY als Base64 oder als Pfad zu einer .json-Datei angeben."
    )
    st.stop()

def ensure_ee_ready() -> None:
    _ = ee_client_init()
