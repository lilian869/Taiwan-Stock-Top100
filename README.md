# Taiwan Stock Top100 — V1.2

台灣上市＋上櫃股票每日成交量 Top 100 個人專業觀察工具。

## V1.2 功能
- 每日收盤後以明確交易日期擷取 TWSE 上市及 TPEx 上櫃全市場行情。
- TWSE 使用指定日期的 MI_INDEX 歷史行情介面；TPEx 使用指定日期的 afterTrading/otc 介面。
- 若當日資料尚未完整發布，依序回查較早交易日；只有上市與上櫃資料均達最低完整筆數才會發布。
- 合併上市、上櫃股票後，依成交股數排序取前 100 名。
- 保存每日全市場行情快照，供後續歷史分析使用。
- 首次執行時，透過 TWSE／TPEx 指定日期行情介面回補至少 120 個交易日；每日執行會檢查歷史資料是否達標。
- 計算 MA5/20/60、RSI14、MACD(12,26,9)、KD(9,3,3)、成交量 MA5/20。
- 合併官方本益比、殖利率及股價淨值比資料（來源有提供時）。
- 以靜態網頁呈現 Top 100，支援個股代號搜尋。

## 資料來源
- TWSE OpenAPI: https://openapi.twse.com.tw/
- TPEx OpenAPI: https://www.tpex.org.tw/openapi/

每日收盤資料不是盤中即時報價。最新快照端點可能因兩個市場的發布時間不同而出現日期落差，因此每日主流程改用指定日期的歷史行情介面，避免直接合併不同日期的最新快照。資料不足或來源異常時會明確失敗，不會以虛構數值補齊。

## 執行
```bash
pip install -r requirements.txt
python -m src.pipeline
```

## 歷史資料與指標限制
每日執行會保存當日行情快照。MA/RSI/MACD/KD 會使用已保存的歷史資料計算；新建專案尚未累積足夠交易日資料時，指標會顯示為 null。首次回補會逐日檢查上市與上櫃行情是否同時完整；來源缺資料、欄位變更或覆蓋率異常時會明確記錄並使工作流程失敗，不會以重複或推算資料填補。

## GitHub Actions
workflow 設定為週一至週五台灣時間 19:30 執行，並可手動觸發。若當日尚未發布完整行情，程式會回查最近一個兩市場資料完整的交易日；若回查範圍內仍無完整資料，workflow 會失敗且不覆寫最新資料。

## 部署
Repository Settings → Pages → Build and deployment → Deploy from a branch → Branch: `main`, Folder: `/docs`。
