---
id: prompt-caching-zh
title: "为什么热前缀胜出：教练产品里的缓存提示词经济学"
category: coaching
locale: zh
tags: [llm, cache, cost, prefix, token, gateway, streaming]
applies_to: [all]
difficulty: advanced
source: "FOOTBALL OS original editorial content — written for this project, no external text reproduced"
confidence: high
last_reviewed: 2026-11-17
---

## "每次提问我们都要为同一份系统提示词付费吗"

一个教练 agent 每次回答用户提问，都会随附一段冗长且完全相同的简报——人设、基本规则、引用契约、以及什么样的回答算得上优秀的范例。每次调用都为这些内容全额买单，会直接主导整张账单。缓存提示词（cached prompt）是 provider 用来以极低的输入成本服务完全相同前缀的机制，而一个 agent 经济性的全部艺术，就在于把前缀做得足够稳定、从而能够被服务，同时把问题本身压得足够小、从而足够便宜。

## 前缀就是契约

可被缓存的，恰恰是那些调用之间永远不变的部分：system 消息、状态信封的形状、引用规则、模型被允许倚重的词汇。问题本身、球员的数据、以及今天的快照，是后缀——真正会变化的部分。产品的 coaching doors 每一次按下所做的一切——算术已算好、警告已裁定、账本行已写好——依其构造产出的前缀字节级完全相同，一次又一次提问之间都如此。一个由新鲜随机数、重排的 key、时间戳或会话专属字符串拼出来的前缀，无法被缓存；对缓存友好的设计意味着提示词是确定性地组装起来的，可变的部分一律追加在末尾。

## provider 的报告是唯一的记分牌

provider 关于缓存行为所报告的——`cached_input_tokens`，有时只在 streaming 响应上才会报告——是唯一诚实的度量。gateway 在冷调用时可能回答"0 cached"，也可能干脆完全不报告，或者在调用量很低时报告一个毫无意义的百分比。纪律在于：在产品实际走的那条路由上、在重复调用的体量下读取报告，并且只声称被实测到的东西。一个对缓存诚实的产品，报告的是 gateway 打印出来的那个比率，绝不是从提示词表观大小反推出来的比率。

## Streaming 不是锦上添花的功能

有些 gateway 只在 streaming 响应上打印缓存用量；有些两种都不打印。一个被困在用调用次数估算缓存的产品，其数字会与 provider 自己的算术渐行渐远。合理的工程姿态是：默认用 stream，随 stream 附带 usage 标志，从 stream 的最后一个 event 里读取 `cached_input_tokens` 计数，并且保留非 streaming 路径——它如实是它本来的样子：一条什么都不打印的路径。这个产品的 gateway 正是这么做的，也正因为如此，教练的回答信封才能诚实地报告缓存命中，而不是去猜。

## 缓存 key 与失效

只有当 key 标识的是契约而不是问题本身时，cached 前缀才算是契约。Node 层级的缓存一般按内容哈希做 key；provider 层级的缓存按前缀字节做 key，并在首次调用把缓存写入服务端之后才有资格命中。一个以球队、平台或功能命名的缓存 key，是 provider 自己做的设计选择；一个经由同一个 gateway 调用的产品，想要让自己热路径上的前缀命中 provider 的缓存，这意味着它需要前缀具备确定性，并且它还需要自己的缓存（回答缓存）叠加在上面，吸收完全相同问题的重复出现。

## 在本产品中的实测

本产品 gateway 上的 coaching doors 会在经 Clash Verge 的 streaming 调用上报告 `cached_input_tokens`。在 Real Book 的系统前缀的热重复调用上，gateway 打印出 ~96–97% 的 cached input tokens；在冷调用上则什么都不打印。产品自己的回答缓存按 key 合并相同的问题，使得两次完全相同的提问只买到一份措辞，而限流中间件把同一个前缀计入同一个共享预算。本章记录的是方法；实时数字在账本（ledger）里，不在这里。

## 何时不适用

一次单一的静态查找——cron 时刻的日历抓取、一段未经修改的规则条文摘录——可以安心地对缓存毫无讲究；缓存友好型提示词设计的开销只是噪声。一个从设计上每次都重新组合的提示词（刻意变化的审计行文）不会也不应该命中 provider 的缓存，给它套上前缀逻辑只会增加开销。而任何不报告缓存用量的 gateway，都会让这一切无法度量；在那种情况下，正确的答案是去改变 gateway 的报告，而不是去编造比率。

## 证据及其边界

这是对某一个产品的工作假设的工程描述——确定性前缀、仅 stream 上报用量、双层调用结构（下层是 provider 的 prefix cache，上层是回答缓存）。它不是对这个 provider 与另一个 provider 的基准对比，"~96–97%" 这个数字是在本主机上、这条 gateway 上观测到的热重复数据，不是稳定 token 的营销承诺。provider 谈判、提示词顺序、调用量都会改变这套算术，因此可持续的部分是方法论——stream、读取 usage、如实汇总；数字本身只是一个快照。
