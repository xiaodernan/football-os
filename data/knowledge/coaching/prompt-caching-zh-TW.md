---
id: prompt-caching-zh-TW
title: "爲什麼熱前綴勝出：教練產品裏的緩存提示詞經濟學"
category: coaching
locale: zh-TW
tags: [llm, cache, cost, prefix, token, gateway, streaming]
applies_to: [all]
difficulty: advanced
source: "FOOTBALL OS original editorial content — written for this project, no external text reproduced"
confidence: high
last_reviewed: 2026-11-17
---

## "每次提問我們都要爲同一份系統提示詞付費嗎"

一個教練 agent 每次回答用戶提問，都會隨附一段冗長且完全相同的簡報——人設、基本規則、引用契約、以及什麼樣的回答算得上優秀的範例。每次調用都爲這些內容全額買單，會直接主導整張賬單。緩存提示詞（cached prompt）是 provider 用來以極低的輸入成本服務完全相同前綴的機制，而一個 agent 經濟性的全部藝術，就在於把前綴做得足夠穩定、從而能夠被服務，同時把問題本身壓得足夠小、從而足夠便宜。

## 前綴就是契約

可被緩存的，恰恰是那些調用之間永遠不變的部分：system 消息、狀態信封的形狀、引用規則、模型被允許倚重的詞彙。問題本身、球員的數據、以及今天的快照，是後綴——真正會變化的部分。產品的 coaching doors 每一次按下所做的一切——算術已算好、警告已裁定、賬本行已寫好——依其構造產出的前綴字節級完全相同，一次又一次提問之間都如此。一個由新鮮隨機數、重排的 key、時間戳或會話專屬字符串拼出來的前綴，無法被緩存；對緩存友好的設計意味着提示詞是確定性地組裝起來的，可變的部分一律追加在末尾。

## provider 的報告是唯一的記分牌

provider 關於緩存行爲所報告的——`cached_input_tokens`，有時只在 streaming 響應上纔會報告——是唯一誠實的度量。gateway 在冷調用時可能回答"0 cached"，也可能乾脆完全不報告，或者在調用量很低時報告一個毫無意義的百分比。紀律在於：在產品實際走的那條路由上、在重複調用的體量下讀取報告，並且只聲稱被實測到的東西。一個對緩存誠實的產品，報告的是 gateway 打印出來的那個比率，絕不是從提示詞表觀大小反推出來的比率。

## Streaming 不是錦上添花的功能

有些 gateway 只在 streaming 響應上打印緩存用量；有些兩種都不打印。一個被困在用調用次數估算緩存的產品，其數字會與 provider 自己的算術漸行漸遠。合理的工程姿態是：默認用 stream，隨 stream 附帶 usage 標誌，從 stream 的最後一個 event 裏讀取 `cached_input_tokens` 計數，並且保留非 streaming 路徑——它如實是它本來的樣子：一條什麼都不打印的路徑。這個產品的 gateway 正是這麼做的，也正因爲如此，教練的回答信封才能誠實地報告緩存命中，而不是去猜。

## 緩存 key 與失效

只有當 key 標識的是契約而不是問題本身時，cached 前綴纔算是契約。Node 層級的緩存一般按內容哈希做 key；provider 層級的緩存按前綴字節做 key，並在首次調用把緩存寫入服務端之後纔有資格命中。一個以球隊、平臺或功能命名的緩存 key，是 provider 自己做的設計選擇；一個經由同一個 gateway 調用的產品，想要讓自己熱路徑上的前綴命中 provider 的緩存，這意味着它需要前綴具備確定性，並且它還需要自己的緩存（回答緩存）疊加在上面，吸收完全相同問題的重複出現。

## 在本產品中的實測

本產品 gateway 上的 coaching doors 會在經 Clash Verge 的 streaming 調用上報告 `cached_input_tokens`。在 Real Book 的系統前綴的熱重複調用上，gateway 打印出 ~96–97% 的 cached input tokens；在冷調用上則什麼都不打印。產品自己的回答緩存按 key 合併相同的問題，使得兩次完全相同的提問只買到一份措辭，而限流中間件把同一個前綴計入同一個共享預算。本章記錄的是方法；實時數字在賬本（ledger）裏，不在這裏。

## 何時不適用

一次單一的靜態查找——cron 時刻的日曆抓取、一段未經修改的規則條文摘錄——可以安心地對緩存毫無講究；緩存友好型提示詞設計的開銷只是噪聲。一個從設計上每次都重新組合的提示詞（刻意變化的審計行文）不會也不應該命中 provider 的緩存，給它套上前綴邏輯只會增加開銷。而任何不報告緩存用量的 gateway，都會讓這一切無法度量；在那種情況下，正確的答案是去改變 gateway 的報告，而不是去編造比率。

## 證據及其邊界

這是對某一個產品的工作假設的工程描述——確定性前綴、僅 stream 上報用量、雙層調用結構（下層是 provider 的 prefix cache，上層是回答緩存）。它不是對這個 provider 與另一個 provider 的基準對比，"~96–97%" 這個數字是在本主機上、這條 gateway 上觀測到的熱重複數據，不是穩定 token 的營銷承諾。provider 談判、提示詞順序、調用量都會改變這套算術，因此可持續的部分是方法論——stream、讀取 usage、如實彙總；數字本身只是一個快照。
