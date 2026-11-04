# 《The View That Changes You》程式動畫製作流程

用程式生成嘅英文科普動畫影片（YouTube 橫片）。畫風：**電影感剪影**；角色：人類（側面剪影）＋人工智能機械人 **AXIS**。

> 片名「The View That Changes You」係暫定名稱。

## 資料夾結構

| 位置 | 內容 |
|---|---|
| `script/` | 劇本檔（JSON 格式）：對白、停頓、場景標記、音效位置 |
| `render/` | 每段影片嘅畫面程式（網頁格式，用瀏覽器逐格繪製） |
| `render/lib/kit2d.js` | 共用 2D 素材：人物、AXIS、地標（自由神像、金字塔、長城、巴黎）、特效、字幕 |
| `render/lib/earth.js` | 立體真實地球（three.js 立體繪圖庫）：日間影像、雲層、夜間燈光、海面反光、大氣層、太陽 |
| `tools/` | 製作工具：配音、時間軸、渲染、混音、一鍵建置 |
| `assets/textures/` | 地球同星空相片素材（出處見 `assets/textures/CREDITS.md`） |
| `assets/brand/` | 頻道素材：Wait What 片頭（5 秒） |
| `prototypes/` | 早期造型同畫風測試（機械人造型表、三種畫風試片） |
| `build/` | 輸出（唔會存入資料庫，可以隨時重新產生） |

## 第一次使用

```bash
tools/setup.sh
```

會安裝：離線語音合成（Piper）、三把英文臨時配音聲線、three.js。另外需要系統已有 `ffmpeg`、`python3`、`node` 同 Playwright（無頭瀏覽器）。

## 製作一段影片

```bash
tools/build.sh ep01_intro
```

流程：
1. `tools/tts.py`：按劇本生成每句臨時配音（機械人聲加電子效果）
2. `tools/timeline.py`：按配音長度計出每句對白同每個場景嘅時間，同埋講嘢時嘅音量變化（用嚟郁角色）
3. `tools/render.js`：用無頭瀏覽器逐格渲染畫面（每秒 30 格，1920×1080）
4. `tools/mix.py`：混合配音、背景低音、轉場重音、升空風聲（全部係臨時合成音效）
5. `ffmpeg`：合成動畫部分 MP4
6. `tools/assemble.py`：喺指定場景位置插入預先做好嘅片段（例如頻道片頭），輸出 `build/<段落>/<段落>_final.mp4`

只改畫面、唔改對白時，可以跳過配音：

```bash
tools/build.sh ep01_intro --no-tts
```

## 改劇本

編輯 `script/ep01_intro.json`：
- `{"say": "H", "text": "..."}`：人類講嘢；`"A"` 係 AXIS
- `{"pause": 0.3}`：停頓（秒）
- `{"mark": "名稱"}`：場景切換點，畫面程式會用呢個名稱決定幾時轉場
- `"inserts"`：插入片段，例如 `{"file": "assets/brand/wait-what-intro-5s.mp4", "at": "paris", "gain_db": 11}` 即係喺 `paris` 場景之前插入頻道片頭，並提高 11 分貝音量

## 重要提示

- **配音係臨時嘅**，正式版要換真人配音：將錄音檔放入 `build/<段落>/audio/lNN.wav`（同一編號），再用 `--no-tts` 重新建置。
- **影片說明欄要註明素材出處**（見 `assets/textures/CREDITS.md`）。
- 背景音同音效都係臨時合成嘅，正式版要換免版稅音樂。
