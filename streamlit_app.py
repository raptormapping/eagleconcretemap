import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import openrouteservice
import time

# ✅ Setup Streamlit Page
st.set_page_config(page_title="Drive-Time Company Map Viewer", layout="wide")
st.title("📍 Drive-Time Company Map Viewer")

# ✅ Session state initialization
for key in ["competitor_visibility", "project_sites", "all_competitors"]:
    st.session_state.setdefault(key, {} if key != "all_competitors" else set())

# ✅ Sidebar: API Key input
if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""

api_key_input = st.sidebar.text_input(
    "🔑 Enter your OpenRouteService API Key",
    value=st.session_state["api_key"],
    type="password"
)
if api_key_input:
    st.session_state["api_key"] = api_key_input

# Check if API key entered
if st.session_state["api_key"]:
    client = openrouteservice.Client(key=st.session_state["api_key"])
else:
    st.warning("⚠️ Enter your API key to enable drive-time analysis features.")
    st.stop()

# ✅ Sidebar: Drive-time radius slider + manual input
st.sidebar.subheader("🚗 Drive-Time Radius (minutes)")
slider_minutes = st.sidebar.slider("Choose radius (quick)", 1, 60, 10, step=1)
manual_minutes = st.sidebar.number_input("Or enter exact minutes", min_value=1, max_value=300, value=slider_minutes, step=1)
drive_time_minutes = manual_minutes
drive_time_seconds = drive_time_minutes * 60

# ✅ File Upload
uploaded_file = st.file_uploader("📂 Upload Excel (Companies & Projects sheets)", type=["xlsx"])
if not uploaded_file:
    st.info("⬆️ Please upload an Excel file with 'Companies' and 'Projects' sheets.")
    st.stop()

# ✅ Load and validate data
try:
    xls = pd.ExcelFile(uploaded_file, engine="openpyxl")
    companies_df = pd.read_excel(xls, "Companies")
    projects_df = pd.read_excel(xls, "Projects")

    for col in ['Company Location', 'Latitude', 'Longitude', 'Company Name']:
        assert col in companies_df.columns, f"'Companies' sheet must include '{col}' column."
    for col in ['Project Name', 'Latitude', 'Longitude']:
        assert col in projects_df.columns, f"'Projects' sheet must include '{col}' column."

except Exception as e:
    st.error(f"❌ Error loading data: {e}")
    st.stop()

# ✅ Initialize project sites
if not st.session_state.project_sites:
    for _, row in projects_df.iterrows():
        st.session_state.project_sites[row['Project Name']] = {
            "lat": row['Latitude'],
            "lon": row['Longitude'],
            "visible": True
        }

# ✅ Caching Isochrone function (with fix)
@st.cache_data(show_spinner="Calculating drive-time radius...")
def get_isochrone(_client, lon, lat, seconds):
    return _client.isochrones(
        locations=[[lon, lat]],
        profile='driving-car',
        range_type='time',
        intervals=[seconds]
    )

# ✅ Competitor visibility initialization
for _, row in companies_df.iterrows():
    cname = row['Company Location']
    st.session_state.all_competitors.add(cname)
    st.session_state.competitor_visibility.setdefault(cname, True)

# ✅ UI: Manage Project Visibility
st.sidebar.subheader("📍 Projects")
for pname, pdata in st.session_state.project_sites.items():
    pdata["visible"] = st.sidebar.checkbox(f"{pname}", value=pdata["visible"])

# ✅ Map initialization
map_center = [companies_df['Latitude'].mean(), companies_df['Longitude'].mean()]
m = folium.Map(location=map_center, zoom_start=10)

# ✅ Color assignment
unique_companies = companies_df['Company Name'].unique()
colormap = plt.colormaps['tab20']
company_colors = {
    name: mcolors.to_hex(colormap(i % colormap.N))
    for i, name in enumerate(unique_companies)
}

# ✅ Project Site Isochrones
for pname, pdata in st.session_state.project_sites.items():
    if pdata["visible"]:
        iso = get_isochrone(client, pdata["lon"], pdata["lat"], drive_time_seconds)
        folium.GeoJson(
            iso,
            name=f"{pname} ({drive_time_minutes}-min radius)",
            style_function=lambda x: {
                'fillColor': '#ff0000', 'color': '#ff0000', 'weight': 2, 'fillOpacity': 0.3
            }
        ).add_to(m)
        folium.Marker(
            location=[pdata["lat"], pdata["lon"]],
            popup=f"{pname}",
            icon=folium.Icon(color="red", icon="star", prefix="fa")
        ).add_to(m)
        time.sleep(1)

# ✅ Competitor Isochrones and Markers
for _, row in companies_df.iterrows():
    cname = row['Company Location']
    if st.session_state.competitor_visibility[cname]:
        iso = get_isochrone(client, row['Longitude'], row['Latitude'], drive_time_seconds)
        color = company_colors[row['Company Name']]
        folium.GeoJson(
            iso,
            style_function=lambda x, color=color: {
                'fillColor': color, 'color': color, 'weight': 2, 'fillOpacity': 0.2
            }
        ).add_to(m)

        folium.Marker(
            location=[row['Latitude'], row['Longitude']],
            popup=f"{cname}",
            icon=folium.Icon(color="black", icon_color=color, icon='info-sign')
        ).add_to(m)
        time.sleep(1)

# ✅ Display Map and Legend Side-by-Side
col1, col2 = st.columns([5, 1])

with col1:
    st.subheader("🗺️ Interactive Drive-Time Map")
    st_folium(m, width=900, height=600, returned_objects=[])

with col2:
    st.subheader("📘 Company Legend")

    legend_items = ""
    for company, color in company_colors.items():
        legend_items += (
            f"<div style='margin-bottom:6px;'>"
            f"<span style='display:inline-block;width:14px;height:14px;"
            f"background:{color};margin-right:8px;border:1px solid black;'></span>"
            f"{company}</div>"
        )

    legend_html = f"""
    <div style='font-size: 14px; max-height: 500px; overflow-y: auto; padding: 4px;'>
        {legend_items}
    </div>
    """

    st.markdown(legend_html, unsafe_allow_html=True)
