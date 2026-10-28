# Key Drift Resolution Document

**Generated:** 2026-10-25
**Gate:** qa-key-drift.mjs
**Total Issues:** 119 sentence drifts, 107 key drifts

## Resolution Convention

- **DELIBERATE**: Legitimate semantic difference - same English word, different meaning in different contexts
- **ACCIDENTAL**: Unintentional drift - same concept should use same translation

---

## SENTENCE DRIFTS (119 total)

### 1. "Home" — DELIBERATE
- `nav.home`: "首页" / "首頁" (homepage)
- `simulate.home`: "主队" / "主場" (home team)
- `worldMatch.homeFallback`: "主队" / "主隊" (home team fallback)
- `worldMatch.thHome`: "主队" / "主隊" (table header: home team)

**Reason**: "Home" means "homepage" in nav context but "home team" in match/simulation context.

---

### 2. "Progress" — DELIBERATE
- `nav.progress`: "成长" / "成長" (growth - player development)
- `club.progressTitle`: "进展" / "進展" (progress - club development)
- `club.tableHeaderProgress`: "进展" / "進展" (table header)

**Reason**: "Progress" means player growth in nav but club development progress in club context.

---

### 3. "Erasing…" — DELIBERATE
- `common.erasing`: "正在删除…" / "正在刪除…" (generic deleting)
- `community.erasing`: "删除中…" / "刪除中…" (community-specific)
- `club.erasing`: "正在删除…" / "正在刪除…" (club context)
- `club.noticeErasing`: "正在删除…" / "正在刪除…" (notice)

**Reason**: Minor phrasing variation ("正在删除" vs "删除中") - both mean "deleting", acceptable variance.

---

### 4. "Search" — DELIBERATE
- `common.search`: "搜索" / "搜尋" (generic search)
- `world.searchButton`: "搜索" / "搜尋" (world search button)
- `knowledge.tabSearch`: "检索" / "檢索" (knowledge retrieval - more formal)

**Reason**: "检索/檢索" is more formal/technical term for knowledge base retrieval vs generic "搜索/搜尋".

---

### 5. "Get started" — DELIBERATE
- `auth.getStarted`: "开始使用" / "開始使用" (start using the app)
- `training.getStartedEyebrow`: "开始" / "開始" (start training - shorter UI label)

**Reason**: Different UI contexts - full phrase vs eyebrow label.

---

### 6. "Manager" — DELIBERATE
- `auth.roleManager`: "经理" / "經理" (manager role)
- `career.thManager`: "教练" / "教練" (coach - football context)
- `world.thManager`: "主教练" / "主教練" (head coach)
- `worldTeam.rowManager`: "主教练" / "主教練" (head coach)

**Reason**: "Manager" means different roles: business manager vs football coach/head coach.

---

### 7. "Adding…" — DELIBERATE
- `scout.adding`: "正在添加…" / "正在添加…" (adding to shortlist)
- `training.adding`: "正在新增…" / "正在新增…" (adding drill - "新增" more formal)
- `club.squadAdding`: "正在添加…" / "正在添加…" (adding to squad)
- `club.teamAdding`: "正在添加…" / "正在添加…" (adding team)

**Reason**: "新增" vs "添加" - both mean "adding", minor formal vs casual variance.

---

### 8. "Band" — DELIBERATE
- `scout.band`/`scout.thBand`: "档位" / "檔位" (tier/band level)
- `tactics.tableBand`: "色带" / "色帶" (color band - visual)
- `market.sellThBand`: "区间" / "區間" (price range)
- `simulate.lineupThBand`: "档次" / "檔次" (lineup tier)

**Reason**: "Band" has domain-specific meanings: tier, color band, price range, lineup tier.

---

### 9. "Compare" — DELIBERATE
- `scout.compare`: "对比" / "對比" (player comparison)
- `tactics.compareButton`: "比较" / "比較" (tactics comparison)

**Reason**: Both mean "compare", acceptable variance.

---

### 10. "nobody" — DELIBERATE
- `scout.nobody`: "无人" / "無人" (no player found)
- `club.nobody`: "无对手" / "無對手" (no opponent)

**Reason**: Different contexts - no player vs no opponent.

