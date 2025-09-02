"""
Nighttime Lights Blackout App
---------------------------------
Uses VIIRS monthly night-lights (avg_rad) from NOAA to find out if there was a structural break in the nighttime lights data.

- You pick a place (default: Mykolaiv, Ukraine) or search for one; a radius slider builds an AOI as a buffered point.
- For 2018 to → 2025, it computes a time series of mean radiance over the AOI, plots it, and offers a CSV download.
- It runs a structural break test + if a break exists, it picks representative “pre” and “post” months and shows summary metrics (pre mean, post mean, delta/%).
- The map (Esri imagery + label overlay) shows a split view: pre month on the left vs. post month on the right, with a colorbar for night-lights intensity.
- If no break is found, it picks a “usual” month (between the 40th–60th percentile of radiance) and shows that single layer instead.
"""

import datetime as dt
from typing import Tuple

import numpy as np
import ee
import folium
import geemap.foliumap as geemap
import pandas as pd
import streamlit as st

st.set_page_config(page_title='Nighttime Lights Blackout App', layout='wide')

@st.cache_data
def ee_authenticate(token_name="EARTHENGINE_TOKEN"):
    geemap.ee_initialize(token_name=token_name)


# ---------------------------------
# Data helpers
# ---------------------------------

VIIRS_IDS = [
    # Prefer stray-light corrected, gap-filled product
    'NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG',
    # Fallback (not strictly needed, but helpful if catalog id changes)
    'NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG',
]


def get_viirs_collection() -> ee.ImageCollection:
    """Return the first available VIIRS monthly collection from known IDs."""
    last_err = None
    for ds in VIIRS_IDS:
        try:
            col = ee.ImageCollection(ds).select('avg_rad')
            return col
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Could not load VIIRS collection. Last error: {last_err}")


def month_to_filter(col: ee.ImageCollection, d: dt.date) -> ee.Image:
    start = ee.Date.fromYMD(d.year, d.month, 1)
    end = start.advance(1, 'month')
    img = col.filterDate(start, end).mosaic().set('system:time_start', start)
    return img

# ---------------------------------
# Water mask (JRC GSW occurrence > 30%)
# ---------------------------------
def jrc_non_water_mask(threshold: int = 30, dataset_id: str = 'JRC/GSW1_4/GlobalSurfaceWater') -> ee.Image:
    """Return a mask image where land = 1 and permanent water = masked (occurrence > threshold)."""
    gsw = ee.Image(dataset_id).select('occurrence') # 0–100
    water = gsw.gt(threshold)
    nonwater = water.Not()
    return nonwater


# ---------------------------------
# Analytics
# ---------------------------------
def find_trend_break(
    df, 
    date_col="date", 
    value_col="mean_rad",
    min_segment=6,            # ≥6 months on each side
    bic_threshold=-10,        # call it a break if ΔBIC <= -10
    pre_window=6,             # search last 6 pre-break months (skip immediate month before break)
    post_window=12,           # search months 2..12 after break
    min_gap_post=1,           # skip the very first post month for imagery
    verbose=True
):
    x = df[[date_col, value_col]].dropna().copy()
    x[date_col] = pd.to_datetime(x[date_col])
    x = x.sort_values(date_col).reset_index(drop=True)

    y = x[value_col].astype(float).to_numpy()
    n = len(y)
    if n < 2*min_segment + 1:
        raise ValueError(f"Need at least {2*min_segment+1} rows, got {n}.")
    t = np.arange(n, dtype=float)

    # Single linear trend
    X1 = np.column_stack([np.ones(n), t])
    b1, *_ = np.linalg.lstsq(X1, y, rcond=None)
    sse1 = np.sum((y - X1 @ b1)**2)
    bic1 = n*np.log(sse1/n) + X1.shape[1]*np.log(n)

    # Best piecewise linear split
    best_bic, best_k = np.inf, None
    for k in range(min_segment, n - min_segment):
        I = (np.arange(n) >= k).astype(float)
        dt = (t - t[k]) * I
        Xk = np.column_stack([np.ones(n), t, I, dt])  # level & slope can change after k
        bk, *_ = np.linalg.lstsq(Xk, y, rcond=None)
        ssek = np.sum((y - Xk @ bk)**2)
        bick = n*np.log(ssek/n) + Xk.shape[1]*np.log(n)
        if bick < best_bic:
            best_bic, best_k = bick, k

    delta_bic = best_bic - bic1
    has_break = delta_bic <= bic_threshold
    if not has_break:
        if verbose:
            st.subheader('No break in long-term night lights detected.')
            # st.write("No break in long-term night light data detected.")
        return {
            "has_break": False, "delta_bic": float(delta_bic),
            "break_date": None, "pre_image_date": None, "post_image_date": None
        }

    # Summaries
    k = best_k
    pre = y[:k]; post = y[k:]
    pre_mean, post_mean = float(pre.mean()), float(post.mean())

    # Pick representative months
    pre_lo = max(0, k - pre_window - 1)
    pre_hi = max(pre_lo, k - 1)             # exclude k-1
    pre_candidates = np.arange(pre_lo, pre_hi) if pre_hi > pre_lo else np.arange(0, k)
    pre_idx = int(pre_candidates[np.argmin(np.abs(y[pre_candidates] - pre_mean))])

    post_start = min(k + max(1, min_gap_post), n-1)
    post_end   = min(k + post_window, n-1)
    post_candidates = np.arange(post_start, post_end+1) if post_end >= post_start else np.arange(k, n)
    post_idx = int(post_candidates[np.argmin(np.abs(y[post_candidates] - post_mean))])

    break_date = pd.to_datetime(x.loc[k, date_col])
    pre_img = pd.to_datetime(x.loc[pre_idx, date_col])
    post_img = pd.to_datetime(x.loc[post_idx, date_col])

    if verbose:
        # st.write("Structural break in long-term night light data detected.")
        st.subheader('Structural break in long-term night lights detected.')
        st.write(f"- Break at: {break_date.date()}  (first month of new regime)")
        # st.write(f"- ΔBIC: {delta_bic:.2f}  (<= {bic_threshold} ⇒ accept)")
        # pct = (post_mean - pre_mean)/pre_mean if pre_mean else np.nan
        # st.write(f"- Pre mean: {pre_mean:.4f} | Post mean: {post_mean:.4f}  (Δ={pct*100:.1f}% if finite)")
        st.write(f"- Pre image:  {pre_img.date()} - Post image: {post_img.date()}")

    return {
        "has_break": True,
        "delta_bic": float(delta_bic),
        "break_date": break_date,
        "pre_image_date": pre_img,
        "post_image_date": post_img,
        "pre_mean": pre_mean,
        "post_mean": post_mean
    }


