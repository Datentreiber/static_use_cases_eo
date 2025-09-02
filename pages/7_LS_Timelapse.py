import io
import folium
import ee
import requests
import streamlit as st
import geemap.foliumap as geemap
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageSequence


from ee_init import ensure_ee_ready
ensure_ee_ready()


st.set_page_config(page_title="Landsat Timelapse from 1984-2025", layout="wide")

st.title("Landsat Timelapse from 1984-2025")

# ---------- Initialize Earth Engine ----------
with st.spinner("Initializing Google Earth Engine..."):
    try:
        ee.Initialize()
    except Exception:
        geemap.ee_initialize()

USE_RGB = True
# Visualization (reflectance range)
if USE_RGB:
    vmin = 0.00
    vmax = 0.25
else:
    # Visualization (reflectance range)
    vmin = 0.03
    vmax = 0.40
start_year = 1984
end_year = 2025

# pre-filters (metadata)
max_cloud = 40
min_sun_elev = 5
min_aoi_cover_pct = 25

fps = 8
dimensions = 600
crs = "EPSG:3857"
overlay_year = True
font_size = 28
margin = 12

# starting location = Hong Kong Airport
lng = 113.91555356276417
lat = 22.30762833157407
location = "Hong Kong Airport"

keyword = st.text_input("Search for a location:", "")
if keyword:
    locations = geemap.geocode(keyword)
    if locations is not None and len(locations) > 0:
        str_locations = [str(g)[1:-1] for g in locations]
        location = st.selectbox("Select a location:", str_locations)
        loc_index = str_locations.index(location)
        selected_loc = locations[loc_index]
        lat, lng = selected_loc.lat, selected_loc.lng

radius_km = st.slider("Radius in km", 2.5, 12.5, 9.0, step=0.5)
# -------------------- Helpers --------------------
def make_aoi(lon, lat, radius_km):
    return ee.Geometry.Point([lon, lat]).buffer(radius_km * 1000).bounds()

# -------------------- Build imagery --------------------
region = make_aoi(lng, lat, radius_km)

# ---------- Landsat collections (C2 L2, Tier 1) ----------
LT04 = ee.ImageCollection("LANDSAT/LT04/C02/T1_L2")
LT05 = ee.ImageCollection("LANDSAT/LT05/C02/T1_L2")
LE07 = ee.ImageCollection("LANDSAT/LE07/C02/T1_L2")
LC08 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
LC09 = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
landsat_raw_all = LT04.merge(LT05).merge(LE07).merge(LC08).merge(LC09)

# ---------- Helpers ----------
def add_months(py_dt, months):
    m = py_dt.month - 1 + months
    y = py_dt.year + m // 12
    m = m % 12 + 1
    return datetime(y, m, 1)

def build_periods(start_y, end_y):
    start = datetime(start_y, 1, 1)
    end = datetime(end_y, 12, 31)
    size = 12
    periods = []
    cur = datetime(start.year, start.month, 1)
    while cur <= end:
        nxt = add_months(cur, size)
        label = f"{cur.year}"
        periods.append({"start": cur, "end": nxt, "label": label})
        cur = nxt
    return periods

def add_aoi_coverage_prop(img):
    inter = img.geometry().intersection(region, ee.ErrorMargin(1))
    cover = inter.area(1).divide(region.area(1))  # 0..1
    return img.set({"aoi_cover": cover})