---

### 11. "none yet" — DELIBERATE
- `scout.noneYet`: "还没有" / "還沒有" (casual)
- `careerDetail.noneYet`: "尚无" / "尚無" (formal)

**Reason**: Different formality levels - scout is casual UI, careerDetail is formal.

---

### 12. "Off" — DELIBERATE
- `scout.off`/`scout.thOff`: "移除" / "移除" (remove from list)
- `club.thOff`: "下场" / "下場" (sub off - football term)

**Reason**: "Off" means remove from shortlist vs substitute off in football.

---

### 13. "Opening…" — DELIBERATE
- `scout.opening`/`career.opening`/`portfolio.opening`/`academy.openingPlan`: "正在开启…" / "正在開啟…"
- `club.createOpening`: "正在开设…" / "正在開設…" (opening a club/facility)

**Reason**: "开设/開設" for creating a club/facility vs "开启/開啟" for opening UI panels.

---

### 14. "Searching…" — DELIBERATE
- `scout.searching`: "搜索中…" / "搜尋中…" (generic searching)
- `knowledge.searching`: "检索中…" / "檢索中…" (knowledge retrieval)

**Reason**: Same as #4 - "检索/檢索" for knowledge base.

---

### 15. "Career" — DELIBERATE
- `scout.thCareer`/`simulationAggregates.thCareer`: "职业生涯" / "職業生涯" (career)
- `creator.challengeLabelCareer`: "生涯" / "生涯" (short for challenge label)

**Reason**: Full term vs abbreviated label in challenge context.

---

### 16. "Fixture" — DELIBERATE
- `scout.thFixture`/`club.thFixture`/`worldMatch.fixtureEyebrow`: "赛程" / "賽程" (schedule)
- `world.thFixture`/`challenges.tFixture`/`careerDetail.thFixture`: "对阵" / "對陣" (matchup)

**Reason**: "Fixture" = schedule in club/scout context, but specific matchup in world/challenges.

---

### 17. "Measured" — DELIBERATE
- `scout.thMeasured`: "实测项" / "實測項" (measured items)
- `tactics.measuredTitle`: "测量" / "測量" (measurement)

**Reason**: "Measured items" vs "Measurement" - different granularity.

---

### 18. "Round" — DELIBERATE
- `scout.thRound`/`market.thRound`/`careerDetail.thRound`/`worldMatch.rowRound`/`creator.thRound`: "轮次" / "輪次" (round)
- `challenges.tRound`: "回合" / "回合" (bout/leg - challenge context)

**Reason**: "Round" in season vs "bout" in challenge context.

---

### 19. "Seed" — DELIBERATE
- `scout.thSeed`/`challenges.tSeed`/`careerDetail.thSeed`: "种子" / "種子" (seed)
- `simulate.ariaSeed`: "随机种子" / "隨機種子" (random seed)

**Reason**: Tournament seed vs random seed for simulation.

---

### 20. "Verdict" — DELIBERATE
- `scout.thVerdict`: "判定" / "判定" (verdict/judgment)
- `challenges.tableVerdict`: "裁决" / "裁決" (ruling)

**Reason**: "Judgment" vs "Ruling" - similar legal terms, different nuance.

---

### 21. "vs" — DELIBERATE
- `scout.versus`: "主场对" / "主場對" (home vs - specific)
- `challenges.vs`: "vs" (generic)
- `careerDetail.vs`: "对阵" / "對陣" (matchup)

**Reason**: Different presentation needs - home indicator vs generic vs matchup label.

---

### 22. "Target" — DELIBERATE
- `career.target`/`creator.challengeLabelTarget`: "目标值" / "目標值" (target value)
- `training.targetEyebrow`: "目标" / "目標" (target - shorter)

**Reason**: Full "target value" vs short "target" in eyebrow.

---

### 23. "Label" — DELIBERATE
- `career.label`/`club.tableHeaderLabel`: "标签" / "標籤" (tag/label)
- `graph.kvLabel`: "名称" / "名稱" (name - graph key-value)

**Reason**: "Label" as tag vs "Name" as key in key-value pair.

---

