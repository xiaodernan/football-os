---
id: how-to-read-the-honours-spine
title: "How to Read the Roll of Honours — 24 Real Tournaments, One Spine"
locale: en
category: history
tags: [honours, roll-of-honours, world-cup, euro, records, openfootball, how-to-read]
applies_to: [all]
difficulty: intermediate
source: "FOOTBALL OS original editorial — computed from the committed openfootball snapshots (CC-BY 4.0); every figure on this page is recomputable from them"
confidence: high
last_reviewed: 2026-11-17
---

## What the spine is

The Roll of Honours in this product is one table with twenty-four rows: the twenty-two World Cups this product carries (1930 Uruguay through 2022 Qatar) plus the two European Championships (Euro 2021, the 2020 tournament played across Europe in 2021; Euro 2024 Germany). That is 1,066 matches and 2,979 goals counted on the pitch. No synthetic rows appear here. Every figure is recomputed from the committed openfootball snapshots each time you open the door — the product never stores a copy, so what you read is the arithmetic of the files themselves, not a number somebody typed into a page.

One structural detail matters before you read anything else: the `kind` field separates a `worldcup` row from an `euro` row. The champion ledger counts them together, but the question "how many titles does Italy own?" deserves the precise answer — five, of which four came at World Cups (1934, 1938, 1982, 2006) and the fifth at Euro 2021. Spain's two are 2010 and Euro 2024. Brazil's five are all World Cups: 1958, 1962, 1970, 1994, 2002. Uruguay two: 1930 and 1950. Argentina three: 1978, 1986, 2022. West Germany three: 1954, 1974, 1990 — counted separately from 2014 Germany, because the snapshots name the federation as it was at the final's whistle, and conflating them would be tidier but less true. France two: 1998, 2018. England one: 1966.

## How the finals are printed

Each row of the spine prints three scorelines, always in the same order: regular time, extra time if played, penalties if taken. A final that went the whole way looks like 2022's — 2-2 after ninety, 3-3 after extra time, 4-2 on penalties — so you can tell at a glance whether a cup was won on the pitch or at the spot. `went_extra_time` is its own column. Goals are counted on the field only; penalty deciders add no entries to the goals tally.

## Two finals worth memorising before you browse

1950, the Maracanazo. Brazil hosted, Uruguay won 2-1 in the Final Round decider at the Maracanã. It remains the starkest underdog ending the spine holds — the host's favourite lost the night the city expected to celebrate.

1954, the Miracle of Bern. Hungary were the stronger side on paper; West Germany won the final 3-2 at Bern. The spine prints this deciding match in its own row with the same three-scoreline layout as every other final — read it, note the sides' inputs, and let the snapshot keep the final honest rather than the folklore.

The row's widest-margin column is ranked from the tournament snapshot itself — 1982's Hungary 10-1 El Salvador at Elche is the widest the spine holds, 2002's Germany 8-0 Saudi Arabia, 1974's Yugoslavia 9-0 Zaire. Each row carries the stage, the date and the venue, so the widest win is never an orphan number.

## How to use the search box

The search door (`/world/real-book/search`) is a case-insensitive substring match over the honours spine's own figures: tournament year, host, champion, runner-up, venue, and the widest-margin match's teams. Type `Germany` and the door answers from ten rows (Germany 2014; West Germany 1954, 1974, 1990; the 2014 host slot, the Euro 2024 host slot and others that name Germany somewhere on the row). An empty box returns all twenty-four — that is deliberate, so a blank visit does not waste the trip. `q=Allemagne` answers zero: the spine is English figures by design, and an honest empty beats a fake translation table.

## What the spine does not contain

No scorers, no assists, no attendance, no bookings, no VAR notes, no weather. The spine is deliberately one shape: the tournament, the host, the final, the goals, the widest win, the title ledger. Anything beyond that belongs to the individual tournament volumes this book is bound from — and to football's own newspapers. If you find yourself looking for a player's goal tally inside an honours row, you have outgrown the spine; if you are checking whether a title was settled on the pitch or at the spot, you are exactly who it was built for.

## Provenance, said plainly

Source: openfootball `worldcup.json` and `euro.json` (CC-BY 4.0). The data is public and real; provenance is stamped on every response this door emits — `data_origin: public-real`, `is_demo_data: false`. The synthetic world that fills this product's matches is not present in the Roll of Honours, by construction. When the snapshots are re-synced from upstream, every figure above re-derives from the same bytes.
