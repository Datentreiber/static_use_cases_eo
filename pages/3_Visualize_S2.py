import ee
import streamlit as st
import geemap.foliumap as geemap
import folium
import datetime

st.set_page_config(page_title="Sentinel-2 Visualizations", layout="wide")

# Visualization configurations (match the GEE script)
MAP_PARAMS: dict[str, list[str]] = {
    "Natural Color (Red/Green/Blue)": ["B4", "B3", "B2"],
    "Vegetation": ["B12", "B8", "B4"],
    "Land/Water": ["B8", "B11", "B4"],
    "Color Infrared": ["B8", "B4", "B3"],
}

shared_vis = {"min": 0, "max": 0.325, "gamma": 1.0}


from ee_init import ensure_ee_ready


def show_s2_fccs():
    ee_authenticate()
    Map = geemap.Map(center=[51.495065, -0.126343], zoom=10, basemap="SATELLITE")  # Uses Esri.WorldImagery on London
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
            Map.set_center(lng, lat, 12)
            st.session_state["zoom_level"] = 12

    # Build Sentinel-2 quarterly median mosaic
    @st.cache_data(show_spinner=False)
    def fetch_mosaic(start_iso: str, end_iso: str) -> tuple[ee.Image | None, int]:
        """Returns (median_image, collection_size). If no imagery, image is None."""
        col = (
            ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
            .filterDate(start_iso, end_iso)
            .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', 10))  # reduced from 30% to 20%
            # Scale reflectance to 0-1 for visualization
            .map(lambda img: img.divide(10000))
        )
        # size = int(col.size().getInfo())  # server call; cached by @st.cache_data
        # if size == 0:
        #     return None, 0
        img = col.median()
        return img#, size

    st.title("Sentinel-2 Visualizations")
    quarters = {
        "Q1 (Jan-Mar)": 1,
        "Q2 (Apr-Jun)": 4,
        "Q3 (Jul-Sep)": 7,
        "Q4 (Oct-Dec)": 10,
    }

    col1, col2 = st.columns([4, 1])
    with col2:
        options = list(MAP_PARAMS.keys())
        viz_type = st.selectbox("Select a Visualization", options, index=0)

        max_year = datetime.date.today().year
        year = st.selectbox("Select a Year", list(range(2016, max_year + 1)), index=max_year - 2016)
        quarter_label = st.selectbox("Select a Quarter", list(quarters.keys()), index=2)  # default Q3

        # Compute quarterly date range (start inclusive, end exclusive)
        start_month = quarters[quarter_label]
        start_date = datetime.date(int(year), int(start_month), 1)

        end_month = start_month + 3
        if end_month > 12:
            end_date = datetime.date(int(year) + 1, end_month - 12, 1)
        else:
            end_date = datetime.date(int(year), end_month, 1)

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        image = fetch_mosaic(start_str, end_str)
        # image, n_images = fetch_mosaic(start_str, end_str)
        # if image is None or n_images == 0:
        #     st.error(
        #         f"No Sentinel-2 images found between {start_str} and {end_str} "
        #         f"({quarter_label} {year}) with ≤20% cloud cover. Try another quarter/year or change the location."
        #     )
        #     st.stop()

        right_layer = geemap.ee_tile_layer(
            image, {**shared_vis, "bands": MAP_PARAMS[viz_type]}, viz_type, opacity=1.0
        )
        Map.split_map("", right_layer)

    with col1:
        Map.to_streamlit()


def app():
    ensure_ee_ready()


    apps = [
        "S2 False Color Composites"
    ]

    selected_app = st.selectbox("Select an app", apps)

    if selected_app == "S2 False Color Composites":
        show_s2_fccs()

app()
