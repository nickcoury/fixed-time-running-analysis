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

---

## 2026-03-22 — Session 2: Championship Per-Lap Data & DUV Profiles

### Major Data Sources Discovered

**Lupatotissima Timing Data (lupatotissima.it)**
- Excel files with per-lap timing for entire IAU championship fields
- Verona 2022: ~200 laps per athlete on 1525.48m loop. Complete field timing.
- Converted to hourly interpolated checkpoints (24 data points per athlete)

**Taipei 2023 Timing Data**
- Excel files with per-lap data for IAU WC Taipei 2023
- 2km loop with intermediate timing at 0.8K and 1.8K
- Complete field timing, ~150 laps per athlete

**BreizhChrono (breizhchrono.com)**
- French timing platform used for Albi championships
- Results export available at `/resultats-courses/.../export` (Excel format)
- Individual timing accessible but JavaScript-heavy live pages

**DUV Athlete Profiles**
- Rich intermediate splits on many athlete pages: 6h, 12h, 100km, 100mi, 50km, 50mi
- URL: `statistik.d-u-v.org/getresultperson.php?runner=RUNNER_ID&dist=24h`
- Coverage varies by race — IAU championships tend to have more splits

### Data Created This Session

**Verona 2022 IAU 24h EC (106 files)**
- 50 men above 139mi threshold, 56 women above 117mi threshold
- Per-lap timing → 24 hourly interpolated checkpoints each
- Top: Sorokin 198.6mi, Piotrowski 187.6mi, Bereznowska 159.2mi
- Source: Lupatotissima Excel files (`/tmp/verona_splits_men.xlsx`, `verona_splits_women.xlsx`)

**Taipei 2023 IAU 24h WC (111 files)**
- 54 men, 57 women above thresholds
- Per-lap timing → 24 hourly interpolated checkpoints each
- Top: Sorokin 187.5mi, Zisimopoulos 181.6mi, Nakata 168.0mi
- Source: Taipei timing Excel files (`/tmp/taipei_laps1.xlsx`, `taipei_laps2.xlsx`)

**DUV Athlete Profile Splits (46 files)**
Athletes scraped: Sorokin (4 races), Tkachuk (3), Zisimopoulos (1), Norum (2),
Hara (2), Herron (4), Dauwalter (2), Kudo (2), Webster (1), Ranson (2),
Bereznowska (3), Falk (6), Pazda-Pozorska (2), Olsson (2), Csecsei (2),
Britton (1), Weber (3), Leblond (2), Coury (1), Nagy (1)
- Checkpoint level: 6h/12h/100km/100mi/50km/50mi where available

**Albi 2025 IAU 24h WC (97 files)**
- 48 men, 49 women above thresholds
- Final distances only (no intermediate splits from DUV event page)
- Top: Tkachuk 294.3km, Webster 278.6km WR, Ranson 274.2km, Nakata 272.0km
- Source: DUV event/119984

**Session Total: 360 new files, bringing total to 374 performances**

### Key Findings

- **Sorokin's WR pacing**: At Verona 2022, covered 15.2km in first hour (9.5mi), 172.3km by 12h (107mi), finishing at 319.6km. Remarkable consistency.
- **Gender pacing differences visible**: At Verona, top women started slower but many showed less falloff in second half
- **Multi-championship athletes**: Many runners appear at both Verona 2022 and Taipei 2023, enabling longitudinal comparison
- **Albi 2025 field**: 363 finishers from 45 countries — largest 24h championship ever

### Next Steps — Updated Priority Order

**Immediate:**
1. ✅ DUV intermediate splits for top 50 — DONE
2. ✅ Albi 2025 championship data — DONE (final distances)
3. ✅ Sorokin Verona 2022 WR — DONE (hourly from per-lap)
4. ✅ Taipei 2023 championship — DONE (hourly from per-lap)
5. Desert Solstice historical results — research agent dispatched
6. European championship data — research agent dispatched
7. Japanese/Asian race data — research agent dispatched
8. Albi 2025 per-lap timing — BreizhChrono has it but needs Playwright for JS-heavy pages

**Medium term:**
9. Bob Hearn blog — extract lap-by-lap analysis (EMU, Desert Solstice)
10. Across the Years archives
11. Albi 2019 per-lap timing — BreizhChrono has this too
12. DUV 48h/6d/12h top lists — expand beyond 24h
13. Soochow/Taipei annual race results (2007-2024) — rich Japanese/Taiwanese data

**Requires outreach:**
14. Contact Aravaipa Running — Desert Solstice chip data
15. Contact IAU — championship per-lap archives
16. Contact Bob Hearn — custom timing extracts

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
