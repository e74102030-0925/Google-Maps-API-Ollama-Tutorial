# Google-Maps-API-Ollama-Tutorial

# 專案簡介
本專案教學如何使用 Python 串接 Google Routes API 與 Street View Static API，並自動將取得的資訊餵給本地端的 Ollama (LLM) 進行分析。

# 準備工作 (Prerequisites)
1. Google Cloud Platform API Key (需開啟 Routes 與 Street View 權限)
2. 連線至rccn私有伺服器:
    本專案使用老師架設的 Ollama 伺服器，請確保你的電腦已連線至校內/實驗室區域網路。
    API Endpoint: http://10.16.80.24:11434/api/generate
    指定模型: llama3.2-vision:11b (此模型支援圖片分析，用於街景描述)。
3. Python 環境

# 核心流程說明
Step 1: Routes API - 輸入起終點，取得路徑座標
Step 2: Street View Static API - 根據座標抓取對應的街景圖
Step 3: Prompt Automation - 組合 API 回傳的資料，發送給 Ollama 進行敘事或分析