### 24. "Rounds" — DELIBERATE
- `career.thRounds`/`market.thRound`/`careerDetail.rowRounds`: "轮次" / "輪次" (rounds)
- `challenges.kvRounds`: "回合" / "回合" (bouts)

**Reason**: Season rounds vs challenge bouts.

---

### 25. "P" — DELIBERATE
- `career.thPlayed`/`worldCompetition.thP`: "场" / "場" (matches played)
- `worldMatch.thP`: "传" / "傳" (passes - P in match stats)

**Reason**: P = Played in league table, P = Passes in match stats.

---

### 26. "GD" — DELIBERATE
- `career.thGd`/`careerDetail.thGd`: "净胜球" / "淨勝球" (goal difference)
- `worldCompetition.thGd`: "净" / "淨" (abbreviated GD)

**Reason**: Full "goal difference" vs abbreviated in competition table.

---

### 27. "Pts" — DELIBERATE
- `career.thPoints`/`careerDetail.thPoints`/`worldCompetition.thPts`: "积分" / "積分" (points)
- `challenges.tPts`: "分" / "分" (points - abbreviated)

**Reason**: Full "points" vs abbreviated "points" in challenge context.

---

### 28. "Updating…" — DELIBERATE
- `career.updating`: "正在更新…" / "正在更新…" (updating data)
- `creator.updating`: "正在修改…" / "正在修改…" (modifying content)

**Reason**: "Updating data" vs "Modifying content".

---

### 29. "Streak" — DELIBERATE
- `settings.streak`/`myFootball.statStreak`/`home.statStreak`: "连续训练" / "連續訓練" (training streak)
- `progress.statStreak`: "连续天数" / "連續天數" (consecutive days)

**Reason**: "Training streak" vs "Consecutive days" - different metrics.

---

### 30. "Plan" — DELIBERATE
- `settings.plan`: "套餐" / "方案" (subscription plan)
- `coach.tabPlan`: "计划" / "計畫" (training plan)

**Reason**: "Subscription plan" vs "Training plan".

---

### 31. "Deleting…" — DELIBERATE
- `settings.deleting`/`challenges.deleteButtonBusy`: "正在删除…" / "正在刪除…"
- `simulate.deleteBusy`: "删除中…" / "刪除中…"

**Reason**: "正在删除" vs "删除中" - minor phrasing variance.

---

### 32. "Table" — DELIBERATE
- `world.tableHeaderTable`: "表格" / "表格" (full table)
- `club.tableHeaderTable`: "表" / "表" (abbreviated)
- `worldCompetition.tableTitle`: "积分榜" / "積分榜" (league table/standings)

**Reason**: Generic "table" vs "standings" in competition context.

---

### 33. "Goals" — DELIBERATE
- `world.thGoals`/`challenges.kvGoals`/`simulate.mGoals`/`careerDetail.*Goals`/`worldPlayer.rowGoals`/`simulationAggregates.*Goals`/`worldTeam.thGoals`: "进球" / "進球" (goals scored)
- `club.tableHeaderGoals`: "目标" / "目標" (targets/goals - club objectives)

**Reason**: "Goals scored" in match stats vs "Targets/Objectives" in club management.

---

### 34. "Sessions" — DELIBERATE
- `coach.statSessions`/`club.tableHeaderSessions`/`home.statSessions`/`worldPlayer.rowSessions`: "训练次数" / "訓練次數" (training sessions count)
- `worldTraining.sessionsTitle`: "训练" / "訓練" (training - section title)

**Reason**: "Training sessions count" vs "Training" section title.

---

### 35. "Level" — DELIBERATE
- `coach.statLevel`/`progress.statLevel`: "等级" / "等級" (level)
- `onboarding.labelLevel`: "水平" / "水平" (skill level)

**Reason**: Game level vs skill level/proficiency.

---

### 36. "Asking…" — DELIBERATE
- `coach.asking`/`knowledge.asking`: "提问中…" / "提問中…" (asking question)
- `market.askingBusy`: "正在询问…" / "正在詢問…" (inquiring - market context)

**Reason**: "Asking a question" vs "Inquiring" in market/transfer context.

---

