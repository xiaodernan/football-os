# ADR-004 — Legal data first: synthetic football world behind provider abstraction

- Status: Accepted · Relates to: PRINCIPLE 4–5, §65, §78
- **Context**: Real fixtures, player ratings, photos, logos and video are protected by copyright, database rights, trademark and portrait rights. Scraping paid datasets (Opta/StatsBomb/Sportradar/FC/FM) is prohibited.
- **Problem**: The product must be data-rich for M1–M7 without any unlicensed data.
- **Options**: (a) scrape public sites; (b) buy a licence before writing code; (c) generate a synthetic football world + user-generated content, and put every real source behind `FootballDataProvider`/`NewsProvider`.
- **Decision**: (c). Deterministic generator builds teams/players/competitions/matches/news (spec §65 targets: 20 teams, 300 players, 10 competitions, 100 matches, 500 articles) with clearly fictional names; all rows carry `data_origin = synthetic | licensed | user` and every read surface renders a `DEMO DATA` badge. Only *available* metrics render; missing ones show `Data unavailable` (spec §15).
- **Consequences**: No claim of being official or of mirroring real-world data; visual assets must be generated/original. A licensed provider becomes a new adapter + data-origin change, not a rewrite. Test fixtures reuse the same generator with a small seed.
