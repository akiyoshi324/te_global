import folium
import matplotlib.cm as cm
import numpy as np
import streamlit as st
import xarray as xr
from streamlit_folium import st_folium

st.set_page_config(page_title="River Depth Return Period 2025", layout="wide")
st.title("River Depth Return Period in 2025")

DATA_PATH = "data/rp_2025_time.nc"


@st.cache_data
def load_data(path):
    ds = xr.open_dataset(path)
    rp = ds["rp"].values
    max_time = ds["time"].values
    return rp, max_time


@st.cache_data
def make_overlay_rgba(rp, vmin, vmax, hide_below_vmin=True):
    """緯度 -60〜75度を切り出してRGBA画像（uint8）を生成"""
    nrows = rp.shape[0]
    # 北緯90度→南緯90度で格納されている前提で -60〜75度を切り出す
    row_top = int((90.0 - 75.0) / 180.0 * nrows)
    row_bot = int((90.0 - (-60.0)) / 180.0 * nrows)
    sub = rp[row_top:row_bot, :]

    norm = np.clip((sub - vmin) / (vmax - vmin), 0.0, 1.0)
    rgba = (cm.Reds(np.nan_to_num(norm, nan=0.0)) * 255).astype(np.uint8)

    # 欠損値（および任意で vmin 未満）を完全透過にする
    mask = ~np.isfinite(sub)
    if hide_below_vmin:
        mask |= sub < vmin
    rgba[mask, 3] = 0
    return rgba


rp, max_time = load_data(DATA_PATH)
nrows, ncols = rp.shape

# サイドバー設定
with st.sidebar:
    st.header("SETTINGS")
    vmin, vmax = st.slider("再現期間 表示範囲 (年)", 1, 100, (5, 20))
    st.caption("地図上をクリックすると、その地点のRPと最大値発生時刻が表示されます。")

# Folium地図の作成
m = folium.Map(location=[0.0, 0.0], zoom_start=2, tiles="OpenStreetMap")

rgba = make_overlay_rgba(rp, vmin, vmax, hide_below_vmin=True)
folium.raster_layers.ImageOverlay(
    image=rgba,
    bounds=[[-60.0, -180.0], [75.0, 180.0]],
    mercator_project=True,  # PlateCarreeデータをWebメルカトルに正しく投影
    name="Return Period",
).add_to(m)

# ピン用のレイヤーを作成（前回のクリック位置があればピンを立てる）
fg = folium.FeatureGroup(name="Selected Point")
if "clicked_pos" in st.session_state:
    c_lat, c_lon = st.session_state["clicked_pos"]
    folium.Marker(
        location=[c_lat, c_lon],
        icon=folium.Icon(color="blue", icon="info-sign"),
    ).add_to(fg)

# feature_group_to_add=fg を追加（地図のズーム位置を維持したままピンだけ更新）
map_data = st_folium(
    m,
    width=None,
    height=620,
    feature_group_to_add=fg,
    returned_objects=["last_clicked"],
)

if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]

    # クリック位置が変わったら保存して再描画（ピンを即時反映）
    if st.session_state.get("clicked_pos") != (lat, lon):
        st.session_state["clicked_pos"] = (lat, lon)
        st.rerun()

    lon = ((lon + 180.0) % 360.0) - 180.0

    col = int((lon + 180.0) / 360.0 * ncols)
    row = int((90.0 - lat) / 180.0 * nrows)

    if 0 <= row < nrows and 0 <= col < ncols:
        rp_val = rp[row, col]
        t_val = max_time[row, col]
        rp_str = f"{rp_val:.2f} year" if np.isfinite(rp_val) else "NaN"
        t_str = (
            np.datetime_as_string(t_val, unit="m").replace("T", " ") + " UTC"
            if not np.isnat(t_val)
            else "NaT"
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Location", f"lat {lat:.3f}, lon {lon:.3f}")
        c2.metric("Return Period", rp_str)
        c3.metric("Time", t_str)
else:
    st.info("地図上の任意の場所をクリックすると、RPと発生時刻が表示されます。")
