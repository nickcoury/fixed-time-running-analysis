# Data Collection Log

Detailed trail of what was searched, what was found, what worked, and what to try next.

---

## 2026-03-22 — Initial Research Phase

### Session 1: Source Mapping

**Sources ranked by split richness:**

| Source | Granularity | Public? | Best For |
|--------|------------|---------|----------|
| Race timing systems (RACE RESULT, bao-ming.com) | Lap-by-lap | Sometimes during live events | Current races |
| Centurion Track 100 | 50K/50mi/100K/6h/12h splits for all finishers | Yes | 100mi track |
| DUV statistik.d-u-v.org | 6h/12h/100km/100mi intermediates | Yes | Bulk discovery |
| Bob Hearn's blog | Lap-by-lap custom analysis | Yes | EMU, Desert Solstice, 6 Jours |
| iRunFar | Narrative pace bands, some checkpoint data | Yes | Marquee performances |
| ARRS (Andy Milroy) | Historical checkpoint splits | Yes | Pre-2000 records |
| Sri Chinmoy Races archive | Checkpoint splits per year | Yes | 1984-1990s 24h races |
| Ultrarunning History | Narrative splits | Yes | Historical context |
| Aravaipa (Desert Solstice, Jackpot, ATY) | Chip timing per-lap | No (internal) | Elite 24h/timed |
| IAU championship lap data | Per-lap on 1.5-2km loops | No (by request) | World championships |
| OpenSplitTime | Aid station level | Yes, structured | Small catalog |

### DUV URL Patterns (Working)
- All-time list: `https://statistik.d-u-v.org/getintbestlist.php?year=all&dist=24h&gender=M&cat=all&nat=all`
- Athlete profile: `https://statistik.d-u-v.org/getresultperson.php?runner=RUNNER_ID`
- Event results: `https://statistik.d-u-v.org/getresultevent.php?event=EVENT_ID`
- Available dist params: 24h, 12h, 6h, 48h, 72h, 100km, 100mi, 6d, 10d

### Key Findings

**DUV All-Time 24h Top 50 extracted (both genders)**
- Men: Sorokin 319.6km down to Gore 270.8km. Nick is #18 at 278.4km.
- Women: Webster 278.6km down to Fredriksson 241.7km. Herron is #4.
- Major update: Sarah Webster (GBR) broke Herron's record at Albi 2025 with 278.622km!

**Centurion Track 100 checkpoint splits extracted:**
- 2021: 8 finishers (Sorokin WR 11:14:56, Amend British WR 14:34:03)
- 2022: 5 finishers (Sorokin DNF at 100K pace of 6:05:41, Whearity 12:42:04)
- 2023: 6 finishers (Lawson 12:37:10, Lid 14:13:15)

**Kouros splits compiled from multiple sources:**
- 1984 Sri Chinmoy 24h: Marathon/50mi/100K/100mi/200K checkpoints (3 WRs)
- 1985 Sri Chinmoy 24h: 1mi/10mi/20mi/50K/50mi/100K/100mi/200K (richest set)
- 1997 Adelaide 24h: Marathon/100K/12h/100mi/200K (303.5km WR)
- 2001 Verona IAU WC: 50K/6h/50mi/100K/12h/100mi (deepest DUV splits)
- 1996 Surgères 48h: 6h/100K/12h/100mi/24h (48h WR)
- 1984 NYRRC 6-day: 24h/48h/72h (635mi)
- 2005 Colac 6-day: 24h/48h/1000K (1036.8km WR, age 49)

**Woodward 1975 100mi WR:** 10 checkpoint splits from ARRS article (richest historical data)

**Herron 2019 Albi:** 12h/20h/24h splits published

### Data Created This Session

| File | Runner | Race | Year | Distance | Data Type |
|------|--------|------|------|----------|-----------|
| adelaide-1997-yiannis-kouros.json | Kouros | Sri Chinmoy Adelaide | 1997 | 24h/188.5mi | 6 checkpoints |
| sri-chinmoy-1984-yiannis-kouros.json | Kouros | Sri Chinmoy NY | 1984 | 24h/177mi | 6 checkpoints |
| sri-chinmoy-1985-yiannis-kouros.json | Kouros | Sri Chinmoy NY | 1985 | 24h/178mi | 9 checkpoints |
| verona-2001-yiannis-kouros.json | Kouros | IAU WC Verona | 2001 | 24h/171mi | 7 checkpoints |
| surgeres-1996-yiannis-kouros.json | Kouros | Surgères 48h | 1996 | 48h/294mi | 6 checkpoints |
| colac-2005-yiannis-kouros.json | Kouros | Colac 6 Day | 2005 | 6d/644mi | 4 checkpoints |
| nyrrc-1984-yiannis-kouros.json | Kouros | NYRRC 6 Day | 1984 | 6d/635mi | 4 checkpoints |
| bedford-2021-aleksandr-sorokin.json | Sorokin | Centurion Track 100 | 2021 | 100mi | 6 checkpoints |
| bedford-2021-samantha-amend.json | Amend | Centurion Track 100 | 2021 | 100mi | 4 checkpoints |
| bedford-2023-dan-lawson.json | Lawson | Centurion Track 100 | 2023 | 100mi | 6 checkpoints |
| tipton-1975-cavin-woodward.json | Woodward | BRRC 100mi | 1975 | 100mi | 10 checkpoints |
| albi-2019-camille-herron.json | Herron | IAU WC Albi | 2019 | 24h/168mi | 3 checkpoints |

**Total: 15 performances (3 per-mile, 12 checkpoint-level)**

### World Record Corrections Found
- 72h women's WR: Viktoria Brown (CAN), NOT Bereznowska
- Bereznowska holds 48h WR (436.371 km, 2025 UltraPark, Poland)
- 6-day men's may have been updated: Ivan Zaborsky 1,047.554 km (2025)
- GOMU (not IAU) governs multi-day championships
- Sarah Webster (GBR) broke women's 24h WR at Albi 2025 with 278.622 km

### Next Steps — Priority Order

**Immediate (next session):**
1. DUV intermediate splits — scrape athlete profiles for top 50 men/women 24h performers
2. More Centurion finisher data — extract remaining finishers from 2021-2023
3. Albi 2025 championship data — new WRs just set, check for published splits
4. Sorokin Verona 2022 (319.6km WR) — check if any more splits surfaced

**Medium term:**
5. Bob Hearn blog — extract his lap-by-lap analysis data (EMU, Desert Solstice)
6. Across the Years archives — check for published split data
7. Jackpot Ultra results — Aravaipa chip timing data
8. Taipei championship results (2023) — bao-ming.com timing portal
9. DUV 48h/6d/12h top lists — expand beyond 24h

**Requires outreach:**
10. Contact Aravaipa Running — request Desert Solstice historical chip data
11. Contact IAU — request championship lap-by-lap data
12. Contact Camille Herron — she's shared her splits with journalists before
13. Contact Bob Hearn — he has custom-extracted lap data from timing systems

**Long-term data archaeology:**
14. Kouros hourly splits — check coaching materials, books ("Running Over the Sahara")
15. Academic papers on ultra pacing — some include raw data in appendices
16. National federation all-time lists (USATF, UKA, Athletics Australia)
17. Kaggle ultra dataset (7.4M records) — useful for population analysis, not splits
