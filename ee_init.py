# ee_init.py — zentrale Earth Engine Initialisierung für Streamlit
# Unterstützt:
# - st.secrets["gcp_service_account"] (vollständiges Service-Account-JSON als Text)
# - st.secrets["EE_PRIVATE_KEY"] (+ optional st.secrets["EE_PROJECT"])
# - Umgebungsvariablen EE_PRIVATE_KEY (+ optional EE_PROJECT)
# - Fallback via geemap.ee_initialize(token_name="EARTHENGINE_TOKEN")

import os
import json
import ee
import streamlit as st

try:
    import geemap  # optionaler Fallback
except Exception:
    geemap = None

from typing import Optional, Tuple

# Scopes für Earth Engine + GCS
_GCP_SCOPES = [
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/devstorage.full_control",
]

@st.cache_resource(show_spinner=False)
def ee_client_init(token_name: str = "EARTHENGINE_TOKEN") -> str:
    """Initialisiert Earth Engine einmalig pro Session und liefert eine Kennung des verwendeten Pfads zurück."""
    # 0) Bereits initialisiert?
    try:
        ee.Number(1).getInfo()
        return "ok:already_initialized"
    except Exception:
        pass

    # 1) Versuche st.secrets["gcp_service_account"] (bestehender Weg)
    #    Erwartet komplettes JSON als String.
    svc_json_text = None
    ee_project = None

    if "gcp_service_account" in st.secrets:
        svc_json_text = st.secrets["gcp_service_account"]
        ee_project = st.secrets.get("ee_project") or st.secrets.get("EE_PROJECT")

    # 2) Falls nicht vorhanden: st.secrets["EE_PRIVATE_KEY"] (+ optional EE_PROJECT)
    if svc_json_text is None and "EE_PRIVATE_KEY" in st.secrets:
        svc_json_text = st.secrets["EE_PRIVATE_KEY"]
        ee_project = ee_project or st.secrets.get("EE_PROJECT") or st.secrets.get("ee_project")

    # 3) Falls weiterhin nicht vorhanden: Environment EE_PRIVATE_KEY (+ optional EE_PROJECT)
    if svc_json_text is None and "EE_PRIVATE_KEY" in os.environ:
        svc_json_text = os.environ.get("EE_PRIVATE_KEY")
        ee_project = ee_project or os.environ.get("EE_PROJECT")

    # 4) EE_SERVICE_ACCOUNT ist informativ; nicht zwingend benötigt, wenn das JSON komplett ist.
    ee_service_account = (
        st.secrets.get("EE_SERVICE_ACCOUNT")
        if hasattr(st, "secrets") else None
    )
    ee_service_account = ee_service_account or os.environ.get("EE_SERVICE_ACCOUNT")

    # 5) Initialisierung über google.oauth2.service_account
    #    Wir parsen das JSON (String) -> dict und erzeugen Credentials mit Scopes.
    if svc_json_text:
        try:
            svc_info = _parse_service_account_json(svc_json_text)
            creds = _build_credentials(svc_info)
            if ee_project:
                ee.Initialize(credentials=creds, project=ee_project)
            else:
                # project ist optional; Earth Engine nutzt dann das dem Service Account zugeordnete Projekt.
                ee.Initialize(credentials=creds)
            # Sanity-Check
            ee.Number(1).getInfo()
            return f"ok:service_account_json{'_with_project' if ee_project else ''}"
        except Exception as e:
            st.error(
                "Earth Engine Initialisierung via Service-Account-JSON ist fehlgeschlagen. "
                "Bitte prüfe:\n"
                "• Das JSON ist vollständig (type, project_id, private_key, client_email, token_uri, …)\n"
                "• Der Service Account hat EE-Zugriff (earthengine.google.com → IAM) und ist in EE registriert\n"
                "• Optional: EE_PROJECT ist korrekt gesetzt"
            )
            st.exception(e)
            # Nicht abbrechen: wir versuchen noch den geemap-Fallback

    # 6) Fallback: geemap Token-Store (dein alter Weg)
    try:
        if geemap is None:
            raise RuntimeError("geemap nicht installiert")
        geemap.ee_initialize(token_name=token_name)
        ee.Number(1).getInfo()
        return "ok:geemap_token"
    except Exception as e:
        st.error(
            "Earth Engine ist nicht initialisiert.\n\n"
            "Empfehlung: Hinterlege den vollständigen Service-Account-Key entweder als "
            "st.secrets['EE_PRIVATE_KEY'] oder Umgebungsvariable EE_PRIVATE_KEY "
            "(als komplettes JSON), und optional EE_PROJECT."
        )
        st.exception(e)
        st.stop()

def ensure_ee_ready() -> None:
    """Sorgt dafür, dass EE initialisiert ist oder bricht mit klarer Fehlermeldung ab."""
    _ = ee_client_init()

# -------------------- interne Helper --------------------

def _parse_service_account_json(s: str) -> dict:
    """Akzeptiert den Inhalt eines Service-Account-Keyfiles als String. Liefert dict.
    Falls s bereits ein JSON-dump ist (inkl. Zeilenumbrüchen), einfach json.loads(s).
    """
    # Manche setzen versehentlich nur den private_key ein. Das reicht NICHT.
    # Wir erwarten das vollständige JSON (type, project_id, private_key_id, private_key, client_email, client_id, auth_uri, token_uri, auth_provider_x509_cert_url, client_x509_cert_url).
    svc_info = json.loads(s)
    required = ["type", "project_id", "private_key", "client_email", "token_uri"]
    missing = [k for k in required if k not in svc_info or not svc_info[k]]
    if missing:
        raise ValueError(f"Service-Account-JSON unvollständig. Fehlende Felder: {', '.join(missing)}")
    if svc_info.get("type") != "service_account":
        raise ValueError("JSON 'type' ist nicht 'service_account'.")
    return svc_info

def _build_credentials(svc_info: dict):
    """Erzeugt google.oauth2.service_account.Credentials mit EE/GCS-Scopes."""
    try:
        from google.oauth2 import service_account
    except Exception as e:
        raise RuntimeError(
            "google-auth ist nicht installiert. Füge 'google-auth' zu deinen Abhängigkeiten hinzu."
        ) from e
    creds = service_account.Credentials.from_service_account_info(svc_info, scopes=_GCP_SCOPES)
    return creds
