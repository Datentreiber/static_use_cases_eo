import io
import ee
import streamlit as st
import geemap.foliumap as geemap
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageSequence
import requests, io

st.set_page_config(page_title="Timelapses", layout="wide")

COUNTRIES = ['Abyei Area',
 'Afghanistan',
 'Akrotiri',
 'Aksai Chin',
 'Albania',
 'Algeria',
 'American Samoa',
 'Andorra',
 'Angola',
 'Anguilla',
 'Antarctica',
 'Antigua & Barbuda',
 'Argentina',
 'Armenia',
 'Aruba',
 'Ashmore & Cartier Is',
 'Australia',
 'Austria',
 'Azerbaijan',
 'Bahamas, The',
 'Bahrain',
 'Bangladesh',
 'Barbados',
 'Belarus',
 'Belgium',
 'Belize',
 'Benin',
 'Bermuda',
 'Bhutan',
 'Bir Tawil',
 'Bolivia',
 'Bosnia & Herzegovina',
 'Botswana',
 'Bouvet Island',
 'Brazil',
 'British Indian Ocean Terr',
 'British Virgin Is',
 'Brunei',
 'Bulgaria',
 'Burkina Faso',
 'Burma',
 'Burundi',
 'Cabo Verde',
 'Cambodia',
 'Cameroon',
 'Canada',
 'Cayman Is',
 'Central African Rep',
 'Chad',
 'Chile',
 'China',
 'Christmas I',
 'Clipperton Island',
 'Cocos (Keeling) Is',
 'Colombia',
 'Comoros',
 'Cook Is',
 'Coral Sea Is',
 'Costa Rica',
 "Cote d'Ivoire",
 'Croatia',
 'Cuba',
 'Curacao',
 'Cyprus',
 'Czechia',
 'Dem Rep of the Congo',
 'Demchok Area',
 'Denmark',
 'Dhekelia',
 'Djibouti',
 'Dominica',
 'Dominican Republic',
 'Dragonja River Mouth',
 'Dramana-Shakatoe Area',
 'Ecuador',
 'Egypt',
 'El Salvador',
 'Equatorial Guinea',
 'Eritrea',
 'Estonia',
 'Ethiopia',
 'Falkland Islands',
 'Faroe Is',
 'Fed States of Micronesia',
 'Fiji',
 'Finland',
 'France',
 'French Guiana',
 'French Polynesia',
 'French S & Antarctic Lands',
 'Gabon',
 'Gambia, The',
 'Gaza Strip',
 'Georgia',
 'Germany',
 'Ghana',
 'Gibraltar',
 'Greece',
 'Greenland',
 'Grenada',
 'Guadeloupe',
 'Guam',
 'Guatemala',
 'Guernsey',
 'Guinea',
 'Guinea-Bissau',
 'Guyana',
 'Haiti',
 'Halaib Triangle',
 'Heard I & McDonald Is',
 'Honduras',
 'Hong Kong',
 'Hungary',
 'IN-CH Small Disputed Areas',
 'Iceland',
 'India',
 'Indonesia',
 'Invernada Area',
 'Iran',
 'Iraq',
 'Ireland',
 'Isla Brasilera',
 'Isle of Man',
 'Israel',
 'Italy',
 'Jamaica',
 'Jan Mayen',
 'Japan',
 'Jersey',
 'Jordan',
 'Kalapani Area',
 'Kazakhstan',
 'Kenya',
 'Kiribati',
 'Korea, North',
 'Korea, South',
 'Korean Is. (UN Jurisdiction)',
 'Kosovo',
 'Koualou Area',
 'Kuwait',
 'Kyrgyzstan',
 'Laos',
 'Latvia',
 'Lebanon',
 'Lesotho',
 'Liancourt Rocks',
 'Liberia',
 'Libya',
 'Liechtenstein',
 'Lithuania',
 'Luxembourg',
 'Macau',
 'Macedonia',
 'Madagascar',
 'Malawi',
 'Malaysia',
 'Maldives',
 'Mali',
 'Malta',
 'Marshall Is',
 'Martinique',
 'Mauritania',
 'Mauritius',
 'Mayotte',
 'Mexico',
 'Moldova',
 'Monaco',
 'Mongolia',
 'Montenegro',
 'Montserrat',
 'Morocco',
 'Mozambique',
 'Namibia',
 'Nauru',
 'Navassa I',
 'Nepal',
 'Netherlands',
 'Netherlands (Caribbean)',
 'New Caledonia',
 'New Zealand',
 'Nicaragua',
 'Niger',
 'Nigeria',
 'Niue',
 "No Man's Land",
 'Norfolk I',
 'Northern Mariana Is',
 'Norway',
 'Oman',
 'Pakistan',
 'Palau',
 'Panama',
 'Papua New Guinea',
 'Paracel Is',
 'Paraguay',
 'Peru',
 'Philippines',
 'Pitcairn Is',
 'Poland',
 'Portugal',
 'Portugal (Azores)',
 'Portugal (Madeira Is)',
 'Puerto Rico',
 'Qatar',
 'Rep of the Congo',
 'Reunion',
 'Romania',
 'Russia',
 'Rwanda',
 'S Georgia & S Sandwich Is',
 'Saint Lucia',
 'Samoa',
 'San Marino',
 'Sao Tome & Principe',
 'Saudi Arabia',
 'Senegal',
 'Senkakus',
 'Serbia',
 'Seychelles',
 'Siachen-Saltoro Area',
 'Sierra Leone',
 'Sinafir & Tiran Is.',
 'Singapore',
 'Sint Maarten',
 'Slovakia',
 'Slovenia',
 'Solomon Is',
 'Somalia',
 'South Africa',
 'South Sudan',
 'Spain',
 'Spain (Africa)',
 'Spain (Canary Is)',
 'Spratly Is',
 'Sri Lanka',
 'St Barthelemy',
 'St Helena',
 'St Kitts & Nevis',
 'St Martin',
 'St Pierre & Miquelon',
 'St Vincent & the Grenadines',
 'Sudan',
 'Suriname',
 'Swaziland',
 'Sweden',
 'Switzerland',
 'Syria',
 'Taiwan',
 'Tajikistan',
 'Tanzania',
 'Thailand',
 'Timor-Leste',
 'Togo',
 'Tokelau',
 'Tonga',
 'Trinidad & Tobago',
 'Tunisia',
 'Turkey',
 'Turkmenistan',
 'Turks & Caicos Is',
 'Tuvalu',
 'US Minor Pacific Is. Refuges',
 'US Virgin Is',
 'Uganda',
 'Ukraine',
 'United Arab Emirates',
 'United Kingdom',
 'United States',
 'United States (Alaska)',
 'United States (Hawaii)',
 'Uruguay',
 'Uzbekistan',
 'Vanuatu',
 'Vatican City',
 'Venezuela',
 'Vietnam',
 'Wake I',
 'Wallis & Futuna',
 'West Bank',
 'Western Sahara',
 'Yemen',
 'Zambia',
 'Zimbabwe']
