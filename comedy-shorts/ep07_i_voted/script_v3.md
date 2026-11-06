# I Voted（ep07）第三版對白（v3，即 v4 出片用）

日期：2026-11-06　范圍：只換對白及演法，畫面素材沿用現成畫面，唔出新圖。

| 鏡頭 | 角色 | 對白 | 演法 |
|---|---|---|---|
| marcus_door + 彩紙 | M | DEMOCRACY, BABY! | 爆發，同之前一樣（重用現有 wav） |
| russell（russell_s1） | R | You voted? | 平淡 |
| marcus_bag，配樂開始 | M | We lost Dave in that line. | 突然冇晒能量，眼神呆滯望前面，好低沉 |
| russell | R | Dave had work. | |
| marcus_bag | M | He looked at his watch. He said, "I'll come back later." | 慢，沉重 |
| marcus_bag | | （靜 1 秒） | 慢慢推近 |
| marcus_bag | M | Nobody comes back later. | |
| russell | R | I saw him at lunch. | |
| marcus_bag | M | You weren't there, Russell. | |
| russell | R | I was right behind you. | |
| marcus_bag | M | You were there. But you weren't THERE. | |
| neil | | （靜 0.6 秒，eyes_closed） | |
| marcus_bag | M | Eleven minutes. A woman named Carol handed me a pen. | 慢 |
| marcus_bag | | （靜 0.8 秒） | |
| marcus_bag | M | It was out of ink. | 幾乎講唔出 |
| russell | R | What's in the bag? | |
| marcus_bag | M | Dave's lunch. He said, "Hold this." | |
| russell | R | So where is it? | |
| marcus_sticker | | （靜 0.5 秒） | 望住自己心口 |
| sticker_close | | （靜 1.0 秒） | 配樂推高 |
| neil | N | I voted too. Five minutes. It was fine. | 平淡 |
| marcus_bag | M | They always say it was fine. | 望住 Russell 方向，好細聲 |
| end_tag | | | 1.5 秒，只接一次 |

## 配音與參數

- 聲：MiniMax `speech-2.8-hd`，`tools/tts.py`，語速只用 API speed（冇 atempo）。
- M 老兵句（"We lost Dave" 起至 "They always say it was fine."）：`emotion: sad`，speed 0.9；"It was out of ink." speed 0.85。DEMOCRACY 句 speed 1.3 沿用現有 wav。
- R、N：speed 1.05，emotion neutral。
- 配樂：程式合成嘅輕悲傷長音，由 "We lost Dave" 開始到正片完結淡出；sticker_close 嗰下推高少少。