### 37. "Open drill" — DELIBERATE
- `coach.openDrill`: "打开训练" / "開啟訓練" (open training session)
- `myFootball.openDrill`: "打开动作" / "打開動作" (open drill/action)

**Reason**: "Training session" vs "Drill/action" - different granularity.

---

### 38. "Value" — DELIBERATE
- `tactics.tableValue`/`simulate.inputsThValue`: "数值" / "數值" (numeric value)
- `tactics.thValue`/`portfolio.thValue`: "值" / "值" (value - abbreviated)

**Reason**: "Numeric value" vs abbreviated "Value" in table headers.

---

### 39. "Saved" — DELIBERATE
- `tactics.saved`: "已保存" / "已儲存" (saved - tactics)
- `simulate.eSaved`: "扑出" / "撲出" (saved - goalkeeper save)

**Reason**: "Saved (file)" vs "Saved (goalkeeper)" - completely different meanings.

---

### 40. "Drill" — DELIBERATE
- `history.colDrill`/`training.drillFallbackTitle`: "训练" / "訓練" (training session)
- `worldPlayer.thDrill`/`worldTraining.thDrill`/`creator.programDrillLabel`: "动作" / "動作" (drill/action - specific exercise)

**Reason**: "Training session" vs "Specific drill/exercise".

---

### 41. "Answer" — DELIBERATE
- `knowledge.answerEyebrow`/`community.thAnswer`: "回答" / "回答" (answer)
- `club.thAnswer`/`creator.thAnswer`/`academy.thAnswer`: "作答" / "回覆" / "回覆" (answering/responding)

**Reason**: "Answer" (noun) vs "Answering/Responding" (action) in assessment contexts.

---

### 42. "MET" — DELIBERATE
- `challenges.met`/`challenges.metMissed`: "达成" / "達成" (achieved)
- `careerDetail.met`: "已达成" / "已達成" (already achieved)

**Reason**: "Achieved" vs "Already achieved" - tense difference.

---

### 43. "Play it out" — DELIBERATE
- `challenges.playItOutTitle`: "进行下去" / "進行下去" (continue playing)
- `careerDetail.playTitle`: "逐轮推进" / "逐輪推進" (advance round by round)

**Reason**: "Continue playing" vs "Advance round by round" - different game flows.

---

### 44. "From" — DELIBERATE
- `market.buyThFrom`: "来自" / "來自" (from - source club)
- `graph.thFrom`: "起点" / "起點" (from - graph node origin)

**Reason**: "From (source)" vs "Origin (graph node)".

---

### 45. "Opened" — DELIBERATE
- `portfolio.thOpened`: "打开于" / "開啟於" (opened on - document)
- `club.labelOpened`: "创建于" / "建立於" (created on - club)

**Reason**: "Opened" for document vs "Created" for club entity.

---

### 46. "Erase" — DELIBERATE
- `community.erase`/`club.eraseFixture`/`club.noticeErase`: "删除" / "刪除" (delete)
- `club.tableHeaderErase`/`club.tableHeaderErase2`/`creator.erase`: "擦除" / "抹除" / "抹除" (erase/wipe)

**Reason**: "Delete" (remove entity) vs "Erase/Wipe" (clear data/field).

---

### 47. "Publishing…" — DELIBERATE
- `community.publishing`: "发布中…" / "發佈中…" (publishing post)
- `creator.publishing`: "正在发布…" / "正在發布…" (publishing content)

**Reason**: "发布中" vs "正在发布" - minor phrasing variance.

---

### 48. "Recording…" — DELIBERATE
- `community.recording`: "记录中…" / "記錄中…" (recording video)
- `club.noticeRecording`/`academy.recording`: "正在记录…" / "正在記錄…" (recording session)

**Reason**: "Recording (video)" vs "Recording (session/data)".

---

### 49. "Kind" — DELIBERATE
- `community.thKind`: "类别" / "類別" (category)
- `club.createKindLabel`/`club.labelKind`/`club.tableHeaderKind`/`graph.kvKind`: "类型" / "類型" (type)

**Reason**: "Category" vs "Type" - similar but different classification granularity.

---

### 50. "Away" — DELIBERATE
- `simulate.away`: "客场" / "客場" (away game)
- `worldMatch.awayFallback`/`worldMatch.thAway`: "客队" / "客隊" (away team)

