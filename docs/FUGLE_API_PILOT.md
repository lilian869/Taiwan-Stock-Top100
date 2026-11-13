# Fugle 盤中行情 API 第一階段測試

## 目標與範圍

- 只測試 Fugle REST API 的個股盤中報價端點。
- 股票清單取自目前 `docs/data/latest.json` 的收盤 Top 100。
- 預設先測 5 檔；確認 API Key 與欄位正常後，再測全部 100 檔。
- 本階段唯讀，不寫入行情資料、不修改 `docs/index.html`、不部署 GitHub Pages，也不觸碰正式 `main` 分支。

## API 規格

- Base URL: `https://api.fugle.tw/marketdata/v1.0/stock`
- Endpoint: `GET /intraday/quote/{symbol}`
- Authentication: HTTP header `X-API-KEY`
- 使用欄位：
  - `symbol`, `name`, `market`
  - `lastPrice`（若缺少則 fallback 到 `closePrice`）
  - `change`, `changePercent`
  - `total.tradeVolume`
  - `lastUpdated`

官方文件：
- https://developer.fugle.tw/docs/data/http-api/getting-started/
- https://developer.fugle.tw/docs/data/http-api/intraday/quote/
- https://developer.fugle.tw/docs/pricing/

## 免費基本用戶限制

官方方案頁目前列出：
- 日內行情 API：60 次／分鐘
- WebSocket：5 個訂閱數、1 條連線
- 行情快照 API：基本用戶不支援

因此本測試逐檔呼叫，預設每次間隔 1.1 秒；100 檔約需 110 秒。不可用多帳號或其他方式規避限制。

## 取得 API Key 與安全設定

1. 登入 Fugle Developer：https://developer.fugle.tw/
2. 申請行情 API Key。
3. 不要把 API Key 寫進程式碼、提交到 GitHub 或貼在聊天訊息。
4. 在 GitHub Repo → Settings → Secrets and variables → Actions → New repository secret 建立：
   - Name: `FUGLE_API_KEY`
   - Secret: 你的 Fugle API Key

## 執行測試

1. 開啟 GitHub Actions。
2. 選擇 `Fugle Intraday API Pilot Test`。
3. 選擇分支 `feature/fugle-intraday-api-pilot`。
4. 第一次將 `test_all_100` 保持 false，先測 5 檔。
5. 5 檔成功後，再執行一次並將 `test_all_100` 設為 true。

也可在本機執行：

```bash
# macOS/Linux
export FUGLE_API_KEY="你的金鑰"
python tools/fugle_smoke_test.py --limit 5

# Windows PowerShell
$env:FUGLE_API_KEY="你的金鑰"
python tools/fugle_smoke_test.py --limit 5

# 測試完整 100 檔
python tools/fugle_smoke_test.py --all --delay 1.1
```

## 驗收標準

| 項目 | 驗收條件 |
|---|---|
| API Key | 認證成功，無 401／403 |
| 報價欄位 | 取得代碼、名稱、價格、累計成交量 |
| 5 檔測試 | 5/5 成功 |
| 100 檔測試 | 100/100 成功，或逐一記錄可解釋的例外 |
| 速率限制 | 不觸發 429；請求間隔至少 1 秒 |
| 資料新鮮度 | 比對 `lastUpdated` 與台灣時間 |
| 正式網站 | 不修改、不部署 |

## 重要資料限制

Fugle 文件說明，盤中累計成交量只計盤中整股交易，不含盤中零股、盤後定價、盤後零股及鉅額交易。因此盤中追蹤數字可能與收盤後官方全日成交量有差異。

API 取得權限不等於可無限制公開轉播行情。正式對外展示前，須先確認 Fugle 及交易所／櫃買中心對公開網站展示與資料再散布的授權要求。
