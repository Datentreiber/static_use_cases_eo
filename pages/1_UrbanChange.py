import ee
import streamlit as st
import geemap.foliumap as geemap
import pandas as pd
import folium
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")

from ee_init import ensure_ee_ready
ensure_ee_ready()


GHSL_PREFIX = "JRC/GHSL/P2023A/GHS_BUILT_S"  # built_surface, built_surface_nres
ghsl_vis = {
    "min": 0,
    "max": 8000,  # 0..8000 m² of built-up per 100 m grid is typical for city cores
    "palette": ["000000", "1f78b4", "a6cee3", "b2df8a", "ffff99", "fdbf6f", "e31a1c"]
}


def urban_change_simple():
    """Show me how much Shenzhen has grown in size."""
    Map = geemap.Map(center=[22.6, 114], zoom=10, basemap="SATELLITE") # Uses Esri.WorldImagery on Shenzhen
    Map.add_basemap("CartoDB.PositronOnlyLabels")  # labels-only overlay

    built_surface_1980 = ee.Image(f"{GHSL_PREFIX}/1980").select("built_surface")
    built_surface_2025 = ee.Image(f"{GHSL_PREFIX}/2025").select("built_surface")

    left_layer = geemap.ee_tile_layer(built_surface_1980, ghsl_vis, "Built Surface 1980", opacity=0.6)
    right_layer = geemap.ee_tile_layer(built_surface_2025, ghsl_vis, "Built Surface 2025", opacity=0.6)

    Map.split_map(left_layer, right_layer)
    # Add continuous colorbar
    Map.add_colorbar(
        vis_params=ghsl_vis,
        label="Built-up area (m² per 100 m grid)",
        orientation="horizontal",  # or "vertical"
        background_color="white",        # <-- sets the bounding box background
        font_size=12,           # optional, makes labels more visible
        position="bottomright"  # optional, controls placement
    )
    Map.to_streamlit()


def urban_change_geocode_low_values_masked():
    """Show me how much Shenzhen has grown in size. Let me select a location, mask out low values and set the opacity of layers."""
    Map = geemap.Map(center=[22.6, 114], zoom=10, basemap="SATELLITE") # Uses Esri.WorldImagery on Shenzhen
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


    built_surface_1980 = ee.Image(f"{GHSL_PREFIX}/1980").select("built_surface")
    built_surface_2025 = ee.Image(f"{GHSL_PREFIX}/2025").select("built_surface")

    # Apply mask: keep only pixels > threshold (and also mask out nodata with selfMask if desired)
    mask_threshold = 1
    built_surface_1980_masked = built_surface_1980.updateMask(built_surface_1980.gt(mask_threshold)).selfMask()
    built_surface_2025_masked = built_surface_2025.updateMask(built_surface_2025.gt(mask_threshold)).selfMask()

    opacity = st.slider("Layer opacity", 0.0, 1.0, 0.7, 0.05)
    left_layer = geemap.ee_tile_layer(built_surface_1980_masked, ghsl_vis, "Built Surface 1980", opacity=opacity)
    right_layer = geemap.ee_tile_layer(built_surface_2025_masked, ghsl_vis, "Built Surface 2025", opacity=opacity)

    Map.split_map(left_layer, right_layer)
    # Add continuous colorbar
    Map.add_colorbar(
        vis_params=ghsl_vis,
        label="Built-up area (m² per 100 m grid)",
        orientation="horizontal",  # or "vertical"
        background_color="white",        # <-- sets the bounding box background
        font_size=12,           # optional, makes labels more visible
        position="bottomright"  # optional, controls placement
    )
    Map.addLayerControl()
    Map.to_streamlit()


def urban_change_time_slider():
    """Show me how much Shenzhen has grown in size. Let me select all available years."""
    # Discrete epochs to pick from
    years = [1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030]
    year = st.select_slider("Built-up year", options=years, value=1980)

    Map = geemap.Map(center=[22.6, 114], zoom=10, basemap="SATELLITE")  # Esri.WorldImagery
    Map.add_basemap("CartoDB.PositronOnlyLabels")  # labels-only overlay

    # Layer for the selected year
    img = ee.Image(f"{GHSL_PREFIX}/{year}").select("built_surface")
    Map.addLayer(img, ghsl_vis, f"Built Surface {year}", opacity=0.6)

    # Colorbar and controls
    Map.add_colorbar(
        vis_params=ghsl_vis,
        label="Built-up area (m² per 100 m grid)",
        orientation="horizontal",
        background_color="white",
        font_size=12,
        position="bottomright",
    )
    Map.to_streamlit()


def urban_change_multi_select():
    """Show me how much Shenzhen has grown in size. Let me select multiple years."""
    Map = geemap.Map(center=[22.6, 114], zoom=10, basemap="SATELLITE")  # Esri.WorldImagery
    Map.add_basemap("CartoDB.PositronOnlyLabels")  # labels-only overlay

    row1_col1, row1_col2 = st.columns([3, 1])
    # width = 950
    # height = 600
    years = [1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030]

    with row1_col2:
        selected_year = st.multiselect("Select a year", years)

    if selected_year:
        for year in selected_year:
            # Map.addLayer(getNLCD(year), {}, "NLCD " + year)
            Map.addLayer(ee.Image(f"{GHSL_PREFIX}/{year}").select("built_surface"), ghsl_vis, f"Built Surface {year}", opacity=0.6)

        Map.add_colorbar(
            vis_params=ghsl_vis,
            label="Built-up area (m² per 100 m grid)",
            orientation="horizontal",
            background_color="white",
            font_size=12,
            position="bottomright",
        )
        with row1_col1:
            Map.to_streamlit()
    else:
        with row1_col1:
            Map.to_streamlit()