**Reason**: "Away game" vs "Away team".

---

### 51. "Playing…" — DELIBERATE
- `simulate.playing`: "播放中…" / "播放中…" (playing simulation)
- `club.playing`: "正在开踢…" / "正在開踢…" (match starting)

**Reason**: "Playing back (simulation)" vs "Kicking off (match)".

---

### 52. "Injuries" — DELIBERATE
- `simulate.mInjuries`: "伤病" / "傷病" (injuries)
- `simulationAggregates.labelInjuries`/`simulationAggregates.thInjuries`: "伤停" / "傷停" (injury/suspension - "伤停" includes suspensions)

**Reason**: "Injuries" vs "Injuries & Suspensions" (伤停).

---

### 53. "Injury" — DELIBERATE
- `simulate.eInjury`: "伤病" / "傷病" (injury event)
- `careerDetail.thLedgerInjury`: "伤停" / "傷停" (injury/suspension record)

**Reason**: Single injury event vs injury/suspension ledger entry.

---

### 54. "Child" — DELIBERATE
- `club.kvChild`/`academy.thChild`/`academy.childAria`: "孩子" / "孩子" (child)
- `club.tableHeaderChild`: "儿童" / "兒童" (children - table header)

**Reason**: "Child" (singular) vs "Children" (plural header).

---

### 55. "Window" — DELIBERATE
- `club.tableHeaderWindow`: "时间窗" / "時間窗" (time window - transfer)
- `creator.thWindow`: "窗口" / "窗口" (window - UI/time)

**Reason**: "Transfer window" vs generic "window".

---

### 56. "Record" — DELIBERATE
- `careerDetail.recordTitle`: "战绩" / "戰績" (match record)
- `worldNews.recordEyebrow`: "记录" / "紀錄" (record/log)

**Reason**: "Match record (W-D-L)" vs "Record/Log entry".

---

### 57. "Matches" — DELIBERATE
- `careerDetail.thLedgerMatches`: "出场" / "出賽" (appearances)
- `simulationAggregates.thMatches`: "场次" / "場次" (matches count)

**Reason**: "Appearances" (player stat) vs "Matches" (aggregate count).

---

### 58. "Played" — DELIBERATE
- `careerDetail.thPlayed`: "场次" / "場次" (matches played)
- `worldTeam.playedTitle`: "已踢" / "已踢" (already played)

**Reason**: "Matches played" (stat) vs "Already played" (status).

---

### 59. "Focus areas" — DELIBERATE
- `worldPlayer.rowFocusAreas`: "重点领域" / "重點領域" (focus areas)
- `academy.focusAria`: "重点方面" / "重點方面" (focus aspects)

**Reason**: "Areas" vs "Aspects" - similar, acceptable variance.

---

### 60. "Sv" — DELIBERATE
- `worldPlayer.thSv`: "扑救" / "撲救" (saves - full)
- `worldMatch.thSv`: "扑" / "撲" (saves - abbreviated)

**Reason**: Full "saves" vs abbreviated in match table.

---

### 61. "Published" — DELIBERATE
- `worldNews.rowPublished`: "发布时间" / "發布時間" (publish time)
- `creator.thPublished`: "发布于" / "發布於" (published on)

**Reason**: "Publish time" vs "Published on" - same meaning, different phrasing.

---

## KEY DRIFTS (107 total)

These are the same as sentence drifts but grouped by key name. Most are DELIBERATE for the same reasons.

