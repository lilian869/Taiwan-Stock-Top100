# Windows 免費本機排程試行指南

## 目的與邊界

- 使用現有 Windows 電腦，在台灣平日 09:00–13:30 執行 Fugle Top100 盤中報價擷取。
- 每 5 分鐘啟動一輪；100 檔依序呼叫，請求間隔 1.1 秒。
- 不使用付費雲端排程、不修改正式網站、不自動推送 GitHub。
- 成功的完整 100 檔快照寫入 `runtime/fugle_intraday_latest.json`。
- 任何一輪失敗時保留上一份完整快照，不以不完整資料覆蓋。
- 執行紀錄寫入 `runtime/logs/`。

## 前提

1. Windows 10/11 電腦。
2. Python 3.10 或更新版本，且命令列可執行 `python`。
3. 交易時段電腦保持開機、連網，使用者保持登入，並停用睡眠。
4. Fugle API Key 已取得且方案允許使用該 API。
5. 此方式不是 24 小時雲端服務；電腦關機、睡眠、登出或斷網時不會更新。

## 一次性設定

在 Windows PowerShell 執行（請把 YOUR_KEY 換成自己的金鑰；不要貼到聊天或提交到 GitHub）：

```powershell
[Environment]::SetEnvironmentVariable("FUGLE_API_KEY", "YOUR_KEY", "User")
```

關閉 PowerShell 再重新開啟。到專案根目錄安裝依賴：

```powershell
python -m pip install requests
```

先做單次測試：

```powershell
$env:FUGLE_API_KEY = [Environment]::GetEnvironmentVariable("FUGLE_API_KEY", "User")
python tools/fugle_intraday_snapshot.py --output runtime\manual_test.json --delay 1.1
```

確認 SUMMARY 顯示 requested=100、success=100、failed=0。測試會呼叫真實 API；請勿短時間重複執行。

## 安裝每日排程

在專案根目錄，以一般（非系統管理員）PowerShell 執行：

```powershell
.\tools\install_fugle_intraday_task.ps1
```

排程器會在週一至週五 08:55 啟動本機輪詢程式。程式只在 09:00–13:30 執行，每輪依 5 分鐘時鐘刻度安排，不會重疊執行。

## 驗收

1. Windows 工作排程器中找到 `TaiwanStockTop100-FugleIntraday`，確認工作已註冊。
2. 交易時段確認 `runtime\logs\runner-YYYYMMDD.log` 持續新增 SUCCESS 記錄。
3. 確認 `runtime\fugle_intraday_latest.json` 的 `requested=100`、`success=100`、`failed=0`。
4. 至少連續觀察 6 輪；另需比較不同輪次的 `asOfTaipei` 與價格／成交量變化。
5. 電腦睡眠、登出、關機或斷網期間不保證更新。Windows 電源設定需自行調整為交易時段不睡眠。

## 停止或移除

停止目前執行中的 PowerShell 視窗可按 Ctrl+C。移除排程：

```powershell
Unregister-ScheduledTask -TaskName "TaiwanStockTop100-FugleIntraday" -Confirm:$false
```

## 注意事項

- Fugle 免費方案的配額與 API 使用條款可能變更，部署前請再次核對官方方案頁。
- API 讀取權限不代表可公開再散布行情；正式網站整合前必須確認資料展示授權。
- 本試行只產生本機 JSON，尚未整合網站，也不會自動發布資料。
