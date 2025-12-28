#!/usr/bin/env python
# coding: utf-8

# In[1]:


get_ipython().system('pip install requests')


# In[2]:


get_ipython().system('pip install polyline')


# In[3]:


#routes_api_讀取csv計算多重路徑_並存成geojson
import requests
import json
import pandas as pd
import polyline
import os

# === 1. 基本設定 ===
API_KEY = "YOUR_API_KEY" # 輸入你的API KEY
CSV_PATH = "pond_selected_start_end.csv"  # 輸入你的CSV檔名
OUTPUT_GEOJSON = "all_routes.geojson" # 輸入你想輸出的geojson檔名
TRAVEL_MODE = "TWO_WHEELER"  # 可改成：DRIVE / WALK / BICYCLE / TWO_WHEELER

# === 2. 讀取 CSV ===
df = pd.read_csv(CSV_PATH)

# === 3. 初始化 ===
url = "https://routes.googleapis.com/directions/v2:computeRoutes"
headers = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": API_KEY,
    "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline"
}

all_features = []

# === 4. 逐行處理 ===
for i, row in df.iterrows():
    try:
        origin = {"latitude": row["start_lat"], "longitude": row["start_lng"]} # 起點欄位名稱
        destination = {"latitude": row["end_lat"], "longitude": row["end_lng"]} # 終點欄位名稱

        body = {
            "origin": {"location": {"latLng": origin}},
            "destination": {"location": {"latLng": destination}},
            "travelMode": TRAVEL_MODE,
            "routingPreference": "TRAFFIC_AWARE", #是否考慮即時交通狀況（TRAFFIC_AWARE 或 TRAFFIC_UNAWARE）
            "computeAlternativeRoutes": False,
            "routeModifiers": {
                "avoidTolls": False,
                "avoidHighways": False,
                "avoidFerries": False
            },
            "languageCode": "zh-TW",
            "units": "METRIC"
        }

        response = requests.post(url, headers=headers, json=body)
        data = response.json()

        if "routes" not in data:
            print(f"無法計算：{row['start']} → {row['end']}")
            continue

        route = data["routes"][0]
        distance = route["distanceMeters"] / 1000
        duration = float(route["duration"].replace("s", "")) / 60  # 轉分鐘
        points = route["polyline"]["encodedPolyline"]
        coords = polyline.decode(points)

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[lon, lat] for lat, lon in coords]
            },
            "properties": {
                "start": row["start"],
                "end": row["end"],
                "route_name": row.get("route_name", f"route_{i+1}"),
                "mode": TRAVEL_MODE,
                "distance_km": round(distance, 2),
                "duration_min": round(duration, 1)
            }
        }
        all_features.append(feature)

        print(f"{row['start']} → {row['end']} | {distance:.2f} km, 約 {duration:.1f} 分鐘")

    except Exception as e:
        print(f"第 {i+1} 筆錯誤：{e}")

# === 5. 輸出整合 GeoJSON ===
geojson_data = {"type": "FeatureCollection", "features": all_features}

with open(OUTPUT_GEOJSON, "w", encoding="utf-8") as f:
    json.dump(geojson_data, f, ensure_ascii=False, indent=2)

print(f"\n已完成！共輸出 {len(all_features)} 條路線至：{OUTPUT_GEOJSON}")


# In[4]:


pip install shapely geopy requests pillow


# In[5]:


#streetview_static_api_讀取geojson_並輸出每個取景點的csv, geojson
import json
import math
import os
import csv
import requests
from shapely.geometry import LineString
from geopy.distance import geodesic
from PIL import Image
from io import BytesIO

API_KEY = "YOUR_API_KEY" # 輸入你的API KEY
GEOJSON_PATH = "all_routes.geojson" # 輸入你的geojson檔名
OUTPUT_DIR = "streetview_images" # 輸入你要存放街景的資料夾名稱
CSV_PATH = "streetview_points.csv" # 輸入你想輸出的csv檔名
GEOJSON_OUT = "streetview_points.geojson" # 輸入你想輸出的geojson檔名

INTERVAL_M = 50 #這裡設定每50公尺一張街景圖
FOV = 90 # Field of View 視野/焦距
PITCH = 0 # 垂直角度（仰角/俯角）

