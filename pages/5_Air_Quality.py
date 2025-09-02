# Nitrogen Dioxide (NO₂) Monitoring with Sentinel-5P in Streamlit + geemap

import streamlit as st
import ee
import datetime
import folium
import calendar
import geemap.foliumap as geemap

st.set_page_config(page_title="Sentinel-5P NO₂ Dashboard", layout="wide")

from ee_init import ensure_ee_ready
ensure_ee_ready()



def no2():
    """Show me how much Shenzhen has grown in size. How much has the built-up area increased?"""
    Map = geemap.Map(zoom=1, basemap="SATELLITE") # Uses Esri.WorldImagery on Shenzhen
    Map.add_basemap("CartoDB.PositronOnlyLabels")  # labels-only overlay

    keyword = st.text_input("Search for a location:", "")
    if keyword:
        locations = geemap.geocode(keyword)
        if locations is not None and len(locations) > 0:
            str_locations = [str(g)[1:-1] for g in locations]
            location = st.selectbox("Select a location:", str_locations)
            loc_index = str_locations.index(location)
            selected_loc = locations[loc_index]
            lat, lng = selected_loc.lat, selected_loc.lng
            folium.Marker(location=[lat, lng], popup=location).add_to(Map)
            Map.set_center(lng, lat, 8)
            st.session_state["zoom_level"] = 8

    month2idx = {name: i for i, name in enumerate(calendar.month_name) if name}
    no2_vis = {"min": 0, "max": 0.0002, "palette": ['black', 'blue', 'purple', 'cyan', 'green', 'yellow', 'red']}

    st.title(f"Average NO2 concentration")
    col1, col2 = st.columns([4, 1])
    with col2:
        max_year = datetime.date.today().year
        year = st.selectbox("Select a Year", list(range(2019, max_year + 1)), index=max_year - 2019)
        month = st.selectbox("Select a Month", [calendar.month_name[m] for m in range(1, 12 + 1)], index=7)

        # Compute date range
        start_date = datetime.date(int(year), int(month2idx[month]), 1)
        end_date = (start_date.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)  # next month's first day
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        col = (
            ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_NO2')
            .select('NO2_column_number_density')
            .filterDate(start_str, end_str)
            .mean()
        )

        right_layer = geemap.ee_tile_layer(
            col, no2_vis, f"NO2 {start_str}-{end_str}", opacity=1.0
        )
        Map.split_map("", right_layer)

    with col1:
        Map.add_colorbar(
            vis_params=no2_vis,
            label="NO2 Concentration (mol/m²)",
            orientation="horizontal",  # or "vertical"
            background_color="white",        # <-- sets the bounding box background
            font_size=12,           # optional, makes labels more visible
            position="bottomright"  # optional, controls placement
        )
        Map.to_streamlit()


def app():

    ee_authenticate()

    apps = [
        "NO2", 
    ]

    selected_app = st.selectbox("Select an app", apps)

    if selected_app == "NO2":
        no2()

app()
