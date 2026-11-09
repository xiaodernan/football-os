---
id: expected-goals-explained
title: "Expected goals: what the number means when the engine prints it"
category: match-analysis
tags: [expected goals, xg, shot quality, xG per shot, chance quality, non-penalty xG, xG against, finishing conversion]
applies_to: [all]
difficulty: beginner
source: "FOOTBALL OS original editorial content — written for this project, no external text reproduced"
confidence: high
last_reviewed: 2026-11-09
---

## What xG is, in the shortest honest sentence

An expected-goals value is an estimate of how likely one shot was to become a goal, written as a number between 0 and 1 and produced by a model that studies millions of past shots and the handful of things that made them. A shot from the six-yard box with one defender in the way and a one-touch finish counts as high quality and is written as a figure close to one. A long-range effort from outside the area, off balance, in the last minute of a lost game counts as low quality and is written as a figure close to zero. xG is not a fraction of a goal and not a referee's opinion — it is the model's answer to the question *if an average player took this exact chance, how often would it go in?*

Every xG in this build — the report the simulator prints, the market ledger, the academy benchmarks — is an estimate behind a formula the page also prints. It is not measured by camera or tracking; it is computed from the shot itself.

## What the number is actually made of

A pre-shot xG model wants to know where the shot was taken from, how it was hit, and what the shooter had to beat. Distance from goal matters more than almost anything else, because close range is where goals come from. The angle changes things: a shot from a narrow angle far side is worth less than a shot from closer in the same distance. Whether the shot was taken with the foot, from a header or from a set piece — penalties are treated separately because open play and set play behave differently. Whether the chance came from a through ball, a cross or a rebound. How many defenders were between the shooter and goal. Some models also use the speed of the move and whether the keeper was set.

It does not know, at the moment the number is written, whether the ball crossed the line. That is the entire point: xG is assigned *before* the outcome, so a misses-by-an-inch does not get to disagree with it afterwards. It is the chance, not the result.

## Reading a report with xG in it

Three habits make the figure useful instead of decorative. First, read the movement of xG across the match, not only the final total: a team that created nothing for an hour and then pushed twice in the last ten minutes will read low xG on the whole and can still have lost fairly, while a team that rode 1.2 xG of earlier pressure may feel unbeaten. Second, compare the goals with the xG, not with the scoreline — a 2-2 draw with 2.8 xG to 0.4 is an entirely different story from a 2-2 draw with 0.4 both ways, and only one of them questions the finishers. Third, read *per shot* as well as the sum: five shots worth 0.11 each say a different thing to three shots worth 0.31. The per-shot figure is where shot selection shows up, and where a forward is turning good positions into mediocre attempts.

When the figure is printed beside the totals \u2014 as in the simulator's report, where the model names its own formula \u2014 read it as the model's own arithmetic, not as the universe's verdict. If the model was built to say "this block was shredded from distance", a one-game 0-dimension win with 2.1 xG is not proof the model is wrong. It is the agreed set of inputs doing what the inputs always do.

## What xG cannot tell you, and should never be asked to

It is an estimate of chance *quality*, not a rating of the striker's technique, the coach's plan, the referee, or the opponent's ambition. A player who finishes at 2x his xG over a season is either world-class at finishing or the sample is small and variance is winning \u2014 xG cannot say which; only more shots will. xG also says nothing about chances that were never taken \u2014 the crosses nobody met, the wrong option chosen with a clear run at goal — and xG is measured per shot or per penalty area, not per decision. It cannot see a keeper's error that made a shot 0.05 into a tap-in. And it does not care about the game state it was used in: a 5 xG in a lost final and a 5 xG in a comfortable win read the identical.

Never conclude "we should have won" from xG. Conclude, rather, "the chances were there, and next week the same chance quality will still bring return" — that is the actual use of the figure, and it is a coach's sentence, not an arbiter's.

## Using xG as a training cue

The gap between goals and xG over many weeks is diagnostic, not judgement. A player consistently underperforming his xG has a technical conversion problem to discuss with a coach — finishing drills against the far corner, shot placement rather than power, first-contact mechanics. Consistently beating xG means the eye and the timing are better than the process "average" model \u2014 maintain what works rather than overhaul it. For a team, the useful split is *creating* versus *taking*: low xG with high conversion is luck wearing a good coat; high xG with low conversion is a finishing problem; high xG with high conversion is what everyone's chasing.

In this build the motion is simulated from a model whose every rate is printed beside it, which makes the practice repeatable: rerun the fixture with the same teams, the same system and the same seed and the xG comes back identical or it is a bug. That repeatability is the actual reason xG belongs in a training system \u2014 the number you train against does not move because you slept badly or the referee was kind.