def compute_change(pre_img: ee.Image, post_img: ee.Image) -> Tuple[ee.Image, ee.Image]:
    """Return (absolute change, percent change) images."""
    pre = pre_img.select('avg_rad')
    post = post_img.select('avg_rad')
    d = post.subtract(pre).rename('d_rad')
    # Avoid division by ~0: cap pre at small epsilon before % change
    eps = ee.Image.constant(1.0)
    pct = d.divide(pre.max(eps)).multiply(100).rename('pct_change')
    return d, pct


def blackout_mask(post_img: ee.Image, pct_img: ee.Image, pct_thresh=-70, abs_thresh=0.5) -> ee.Image:
    """Mask of likely blackouts: big negative % change + low absolute radiance."""
    cond = pct_img.lte(pct_thresh).And(post_img.select('avg_rad').lte(abs_thresh))
    return cond.selfMask().rename('blackout')


def region_ts(col: ee.ImageCollection, aoi: ee.Geometry, scale=500) -> pd.DataFrame:
    """Return a pandas DataFrame with date and mean radiance over AOI."""
    def feat(img):
        mean = img.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=aoi, scale=scale, maxPixels=1e13
        ).get('avg_rad')
        return ee.Feature(None, {
            'date': ee.Date(img.get('system:time_start')).format('YYYY-MM'),
            'mean': mean
        })

    fc = col.map(feat).filter(ee.Filter.notNull(['mean']))
    lst = fc.aggregate_array('date').getInfo()
    vals = fc.aggregate_array('mean').getInfo()
    df = pd.DataFrame({'date': pd.to_datetime(lst), 'mean_rad': vals})
    df = df.sort_values('date').reset_index(drop=True)
    return df


