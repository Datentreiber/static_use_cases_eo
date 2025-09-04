import ee
import streamlit as st
import geemap.foliumap as geemap
import folium

st.set_page_config(layout="wide")


from ee_init import ensure_ee_ready
ensure_ee_ready()


def mask_landsat_l2(img):
    qa = img.select('QA_PIXEL')
    cond = (qa.bitwiseAnd(1 << 1).eq(0)   # dilated
            .And(qa.bitwiseAnd(1 << 2).eq(0))  # cirrus
            .And(qa.bitwiseAnd(1 << 3).eq(0))  # cloud
            .And(qa.bitwiseAnd(1 << 4).eq(0))  # shadow
            .And(qa.bitwiseAnd(1 << 5).eq(0))) # snow
    return img.updateMask(cond).copyProperties(img, img.propertyNames())

# -------------------- Data builders --------------------
def get_landsat_lst(aoi, start, end):
    col = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
           .merge(ee.ImageCollection('LANDSAT/LC09/C02/T1_L2'))
           .filterBounds(aoi)
           .filterDate(start, end)
           .map(mask_landsat_l2)
           .map(lambda img: img.addBands(
               img.select('ST_B10')
                  .multiply(0.00341802).add(149.0).subtract(273.15)
                  .rename('LST_C'),
               None, True)))
    return col.select('LST_C').median().clip(aoi)


def coolmap_simple_select_city():
    """Where are cool spots in X?"""
    # -------------------- Defaults --------------------
    POI_LON, POI_LAT = 2.3522, 48.8566 # Paris
    RADIUS_KM = 15         # AOI radius
    YEAR = 2024            # Summer year

    TEMP_OPACITY = 0.6
    temp_vis = {
        "min": 20,
        "max": 45, 
        "palette": ['#313695','#4575b4','#74add1','#abd9e9','#e0f3f8','#ffffbf',
                    '#fee090','#fdae61','#f46d43','#d73027','#a50026']
    }

    Map = geemap.Map(center=(POI_LAT, POI_LON), zoom=12, basemap="SATELLITE") # Uses Esri.WorldImagery on Shenzhen
    Map.add_basemap("CartoDB.PositronOnlyLabels")  # labels-only overlay

    keyword = st.text_input("Search for a location:", "")
    if keyword:
        locations = geemap.geocode(keyword)
        if locations is not None and len(locations) > 0:
            str_locations = [str(g)[1:-1] for g in locations]
            location = st.selectbox("Select a location:", str_locations)
            loc_index = str_locations.index(location)
            selected_loc = locations[loc_index]
            POI_LAT, POI_LON = selected_loc.lat, selected_loc.lng
            folium.Marker(location=[POI_LAT, POI_LON], popup=location).add_to(Map)
            Map.set_center(POI_LON, POI_LAT, 12)
            st.session_state["zoom_level"] = 12

    # -------------------- Helpers --------------------
    def make_aoi(lon, lat, radius_km):
        return ee.Geometry.Point([lon, lat]).buffer(radius_km * 1000).bounds()

    def summer_dates(year):
        start = ee.Date.fromYMD(year, 6, 1)
        end   = ee.Date.fromYMD(year, 8, 31).advance(1, 'day')  # exclusive
        return start, end

    # -------------------- Build imagery --------------------
    AOI = make_aoi(POI_LON, POI_LAT, RADIUS_KM)
    start, end = summer_dates(YEAR)
    lst  = get_landsat_lst(AOI, start, end)
    right_layer = geemap.ee_tile_layer(lst, temp_vis, 'Temperature (°C)', opacity=TEMP_OPACITY)

    Map.split_map("", right_layer) # empty left layer
    Map.add_colorbar(
        vis_params=temp_vis,
        label="Temperature (°C)",
        orientation="horizontal",  # or "vertical"
        background_color="white",        # <-- sets the bounding box background
        font_size=14,           # optional, makes labels more visible
        position="bottomright"  # optional, controls placement
    )

    # # Info in notebook console
    # print('AOI radius (km):', RADIUS_KM)
    # print('Summer:', YEAR, start.format('YYYY-MM-dd').getInfo(), '→', end.format('YYYY-MM-dd').getInfo())
    # print('S2 CLOUDY_PIXEL_PERCENTAGE ≤', CLOUD_PCT, '%')

    Map.to_streamlit()


def app():
    st.title("Coolmap Variants")

    

    apps = [
        "COOLMAP SIMPLE SELECT CITY"
    ]

    selected_app = st.selectbox("Select an app", apps)

    if selected_app == "COOLMAP SIMPLE SELECT CITY":
        coolmap_simple_select_city()

app()
