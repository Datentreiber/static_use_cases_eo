# ee_init.py — zentrale Earth Engine Initialisierung für Streamlit

import json
import streamlit as st
import ee

try:
    import geemap  # optionaler Fallback
except Exception:
    geemap = None

@st.cache_resource(show_spinner=False)
def ee_client_init(token_name: str = "EARTHENGINE_TOKEN") -> str:
    # 0) Bereits initialisiert?
    try:
        ee.Number(1).getInfo()
        return "ok:already"
    except Exception:
        pass

    # 1) Application Default Credentials (lokal)
    try:
        ee.Initialize()
        ee.Number(1).getInfo()
        return "ok:adc"
    except Exception:
        pass

    # 2) Service Account (empfohlen für Streamlit Cloud)
    try:
        sa_blob = st.secrets["gcp_service_account"]  # KeyError falls nicht gesetzt
        sa_info = json.loads(sa_blob)
        from google.oauth2 import service_account
        scopes = [
            "https://www.googleapis.com/auth/earthengine",
            "https://www.googleapis.com/auth/devstorage.read_write",
        ]
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=scopes)
        project = st.secrets.get("ee_project", sa_info.get("project_id"))
        ee.Initialize(credentials=creds, project=project)
        ee.Number(1).getInfo()
        return "ok:service_account"
    except KeyError:
        # kein Secret → weiter zu (3)
        pass
    except Exception as e:
        st.error("Earth Engine mit Service Account konnte nicht initialisiert werden. "
                 "Prüfe EE-Rechte (IAM) und das Secret-Format.")
        st.exception(e)
        st.stop()

    # 3) Fallback: geemap Token-Store (dein alter Weg)
    try:
        if geemap is None:
            raise RuntimeError("geemap nicht installiert")
        geemap.ee_initialize(token_name=token_name)
        ee.Number(1).getInfo()
        return "ok:geemap_token"
    except Exception as e:
        st.error(
            "Earth Engine ist nicht initialisiert.\n\n"
            "Empfehlung: hinterlege einen Service-Account-Key in st.secrets['gcp_service_account'] "
            "und (optional) st.secrets['ee_project']."
        )
        st.exception(e)
        st.stop()

def ensure_ee_ready() -> None:
    _ = ee_client_init()
