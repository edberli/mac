# 交接：EP01 普通話配音（音軌已完成，2026-11-05）

**現況**：`publish/ep01.audio.zh.m4a` 已生成（201.19 秒，用戶揀定人類 `Chinese (Mandarin)_Gentle_Youth`、AXIS `Chinese (Mandarin)_Gentleman`＋`robot` 效果）。要連 `MINIMAX_BASE=https://api.minimaxi.com`。以下係當時嘅步驟紀錄。

## 目標

為已完成嘅 EP01（英文版，3 分 21 秒）整一條**普通話音軌**，畫面完全唔改。上載去 YouTube 做「多語言音軌」，華語觀眾可以喺播放器揀普通話。

## 已經準備好

| 項目 | 位置 |
|---|---|
| 普通話翻譯（簡體，每句對應英文） | `script/ep01_zh.json` |
| 英文版時間軸（普通話會放入同一時間位置） | `script/timelines/ep01_intro.json`、`script/timelines/ep01_main.json` |
| 一條命令完成配音、對時間、混音、插片頭 | `tools/dub.py` |
| 中文字幕（簡體、繁體） | `publish/ep01.zh-Hans.srt`、`publish/ep01.zh-Hant.srt` |

`tools/dub.py` 已經喺雲端用英文錄音代替試行過：輸出音軌 201.19 秒，同影片 201.20 秒吻合。

## 步驟

1. 準備環境（第一次）：

```bash
cd overview-video && tools/setup.sh
```

2. 設定金鑰（只放喺環境變數）：

```bash
export MINIMAX_API_KEY="你嘅 MiniMax 金鑰"
```

3. 揀聲：先出試聽（每段頭 4 句），畀用戶聽：

```bash
python3 tools/dub.py ep01 zh --human "Chinese (Mandarin)_Straightforward_Boy" --axis "Chinese (Mandarin)_Sincere_Adult" --samples
```

   建議組合（同英文版一樣：年輕男聲＋成熟男聲，AXIS 加 `robot` 效果）：
   - 人類：`Chinese (Mandarin)_Straightforward_Boy`（年輕、坦率）或 `Chinese (Mandarin)_Gentle_Youth`（溫和年輕）
   - AXIS：`Chinese (Mandarin)_Sincere_Adult`（真誠成年男聲）、`Chinese (Mandarin)_Reliable_Executive`（穩重中年）或 `Chinese (Mandarin)_Gentleman`（有磁性）
   - 試聽檔案喺 `build/ep01_intro/dub_zh/audio/`、`build/ep01_main/dub_zh/audio/`

4. 用戶揀好之後，生成全片：

```bash
python3 tools/dub.py ep01 zh --human "<人類聲線>" --axis "<AXIS 聲線>"
```

   - 有句子出現「still … too long」：代表普通話太長、塞唔落英文時間位置。將 `script/ep01_zh.json` 嗰句改短，再執行一次步驟 4（唔好加 `--reuse`）。
   - 輸出：`publish/ep01.audio.zh.m4a`（長度應該約 201.2 秒）

5. 交畀用戶上載：YouTube Studio → 該影片 →「字幕」（或「語言」）→ 加入語言「中文（普通話）」→ 上載音軌 `ep01.audio.zh.m4a`；同時上載 `ep01.zh-Hans.srt`／`ep01.zh-Hant.srt` 字幕。

## 注意

- 英文版畫面已經內嵌英文字幕，中文字幕會出喺附近，可能有少少重疊（用戶已接受）。
- 片頭（Wait What）喺 18.67 秒插入 5 秒，`tools/dub.py` 會自動處理。
- 費用：MiniMax 按字數收費，全片中文大約 1,500 字，好少錢；試聽只用頭幾句。
