# Sommer-Hitzeinseln – Brandenburg: 2018 vs. 2024
# Vergleich nebeneinander (zwei Karten-Spalten)

import ee
import streamlit as st
import geemap

# Komponenten aus dem Stack
from blocks.components.util.scaffold import ee_authenticate
from blocks.components.gee.aoi_from_spec import aoi_from_spec
from blocks.components.visual.split_map_right import render_split_map_right
from ee_init import ensure_ee_ready

st.title("Sommer-Hitzeinseln – Brandenburg: 2018 vs. 2024")

# 1) EE initialisieren
ensure_ee_ready()

# 2) AOI: Bundesland Brandenburg (exakte Grenze, soweit verfügbar)
def get_brandenburg_geometry():
    # Versuche: Admin-Grenze (GAUL Level 1). Fallback: Geocoder-Bounding-Box.
    try:
        gaul = ee.FeatureCollection("FAO/GAUL/2015/level1")
        aoi = gaul.filter(ee.Filter.And(
            ee.Filter.eq("ADM1_NAME", "Brandenburg"),
            ee.Filter.eq("ADM0_NAME", "Germany")
        )).geometry()
        # Sicherstellen, dass etwas gefunden wurde
        _bounds = aoi.bounds()
        return aoi
    except Exception:
        pass
    # Fallback: Geocoder → Bounding Box
    spec = {"type": "place", "name": "Brandenburg, Germany"}
    return aoi_from_spec(spec)

aoi = get_brandenburg_geometry()

# 3) Sommer-Fenster (Juni–August) und LST aus Landsat L2 (LC08/LC09)
VIS = {
    "min": 20,
    "max": 45,
    "opacity": 0.6,
    "palette": ["#313695","#4575b4","#74add1","#abd9e9","#e0f3f8","#ffffbf","#fee090","#fdae61","#f46d43","#d73027","#a50026"]
}

def _mask_l2_qa(img):
    # QA_PIXEL Bits 1–5 = 0 (keine Wolken, Cirrus, Schatten, Schnee)
    qa = img.select("QA_PIXEL")
    mask = (qa.bitwiseAnd(1 << 1).eq(0)
            .And(qa.bitwiseAnd(1 << 2).eq(0))
            .And(qa.bitwiseAnd(1 << 3).eq(0))
            .And(qa.bitwiseAnd(1 << 4).eq(0))
            .And(qa.bitwiseAnd(1 << 5).eq(0)))
    return img.updateMask(mask)

def _to_celsius(img):
    # Invarianten: LST_K = ST_B10 * 0.00341802 + 149.0 ; dann -273.15
    lst_k = img.select("ST_B10").multiply(0.00341802).add(149.0)
    lst_c = lst_k.subtract(273.15).rename("LST_C")
    return lst_c

def summer_dates(year: int):
    start = ee.Date.fromYMD(year, 6, 1)
    end = ee.Date.fromYMD(year, 8, 31)
    return start, end

def summer_lst_image(year: int, aoi_geom: ee.Geometry) -> ee.Image:
    start, end = summer_dates(year)
    col8 = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
            .filterDate(start, end)
            .filterBounds(aoi_geom)
            .map(_mask_l2_qa)
            .select(["ST_B10"]))
    col9 = (ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
            .filterDate(start, end)
            .filterBounds(aoi_geom)
            .map(_mask_l2_qa)
            .select(["ST_B10"]))
    col = col8.merge(col9)
    # GUARD: leere Sammlung
    try:
        if col.size().getInfo() == 0:
            st.warning(f"Für den Sommer {year} wurden hier keine passenden Landsat-L2-Aufnahmen gefunden. "
                       f"Wir können alternativ das Zeitfenster leicht erweitern.")
    except Exception:
        # Wenn getInfo im Headless-Betrieb nicht möglich ist, fahren wir fort.
        pass
    # Median + in °C umrechnen
    lst_median = col.median()
    lst_c = _to_celsius(lst_median).clip(aoi_geom)
    return lst_c

year_left = 2018
year_right = 2024

img_left = summer_lst_image(year_left, aoi)
img_right = summer_lst_image(year_right, aoi)

# 4) Darstellung: Zwei Karten nebeneinander (jeweils rechte Seite als Layer)
c1, c2 = st.columns(2)

with c1:
    st.subheader(f"Sommer {year_left}")
    m_left = geemap.Map(plugin_Draw=False, locate_control=False)
    m_left.center_object(aoi, 7)
    render_split_map_right(
        m=m_left,
        right_layer=img_left,
        vis_params=VIS,
        title=f"LST (°C) – {year_left}",
        height=680,
        colorbar_label="LST (°C)"
    )

with c2:
    st.subheader(f"Sommer {year_right}")
    m_right = geemap.Map(plugin_Draw=False, locate_control=False)
    m_right.center_object(aoi, 7)
    render_split_map_right(
        m=m_right,
        right_layer=img_right,
        vis_params=VIS,
        title=f"LST (°C) – {year_right}",
        height=680,
        colorbar_label="LST (°C)"
    )

st.caption("Hinweis: Links und rechts sind separat zoom-/verschiebbar. Farben zeigen die Landoberflächentemperatur (°C) als Sommer-Median.")
