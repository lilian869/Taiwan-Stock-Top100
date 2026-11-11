# Taiwan Stock Top100 — V1.1

台灣上市＋上櫃股票每日成交量 Top 100 個人專業觀察工具。

## V1.1 功能
- 每日收盤後擷取 TWSE 上市及 TPEx 上櫃全市場行情。
- 合併上市、上櫃股票後，依成交股數排序取前 100 名。
- 保存每日全市場行情快照，供後續歷史分析使用。
- 計算 MA5/20/60、RSI14、MACD(12,26,9)、KD(9,3,3)、成交量 MA5/20。
- 合併官方本益比、殖利率及股價淨值比資料（來源有提供時）。
- 以靜態網頁呈現 Top 100，支援個股代號搜尋。

## 資料來源
- TWSE OpenAPI: https://openapi.twse.com.tw/
- TPEx OpenAPI: https://www.tpex.org.tw/openapi/

本工具使用收盤行情，不提供盤中即時報價。資料來源欄位可能調整，擷取失敗時會在 workflow 中明確失敗，不會以虛構數值補齊。

## 執行
```bash
pip install -r requirements.txt
python -m src.pipeline
```

## 歷史資料與指標限制
每日執行會保存當日行情快照。MA/RSI/MACD/KD 會使用已保存的歷史資料計算；新建專案尚未累積足夠交易日資料時，指標會顯示為 null。**目前版本尚未完成 120 個交易日的歷史回補**，不能將每日累積誤認為已回補 120 日。

## GitHub Actions
workflow 設定為週一至週五 UTC 08:30（台灣時間 16:30）執行，並可手動觸發。若當日休市或來源無資料，workflow 會記錄失敗／無資料狀態，不會覆寫成假資料。

## 部署
Repository Settings → Pages → Build and deployment → Deploy from a branch → Branch: `main`, Folder: `/docs`。