# UI + App
def nightlights():
    st.set_page_config(page_title='Nighttime Lights Blackout App', layout='wide')
    st.title('Nighttime Lights — Economic Activity & Blackout Detector')
    st.caption('VIIRS DNB Monthly (NOAA) • Earth Engine • geemap • Streamlit')

    viirs = get_viirs_collection()

    # starting location
    lat = 46.952137
    lng = 32.019653
    location = "Mykolaiv, Ukraine"

    # pct_thresh = -70
    # abs_thresh = 1
    scale = 500
    mask_water = True
    year_min = 2018
    year_max = 2025
    month_min = 1
    month_max = 8

    keyword = st.text_input("Search for a location:", "")
    if keyword:
        locations = geemap.geocode(keyword)
        if locations is not None and len(locations) > 0:
            str_locations = [str(g)[1:-1] for g in locations]
            location = st.selectbox("Select a location:", str_locations)
            loc_index = str_locations.index(location)
            selected_loc = locations[loc_index]
            lat, lng = selected_loc.lat, selected_loc.lng

    radius_km = st.slider("Radius in km", 10.0, 100.0, 20.0, step=1.0)
    # -------------------- Helpers --------------------
    def make_aoi(lon, lat, radius_km):
        return ee.Geometry.Point([lon, lat]).buffer(radius_km * 1000).bounds()

    # -------------------- Build imagery --------------------
    aoi = make_aoi(lng, lat, radius_km)

    # Time series chart
    st.subheader('AOI Time Series')
    ts_col = viirs.filterBounds(aoi).filterDate(ee.Date.fromYMD(year_min, month_min, 1), ee.Date.fromYMD(year_max, month_max, 1).advance(1,'month'))
    df = region_ts(ts_col, aoi, scale=scale)

    if not df.empty:
        st.line_chart(df.set_index('date')['mean_rad'])
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button('Download CSV', csv, file_name='viirs_timeseries.csv', mime='text/csv')
    else:
        st.info('No time series data returned for this AOI/time window.')

    trend = find_trend_break(df)

    if trend["has_break"]:
        st.subheader('Summary')
        pre_mean = trend["pre_mean"]
        post_mean = trend["post_mean"]
        change = float(post_mean - pre_mean)
        pct = 100.0 * change / max(pre_mean, 0.2)
        c1, c2, c3 = st.columns(3)
        c1.metric('Pre mean (avg_rad)', f"{pre_mean:.2f}")
        c2.metric('Post mean (avg_rad)', f"{post_mean:.2f}")
        c3.metric('Δ & %', f"{change:.2f}", f"{pct:+.1f}%")

    # Optional permanent water mask
    if mask_water:
        land_mask = jrc_non_water_mask()

    # Map and layers
    m = geemap.Map(center=[lat, lng], zoom=9, basemap="SATELLITE")  # Uses Esri.WorldImagery
    if keyword:
        folium.Marker(location=[lat, lng], popup=location).add_to(m)
        m.set_center(lng, lat, 9)
    m.add_basemap("CartoDB.PositronOnlyLabels")  # labels-only overlay

    vis_viirs = {'min': 0, 'max': 40, 'palette': ['#000000', '#0a0a4f', '#225ea8', '#1d91c0', '#41b6c4', '#7fcdbb', '#c7e9b4', '#ffffb2', '#fed976', '#fd8d3c', '#e31a1c']}
    if trend["has_break"]:
        pre_year = trend["pre_image_date"].year
        pre_month = trend["pre_image_date"].month
        post_year = trend["post_image_date"].year
        post_month = trend["post_image_date"].month
        pre_date = dt.datetime.strptime(f"{pre_year}-{pre_month}", "%Y-%m")
        post_date = dt.datetime.strptime(f"{post_year}-{post_month}", "%Y-%m")

        # Prepare images
        pre_img = month_to_filter(viirs, pre_date).clip(aoi)
        post_img = month_to_filter(viirs, post_date).clip(aoi)

        # d_img, pct_img = compute_change(pre_img, post_img)

        # # Mask out small percent changes (<40% in absolute value)
        # pct_img = pct_img.where(pct_img.abs().lt(40), ee.Image(0))#.updateMask(pct_img.abs().gte(40))
        # if mask_water:
        #     pct_img = pct_img.where(land_mask.eq(0), ee.Image(0))
        # mask_img = blackout_mask(post_img, pct_img, pct_thresh=pct_thresh, abs_thresh=abs_thresh)
        # vis_change_pct = {'min': -100, 'max': 100, 'palette': ['#67001f', '#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#f7f7f7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac', '#053061']}

        pre_label = f"Pre Night Lights {pre_date.strftime('%Y-%m')}"
        post_label = f"Post Night Lights {post_date.strftime('%Y-%m')}"

        pre_lyr = geemap.ee_tile_layer(pre_img, vis_viirs, pre_label)
        post_lyr = geemap.ee_tile_layer(post_img, vis_viirs, post_label)

        # Split view pre vs post
        m.split_map(left_layer=pre_lyr, right_layer=post_lyr)

        # Optional permanent water mask
        # if mask_water:
        #     water_overlay = land_mask.Not().selfMask()
        #     m.addLayer(water_overlay, {'palette': ['#0000ff']}, 'JRC Permanent Water (>30%)', False)
        # m.addLayer(pct_img, vis_change_pct, 'Percent Change (post − pre)', True)
        # m.addLayer(mask_img, {'palette': ['#ff0000']}, 'Blackout Hotspots', False)
        # m.add_colorbar(vis_change_pct, label='% change (post−pre)')
    else:
        # No trend break: Take last "usual" night lights layer between p40 and p60
        p40 = df["mean_rad"].quantile(0.40)
        p60 = df["mean_rad"].quantile(0.60)
        usual_date = df[(df["mean_rad"] > p40) & (df["mean_rad"] < p60)]["date"].iloc[-1]
        usual_img = month_to_filter(viirs, usual_date).clip(aoi)
        # Simple visualization of a usual night lights layer
        m.addLayer(usual_img, vis_viirs, f'Usual Night Lights {usual_date.strftime("%Y-%m")}', True, opacity=0.7)

    # m.addLayer(aoi, {'color': 'yellow'}, 'AOI', False)
    m.add_colorbar(
        vis_params=vis_viirs,
        label="Night Lights Intensity (avg_rad, nW/cm²/sr)",
        orientation="horizontal",  # or "vertical"
        background_color="white",        # <-- sets the bounding box background
        font_size=14,           # optional, makes labels more visible
    )

    m.to_streamlit()

def app():
    ee_authenticate()

    nightlights()

app()