def apply_scale_mask_rename(img):
    # QA-based cloud/shadow/snow mask (QA_PIXEL)
    qa = img.select("QA_PIXEL")
    dilated = qa.bitwiseAnd(1 << 1).eq(0)
    cirrus  = qa.bitwiseAnd(1 << 2).eq(0)  # cirrus not present on TM, harmless
    cloud   = qa.bitwiseAnd(1 << 3).eq(0)
    shadow  = qa.bitwiseAnd(1 << 4).eq(0)
    snow    = qa.bitwiseAnd(1 << 5).eq(0)
    qa_mask = dilated.And(cirrus).And(cloud).And(shadow).And(snow)

    # Saturation mask
    rad_sat = img.select("QA_RADSAT")
    sat_mask = rad_sat.eq(0)

    img = img.updateMask(qa_mask.And(sat_mask))

    # Scale reflectance (C2 L2): SR_B* * 0.0000275 + -0.2
    optical = img.select("SR_B.*").multiply(0.0000275).add(-0.2)
    img = img.addBands(optical, None, True)

    # Select Bands
    # OLI (L8/9): BLUE=B2, GREEN=B3, RED=B4, NIR=B5, SWIR1=B6
    # TM/ETM+ (L4/5/7): BLUE=B1, GREEN=B2, RED=B3, NIR=B4, SWIR1=B5
    if USE_RGB:
        def rename_oli(i):    # L8/9
            return i.select(["SR_B2", "SR_B3", "SR_B4"], ["RED", "NIR", "SWIR1"])
        def rename_tm_etm(i): # L4/5/7
            return i.select(["SR_B1", "SR_B2", "SR_B3"], ["RED", "NIR", "SWIR1"])
    else:
        # FOR SWIR/NIR/RED
        def rename_oli(i):    # L8/9
            return i.select(["SR_B4", "SR_B5", "SR_B6"], ["RED", "NIR", "SWIR1"])
        def rename_tm_etm(i): # L4/5/7
            return i.select(["SR_B3", "SR_B4", "SR_B5"], ["RED", "NIR", "SWIR1"])
    

    renamed = ee.Image(
        ee.Algorithms.If(
            img.bandNames().contains("SR_B6"),
            rename_oli(img),
            rename_tm_etm(img),
        )
    )
    return renamed.copyProperties(img, ["system:time_start"])

def download_gif(url: str) -> bytes:
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return r.content

def overlay_years_on_gif(gif_bytes: bytes, year_list, fps: int, font_size: int = 28, margin: int = 12) -> bytes:
    # Draw year (top-right) per frame using Pillow
    with Image.open(io.BytesIO(gif_bytes)) as im:
        frames = []
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        for idx, frame in enumerate(ImageSequence.Iterator(im)):
            text = str(year_list[min(idx, len(year_list)-1)])
            frame = frame.convert("RGBA")
            w, h = frame.size

            # Measure text
            draw_tmp = ImageDraw.Draw(frame)
            # textbbox is more reliable across Pillow versions
            bbox = draw_tmp.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

            x = margin #max(0, w - margin - tw)
            y = margin

            # Draw semi-transparent box for readability
            overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(overlay)
            pad = 4
            d.rectangle([x - pad, y - pad, x + tw + pad, y + th + pad], fill=(0, 0, 0, 128))
            d.text((x, y), text, font=font, fill=(255, 255, 255, 255))

            composed = Image.alpha_composite(frame, overlay)
            frames.append(composed.convert("P", palette=Image.ADAPTIVE))

        buf = io.BytesIO()
        duration = max(1, int(1000 / max(1, fps)))  # ms per frame
        frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:],
                       duration=duration, loop=0, disposal=2)
        return buf.getvalue()

# ---------- Periods ----------
start_y = int(start_year)
end_y = int(end_year)
periods_py = build_periods(start_y, end_y)
periods_ee = ee.List([
    ee.Dictionary({"start": ee.Date(p["start"]), "end": ee.Date(p["end"]), "label": p["label"]})
    for p in periods_py
])
# Year per period for overlay
years_for_frames = [p["start"].year for p in periods_py]

# ---------- Prefilter to speed things up ----------
min_aoi_cover_frac = float(min_aoi_cover_pct) / 100.0

