# Google-Maps-API-Ollama-Tutorial

# 簡介
本專案教學如何使用 Python 串接 Google Routes API 與 Street View Static API，並自動將取得的資訊餵給本地端的 Ollama (LLM) 進行分析。

# 準備工作
1. Google Cloud Platform API Key (需開啟 Routes 與 Street View 權限)
2. 連線至rccn私有伺服器:
    本專案使用老師架設的 Ollama 伺服器，請確保你的電腦已連線至校內/實驗室區域網路。
    API Endpoint: http://10.16.80.24:11434/api/generate
    指定模型: llama3.2-vision:11b
3. Python 環境

# 大致流程說明
1. Routes API - 輸入起訖點，取得路徑座標
2. Street View Static API - 根據座標抓取對應的街景圖
3. Prompt Automation - 組合 API 回傳的資料，發送給 Ollama 進行敘事或分析

# 範例資料
1. 起訖點檔案：pond_selected_start_end.csv
2. 輸出的路線檔案：all_routes.geojson
3. 輸出的街景照片資料夾：streetview_images
4. 取景點位檔案：streetview_points.csv / streetview_points.geojson