default_country_index = COUNTRIES.index('Germany')

WORLD_REGIONS = [
    "Africa",
    "E Asia",
    "Europe",
    "N Asia",
    "S Asia",
    "Oceania",
    "SE Asia",
    "SW Asia",
    "Australia",
    "Caribbean",
    "Antarctica",
    "S Atlantic",
    "Central Asia",
    "Indian Ocean",
    "North America",
    "South America",
    "Central America"
]
default_region_index = WORLD_REGIONS.index("Africa")

from ee_init import ensure_ee_ready
ensure_ee_ready()



def label_gif_with_month(gif_bytes, labels, fps, xy=(10, 10)):
    """Overlay per-frame text labels (e.g., Month) in the top-left corner."""
    im = Image.open(gif_bytes)
    frames = []
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 28)
    except Exception:
        font = ImageFont.load_default()

    for i, frame in enumerate(ImageSequence.Iterator(im)):
        frame_rgba = frame.convert("RGBA")
        overlay = Image.new("RGBA", frame_rgba.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        label = labels[i % len(labels)]
        # background box for legibility
        tw, th = draw.textbbox((0, 0), label, font=font)[2:]
        x, y = xy
        draw.rectangle((x - 6, y - 6, x + tw + 6, y + th + 6), fill=(0, 0, 0, 120))
        draw.text((x, y), label, font=font, fill=(255, 255, 255, 255))

        frames.append(Image.alpha_composite(frame_rgba, overlay).convert("P"))

    out = io.BytesIO()
    duration = max(1, int(1000 / fps))  # ms per frame
    frames[0].save(out, format="GIF", save_all=True, append_images=frames[1:], loop=0,
                   duration=duration, disposal=2)
    out.seek(0)
    return out

def ndvi(aoi_type):
    st.title("Vegetation Index Timelapse")

    ref_year = 2019
    fps = 9
    dimensions = 600
    crs = "EPSG:3857"

    # --- Data + processing ---
    # Collections and region/mask
    col = ee.ImageCollection("MODIS/061/MOD13A2").select("NDVI")

    def add_doy(img):
        doy = ee.Date(img.get("system:time_start")).getRelative("day", "year")
        return img.set("doy", doy)

    col = col.map(add_doy)

    # Use a single year to get the distinct DOYs to match across the full collection
    distinctDOY = col.filterDate(f"{ref_year}-01-01", f"{ref_year+1}-01-01")

    # Join by DOY
    join_filter = ee.Filter.equals(leftField="doy", rightField="doy")
    saved_join = ee.Join.saveAll(matchesKey="doy_matches")
    joinCol = ee.ImageCollection(saved_join.apply(distinctDOY, col, join_filter))

    # Reduce median among matches for each DOY
    def median_by_doy(img):
        doyCol = ee.ImageCollection.fromImages(img.get("doy_matches"))
        # Keep 'doy' for potential debugging/ordering
        return doyCol.reduce(ee.Reducer.median()).copyProperties(img, ["doy"])

    comp = joinCol.map(median_by_doy)

    # Visualization params
    visParams = {
        "min": 0.0,
        "max": 9000.0,
        "palette": [
            "FFFFFF","CE7E45","DF923D","F1B555","FCD163","99B718","74A901",
            "66A000","529400","3E8601","207401","056201","004C00","023B01",
            "012E01","011D01","011301"
        ],
    }
    if aoi_type == "world_region":
        aoi_name = st.selectbox("Select a Continent", WORLD_REGIONS, index=default_region_index)
        mask_fc = (
            ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
            .filter(ee.Filter.eq("wld_rgn", aoi_name))
        )
        zoom_lvl = 3
    elif aoi_type == "country":
        aoi_name = st.selectbox("Select a Country", COUNTRIES, index=default_country_index)
        mask_fc = (
            ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
            .filter(ee.Filter.eq("country_na", aoi_name))
        )
        zoom_lvl = 5

    region = mask_fc.geometry().bounds()

    # Prepare frames and GIF params
    rgbVis = comp.map(lambda img: img.visualize(**visParams).clip(mask_fc))
    gifParams = {
        "region": region,
        "dimensions": dimensions,
        "crs": crs,
        "framesPerSecond": fps,
    }

    # --- Layout: map (left) and animation (right) ---
    left, right = st.columns([1, 1])

    # Build month labels from DOY values in the composited collection
    doys = comp.aggregate_array("doy").getInfo()  # list (0-based day-of-year)
    months = []
    for d in doys:
        dt = datetime(ref_year, 1, 1) + timedelta(days=int(d))
        months.append(dt.strftime("%B"))  # "January", "February", ...

    with left:
        st.subheader("Map")
        coords = mask_fc.geometry().centroid().getInfo()['coordinates']
        m = geemap.Map(center=[coords[1], coords[0]], zoom=zoom_lvl, basemap="SATELLITE")  # Uses Esri.WorldImagery on London
        # Styled boundary
        boundary_style = mask_fc.style(color="black", fillColor="00000000", width=1)
        m.addLayer(boundary_style, {}, f"{aoi_name} boundary")

        # Add the first frame as a static preview layer on the map
        first_frame = ee.Image(comp.first()).visualize(**visParams).clip(mask_fc)
        m.addLayer(first_frame, {}, "NDVI (first DOY frame)")
        m.to_streamlit()

    with right:
        st.subheader("Vegetation Animation")
        # Get a GIF from EE and show it
        try:
            gif_url = rgbVis.getVideoThumbURL(gifParams)

            # Download the GIF, overlay month text, and display
            resp = requests.get(gif_url, timeout=60)
            resp.raise_for_status()
            raw_gif = io.BytesIO(resp.content)
            labeled_gif = label_gif_with_month(raw_gif, months, fps=fps, xy=(10, 10))
            st.image(labeled_gif, caption=f"NDVI median-per-DOY animation ({aoi_name}, MOD13A2)",
                    use_container_width=True)
        except Exception as e:
            st.error(f"Failed to create animation: {e}")
            st.info("Tip: Make sure your Earth Engine account is enabled and you’re logged in.")

        # --- Footer info ---
        with st.expander("What this app does"):
            st.markdown(
                """
        - Loads **MODIS/061/MOD13A2 NDVI** and tags each image with its **day-of-year (DOY)**.
        - Uses a **reference year** (default 2019) to get the set of DOYs.
        - For each DOY, **collects all matching DOYs across the full collection** and reduces them with the **median**.
        - Visualizes the sequence and renders a **GIF animation**.
                """
            )

def app():
    ee_authenticate()

    apps = [
        "NDVI Continent",
        "NDVI Country",
    ]
    selected_app = st.selectbox("Select an app", apps)

    if selected_app == "NDVI Continent":
        ndvi(aoi_type="world_region")
    elif selected_app == "NDVI Country":
        ndvi(aoi_type="country")

app()