def urban_change_split_select():
    """Show me how much Shenzhen has grown in size. How much has the built-up area increased?"""
    Map = geemap.Map(center=[22.6, 114], zoom=10, basemap="SATELLITE") # Uses Esri.WorldImagery
    Map.add_basemap("CartoDB.PositronOnlyLabels")  # labels-only overlay

    years = [1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030]
    layers = {
        f"Built Surface {year}": geemap.ee_tile_layer(
            ee.Image(f"{GHSL_PREFIX}/{year}").select("built_surface"), 
            ghsl_vis, f"Built Surface {year}", opacity=0.6) for year in years
    }

    col1, col2 = st.columns([4, 1])
    with col2:
        options = list(layers.keys())
        left = st.selectbox("Select a left year", options, index=0)
        right = st.selectbox("Select a right year", options, index=9)

        left_layer = layers[left]
        right_layer = layers[right]
        Map.split_map(left_layer, right_layer)

    with col1:
        Map.add_colorbar(
            vis_params=ghsl_vis,
            label="Built-up area (m² per 100 m grid)",
            orientation="horizontal",  # or "vertical"
            background_color="white",        # <-- sets the bounding box background
            font_size=12,           # optional, makes labels more visible
            position="bottomright"  # optional, controls placement
        )
        Map.addLayerControl()
        Map.to_streamlit()


def urban_change_with_stats():
    """Show me how much Shenzhen has grown in size. How much has the built-up area increased?"""
    region = ee.Geometry.Rectangle([113.75, 22.36, 114.63, 22.89]) # Shenzhen

    Map = geemap.Map(center=[22.6, 114], zoom=10, basemap="SATELLITE") # Uses Esri.WorldImagery
    Map.add_basemap("CartoDB.PositronOnlyLabels")  # labels-only overlay

    built_surface_1980 = ee.Image(f"{GHSL_PREFIX}/1980").select("built_surface")
    built_surface_2025 = ee.Image(f"{GHSL_PREFIX}/2025").select("built_surface")

    left_layer = geemap.ee_tile_layer(built_surface_1980, ghsl_vis, "Built Surface 1980", opacity=0.6)
    right_layer = geemap.ee_tile_layer(built_surface_2025, ghsl_vis, "Built Surface 2025", opacity=0.6)

    Map.split_map(left_layer, right_layer)
    # Add continuous colorbar
    Map.add_colorbar(
        vis_params=ghsl_vis,
        label="Built-up area (m² per 100 m grid)",
        orientation="horizontal",  # or "vertical"
        background_color="white",        # <-- sets the bounding box background
        font_size=12,           # optional, makes labels more visible
        position="bottomright"  # optional, controls placement
    )
    Map.addLayerControl()


    all_years = list(range(1975, 2035, 5))  # 1975..2030 inclusive

    def ghsl_image(year):
        return ee.Image(f"{GHSL_PREFIX}/{int(year)}").select("built_surface")
    
    def builtup_km2(year: int) -> float:
        img = ghsl_image(year)
        # Sum the built-up surface values across the region.
        # Note: The pixel value is m² of built-up in each 100 m cell,
        # so a simple sum at 100 m scale yields total m² of built-up.
        stat = img.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=region,
            scale=100,
            maxPixels=1e13,
            tileScale=4,
        ).get("built_surface")
        val = stat.getInfo()
        if val is None:
            return 0.0
        return float(val) / 1e6  # m² -> km²

    series = []
    for y in all_years:
        try:
            area_km2 = builtup_km2(y)
        except Exception:
            # In case of transient API errors, try once more
            area_km2 = builtup_km2(y)
        series.append({"year": y, "built_up_km2": area_km2})

    df = pd.DataFrame(series).sort_values("year").reset_index(drop=True)

    # Make a figure object (don’t call plt.show() in Streamlit)
    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    ax.plot(df["year"], df["built_up_km2"], marker="o")
    ax.set_title("Shenzhen Built-up Surface Area (GHSL, 1975–2025)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Built-up area (km²)")
    ax.grid(True, alpha=0.3)

    left, right = st.columns([3, 2], gap="large")
    with left:
        Map.to_streamlit(height=650)  # width handled by the column
    with right:
        st.pyplot(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True)


def app():
    st.title("Urban Change Variants")

    apps = [
    	"URBAN CHANGE WITH STATS",
        "URBAN CHANGE SIMPLE", 
        "URBAN CHANGE MULTI SELECT",
        "URBAN CHANGE SPLIT SELECT",
        "URBAN CHANGE TIME SLIDER", 
        "URBAN CHANGE CHOOSE LOCATION + LOW VALUES MASKED", 
    ]

    selected_app = st.selectbox("Select an app", apps)

    if selected_app == "URBAN CHANGE SIMPLE":
        urban_change_simple()
    elif selected_app == "URBAN CHANGE MULTI SELECT":
        urban_change_multi_select()
    elif selected_app == "URBAN CHANGE SPLIT SELECT":
        urban_change_split_select()
    elif selected_app == "URBAN CHANGE TIME SLIDER":
        urban_change_time_slider()
    elif selected_app == "URBAN CHANGE CHOOSE LOCATION + LOW VALUES MASKED":
        urban_change_geocode_low_values_masked()
    elif selected_app == "URBAN CHANGE WITH STATS":
        urban_change_with_stats()

app()