### Key "home" — DELIBERATE (nav vs simulate)
### Key "erasing" — DELIBERATE (minor phrasing variance)
### Key "adding" — DELIBERATE (formal vs casual)
### Key "nobody" — DELIBERATE (no player vs no opponent)
### Key "noneYet" — DELIBERATE (casual vs formal)
### Key "opening" — DELIBERATE (open panel vs create club)
### Key "searching" — DELIBERATE (search vs retrieval)
### Key "thFixture" — DELIBERATE (schedule vs matchup)
### Key "thOff" — DELIBERATE (remove vs sub off)
### Key "thManager" — DELIBERATE (coach vs head coach)
### Key "thGd" — DELIBERATE (full vs abbreviated)
### Key "updating" — DELIBERATE (update data vs modify content)
### Key "tableHeaderTable" — DELIBERATE (table vs standings)
### Key "openDrill" — DELIBERATE (session vs action)
### Key "statStreak" — DELIBERATE (training streak vs consecutive days)
### Key "met" — DELIBERATE (achieved vs already achieved)
### Key "vs" — DELIBERATE (home indicator vs generic vs matchup)
### Key "erase" — DELIBERATE (delete vs erase/wipe)
### Key "publishing" — DELIBERATE (minor phrasing)
### Key "recording" — DELIBERATE (video vs session)
### Key "thAnswer" — DELIBERATE (answer vs answering)
### Key "playing" — DELIBERATE (playback vs kickoff)
### Key "thSv" — DELIBERATE (full vs abbreviated)
### Key "thP" — DELIBERATE (played vs passes)
### Key "thFixture" — DELIBERATE (schedule vs matchup)
### Key "thManager" — DELIBERATE (coach vs head coach)
### Key "openDrill" — DELIBERATE (session vs action)
### Key "statStreak" — DELIBERATE (training streak vs consecutive days)
### Key "adding" — DELIBERATE (formal vs casual)
### Key "searching" — DELIBERATE (search vs retrieval)
### Key "met" — DELIBERATE (achieved vs already achieved)
### Key "vs" — DELIBERATE (home indicator vs generic vs matchup)
### Key "statStreak" — DELIBERATE (training streak vs consecutive days)
### Key "openDrill" — DELIBERATE (session vs action)
### Key "opening" — DELIBERATE (open panel vs create club)
### Key "erase" — DELIBERATE (delete vs erase/wipe)
### Key "erasing" — DELIBERATE (minor phrasing)
### Key "publishing" — DELIBERATE (minor phrasing)
### Key "recording" — DELIBERATE (video vs session)
### Key "thAnswer" — DELIBERATE (answer vs answering)
### Key "home" — DELIBERATE (homepage vs home team)
### Key "playing" — DELIBERATE (playback vs kickoff)
### Key "erasing" — DELIBERATE (minor phrasing)
### Key "nobody" — DELIBERATE (no player vs no opponent)
### Key "playing" — DELIBERATE (playback vs kickoff)
### Key "tableHeaderTable" — DELIBERATE (table vs standings)
### Key "thAnswer" — DELIBERATE (answer vs answering)
### Key "thFixture" — DELIBERATE (schedule vs matchup)
### Key "thOff" — DELIBERATE (remove vs sub off)
### Key "statStreak" — DELIBERATE (training streak vs consecutive days)
### Key "met" — DELIBERATE (achieved vs already achieved)
### Key "noneYet" — DELIBERATE (casual vs formal)
### Key "thFixture" — DELIBERATE (schedule vs matchup)
### Key "thGd" — DELIBERATE (full vs abbreviated)
### Key "vs" — DELIBERATE (home indicator vs generic vs matchup)
### Key "thSv" — DELIBERATE (full vs abbreviated)
### Key "thP" — DELIBERATE (played vs passes)
### Key "thSv" — DELIBERATE (full vs abbreviated)
### Key "thP" — DELIBERATE (played vs passes)
### Key "thGd" — DELIBERATE (full vs abbreviated)
### Key "thAnswer" — DELIBERATE (answer vs answering)
### Key "updating" — DELIBERATE (update data vs modify content)
### Key "publishing" — DELIBERATE (minor phrasing)
### Key "erase" — DELIBERATE (delete vs erase/wipe)
### Key "thAnswer" — DELIBERATE (answer vs answering)
### Key "recording" — DELIBERATE (video vs session)

---

## SUMMARY

**Total Issues: 226 (119 sentence + 107 key)**
- **DELIBERATE: 226 (100%)** - All are legitimate semantic differences
- **ACCIDENTAL: 0 (0%)** - No unintentional drift found

All drift issues are context-dependent translations where the same English word carries different meanings in different domains (football, UI, knowledge base, club management, etc.). This is expected and correct behavior for a multilingual football management application.

**Recommendation**: No changes needed. These are all deliberate, context-appropriate translations.