os.makedirs(OUTPUT_DIR, exist_ok=True)

# === 計算方位角 heading ===
def bearing(p1, p2):
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dlon)
    brng = math.degrees(math.atan2(y, x))
    return (brng + 360) % 360 # 餵給 Street View API 的 heading 參數

# === 計算取樣點 ===
def sample_points(line, interval_m=50):
    shapely_line = LineString([(lon, lat) for lat, lon in line])
    pts = []
    d = 0
    while d < shapely_line.length:
        pt = shapely_line.interpolate(d)
        pts.append((pt.y, pt.x))  # lat, lon
        d += interval_m / 111320
    return pts

# === 找最近有街景的點（自動搜尋半徑） ===
def find_nearest_streetview(lat, lon):
    radii = [0, 10, 20, 30, 50, 80]  # m
    for r in radii:
        url = (
            "https://maps.googleapis.com/maps/api/streetview/metadata"
            f"?location={lat},{lon}&key={API_KEY}"
        )
        res = requests.get(url).json()
        if res.get("status") == "OK":
            sv_lat = res["location"]["lat"]
            sv_lon = res["location"]["lng"]
            dist = geodesic((lat, lon), (sv_lat, sv_lon)).meters
            if dist <= r + 0.1:
                return (sv_lat, sv_lon, dist)
        # 否則換下一個搜尋半徑
    return (None, None, None)

# === 抓街景圖 ===
def fetch_streetview(lat, lon, heading, filename):
    url = (
        "https://maps.googleapis.com/maps/api/streetview"
        f"?size=640x640&location={lat},{lon}&heading={heading}&pitch={PITCH}&fov={FOV}&key={API_KEY}"
    )
    r = requests.get(url)
    if r.status_code == 200:
        img = Image.open(BytesIO(r.content))
        img.save(filename)
        return True
    return False


# === 主要流程：讀路線 → 生成影像＋紀錄 metadata ===
records = []

with open(GEOJSON_PATH, encoding="utf-8") as f:
    data = json.load(f)

for i, feat in enumerate(data["features"]):
    coords = feat["geometry"]["coordinates"]
    route_name = feat["properties"].get("route_name", f"route{i+1}")

    if isinstance(coords[0][0], list):
        coords = [pt for seg in coords for pt in seg]

    line = [(c[1], c[0]) for c in coords]

    samples = sample_points(line, INTERVAL_M)
    print(f"📍 {route_name} 取樣 {len(samples)} 點")

    for j in range(len(samples)-1):
        lat0, lon0 = samples[j]
        next_pt = samples[j+1]

        head = bearing((lat0, lon0), next_pt)

        # 找最近可用街景
        sv_lat, sv_lon, offset = find_nearest_streetview(lat0, lon0)

        if sv_lat is None:
            print(f"❌ 無街景：{lat0}, {lon0}")
            continue

        # 儲存圖片
        fname = os.path.join(OUTPUT_DIR, f"{route_name}_{j+1:03d}.jpg")
        success = fetch_streetview(sv_lat, sv_lon, head, fname)

        if success:
            print(f"✅ {fname}")
        else:
            print(f"⚠️ 街景下載失敗：{sv_lat},{sv_lon}")

        records.append({
            "route_name": route_name,
            "index": j+1,
            "original_lat": lat0,
            "original_lon": lon0,
            "sv_lat": sv_lat,
            "sv_lon": sv_lon,
            "heading": head,
            "pitch": PITCH,
            "fov": FOV,
            "distance_offset_m": offset,
            "image_path": fname
        })

# === 輸出 CSV ===
with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=list(records[0].keys())
    )
    writer.writeheader()
    writer.writerows(records)

print(f"已輸出 CSV：{CSV_PATH}")

# === 輸出 GeoJSON ===
geojson = {
    "type": "FeatureCollection",
    "features": []
}

for rec in records:
    geojson["features"].append({
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [rec["sv_lon"], rec["sv_lat"]]
        },
        "properties": rec
    })

with open(GEOJSON_OUT, "w", encoding="utf-8") as f:
    json.dump(geojson, f, ensure_ascii=False, indent=2)