landsat_window = (
    landsat_raw_all
    .filterDate(f"{start_y}-01-01", f"{end_y+1}-01-01")
    .filterBounds(region)
)
prefiltered_fixed = (
    landsat_window
    .map(add_aoi_coverage_prop)
    .filter(ee.Filter.gte("SUN_ELEVATION", min_sun_elev))
    .filter(ee.Filter.gte("aoi_cover", min_aoi_cover_frac))
)
before_count = landsat_window.size().getInfo()

while True:
    prefiltered = prefiltered_fixed.filter(ee.Filter.lte("CLOUD_COVER", max_cloud))
    after_count  = prefiltered.size().getInfo()
    perc_retained = 100.0 * after_count / max(1, before_count)
    # st.write(
    #     f"{max_cloud:.1f}% Clouds: Scenes used: **{after_count}** / **{before_count}** ({perc_retained:.1f}% retained)"
    # )
    if perc_retained < 40.0 or max_cloud < 10.0:
        break
    max_cloud = max(5, max_cloud - 10)


landsat = prefiltered.map(apply_scale_mask_rename)

# ---------- Build period composites ----------
def composite_from_period(d):
    d = ee.Dictionary(d)
    s = ee.Date(d.get("start"))
    e = ee.Date(d.get("end"))
    label = ee.String(d.get("label"))
    comp = landsat.filterDate(s, e).median()
    return comp.set({"system:time_start": s.millis(), "label": label})

composites = ee.ImageCollection(periods_ee.map(composite_from_period))

# ---------- Visualization (SWIR1/NIR/RED or RGB) ----------
vis_params = {"bands": ["SWIR1", "NIR", "RED"], "min": vmin, "max": vmax}
rgbVis = composites.map(lambda img: img.visualize(**vis_params).clip(region))
gif_params = {"region": region, "dimensions": dimensions, "crs": crs, "framesPerSecond": fps}

# ---------- UI Layout ----------
left, right = st.columns([1, 1])

with left:
    st.subheader("Map")
    m = geemap.Map(center=[lat, lng], zoom=12, basemap="SATELLITE")  # Uses Esri.WorldImagery
    m.add_basemap("CartoDB.PositronOnlyLabels")  # labels-only overlay
    if keyword:
        if locations is not None and len(locations) > 0:
            folium.Marker(location=[lat, lng], popup=location).add_to(m)
            zoom_lvl = 11
            if radius_km <= 7.0:
                zoom_lvl = 12
            if radius_km <= 5.0:
                zoom_lvl = 13
            m.set_center(lng, lat, zoom_lvl)
            st.session_state["zoom_level"] = zoom_lvl

    # Add first frame preview (raw composite, not visualized imagecollection)
    last_comp = ee.Image(composites.sort('system:time_start', False).first()).clip(region)
    m.addLayer(last_comp, vis_params, "Yearly last frame")

    m.to_streamlit(height=640)

with right:
    st.subheader("Animation")
    try:
        # 1) Get GIF URL from EE
        gif_url = rgbVis.getVideoThumbURL(gif_params)

        if overlay_year:
            # 2) Download
            raw_gif = download_gif(gif_url)
            # 3) Overlay year per frame
            annotated = overlay_years_on_gif(
                raw_gif, years_for_frames, fps=fps, font_size=font_size, margin=margin
            )
            st.image(annotated, caption=f"Yearly Timelapse ({start_y}–{end_y})", use_container_width=True)
            st.download_button("Download annotated GIF", data=annotated, file_name=f"landsat_{location}_1984_2025.gif", mime="image/gif")
            st.markdown(f"[Open original GIF URL (no overlay)]({gif_url})")
        else:
            st.image(gif_url, caption=f"Yearly Timelapse ({start_y}–{end_y})", use_container_width=True)
            st.markdown(f"[Open GIF URL]({gif_url})")

    except Exception as e:
        st.error(f"Failed to create/annotate animation: {e}")
        st.info("Try relaxing filters, shrinking the time range, or verifying Earth Engine auth.")