print(f"已輸出 GeoJSON：{GEOJSON_OUT}")


# In[6]:


# Llama分析所有照片
import os
import json
import base64
import requests
import csv

HOST = "http://10.16.80.24:11434/api/generate" #輸入IP
MODEL = "llama3.2-vision:11b"

IMAGE_FOLDER = "streetview_images" # 輸入存放街景的資料夾名稱
INPUT_GEOJSON = "streetview_points.geojson" # 輸入geojson檔名
OUTPUT_GEOJSON = "streetview_points_with_desc.geojson" # 輸入加入描述後你想要的geojson檔名
OUTPUT_CSV = "streetview_points_with_desc.csv" # 輸入加入描述後你想要的csv檔名


# === 1. 單張圖片 → Llama Vision ===
def query_image(image_path, prompt):
    with open(image_path, "rb") as f:
        img_bytes = f.read()

    img_b64 = base64.b64encode(img_bytes).decode("utf-8")

    data = {
        "model": MODEL,
        "prompt": prompt,
        "images": [img_b64],
        "stream": False
    }

    r = requests.post(HOST, json=data)
    r.raise_for_status()
    return r.json()["response"]


# === 2. 載入原始 GeoJSON（街景點位）# === 
with open(INPUT_GEOJSON, "r", encoding="utf-8") as f:
    base_geo = json.load(f)

# 轉成 dict 方便查找
geo_lookup = {}
for feat in base_geo["features"]:
    img_path = feat["properties"]["image_path"].replace("/", "\\")
    geo_lookup[os.path.basename(img_path)] = feat


# === 3. 準備 CSV（若不存在就建立） === 
csv_exists = os.path.exists(OUTPUT_CSV)

csv_file = open(OUTPUT_CSV, "a", newline="", encoding="utf-8")
csv_writer = csv.writer(csv_file)

if not csv_exists:
    csv_writer.writerow([
        "route_name", "index", "image_path", "lat", "lon", "llama_desc"
    ])


# === 4. 如果已經有輸出的 GeoJSON → 載入，不覆蓋 === 
if os.path.exists(OUTPUT_GEOJSON):
    with open(OUTPUT_GEOJSON, "r", encoding="utf-8") as f:
        out_geo = json.load(f)
else:
    out_geo = {"type": "FeatureCollection", "features": []}


# === 5. 自動搜尋所有街景照片並處理 === 
all_images = sorted([
    f for f in os.listdir(IMAGE_FOLDER)
    if f.lower().endswith((".jpg", ".png", ".jpeg"))
])

print(f"共偵測到 {len(all_images)} 張街景照片，開始分析...\n")


for img in all_images:
    img_path = os.path.join(IMAGE_FOLDER, img)
    print(f"解析：{img} ...")

    # 如果原始 geojson 裡沒有這個點，就跳過
    if img not in geo_lookup:
        print(f"⚠ 原始 GeoJSON 找不到 {img}，跳過")
        continue

    # Llama 分析
    desc = query_image(
        img_path,
        prompt="Please describe this street scene in three sentences: key objects, spatial features, atmosphere." #在這裡輸入你的prompt
    )

    # 將描述寫入對應的 feature
    feature = geo_lookup[img]
    lat = feature["geometry"]["coordinates"][1]
    lon = feature["geometry"]["coordinates"][0]

    # ---- 寫入 CSV ----
    csv_writer.writerow([
        feature["properties"]["route_name"],
        feature["properties"]["index"],
        feature["properties"]["image_path"],
        lat,
        lon,
        desc
    ])

    # ---- 寫入 GeoJSON ----
    new_feature = {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": {
            **feature["properties"],
            "llama_desc": desc
        }
    }

    out_geo["features"].append(new_feature)


# === 6. 儲存 GeoJSON === 
with open(OUTPUT_GEOJSON, "w", encoding="utf-8") as f:
    json.dump(out_geo, f, ensure_ascii=False, indent=2)

csv_file.close()

print("\n====== 全部街景分析完成 ======")
print(f"✓ 已更新 CSV：{OUTPUT_CSV}")
print(f"✓ 已更新 GeoJSON：{OUTPUT_GEOJSON}")





