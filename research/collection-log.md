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

---

## 2026-03-22 — Session 3: Top-50 Completion, Multi-Distance Expansion

### Methodology

**Systematic DUV top-50 sweep:** Fetched all-time top-50 men and women 24h lists from DUV. Identified 43 athletes missing from the dataset. Scraped each athlete's DUV profile page for all 24h results with intermediate splits. Created split files for every qualifying performance.

**Multi-distance expansion:** Extended dataset to 48h, 6-day, and 12h distances. Fetched DUV profiles for top performers in each distance. Created separate distance categories in the index.

**Background research agents:** Dispatched three parallel agents:
1. **DUV 48h/6d/12h top-20 lists** — complete rankings with runner IDs
2. **Desert Solstice/ATY/Jackpot** — RaceResult has per-lap data (needs Playwright), Bob Hearn blog has pace charts
3. **Japanese/Asian 24h data** — Jingu Gaien has JUA hourly PDFs, Soochow has 19 editions on DUV

### Data Created This Session

**DUV Profile Scraping — 24h Top-50 Completion (72 files)**
- Men: Zaborskii, Zhalybin, Field, Morton, Sekiya (6 Soochow races), Filipov, Bonne, Nunes, Inoue (3 races), Clavery, Napiorkowski (2), Schwerk (2 historical), Kruglikov (3), Safin, Polozhentsev, Bystrov (2), Ailenei (2), Otaki (2)
- Women: Berces (2), Lizak (5 Desert Solstice with rich splits), Slaby (4), Little, Smith, Churanova (2), Ovsiannikova, Tarnutzer (2), Honkala (2), Dimitriadu, Lomsky (2 historical), Fontaine (3), Caliskaner, Fredriksson, Sakane, Gogoleva, Sidorenkova

**48h Performances (16 total)**
- Bonne 485km 48h WR (Pabianice 2025)
- Bereznowska 436km 48h women's WR, plus 2024 Taipei with 7 checkpoints (richest 48h data)
- Herron 435km Canberra with 100mi/200km/24h splits
- Fudali 3 races (Pabianice, BUFF, Taipei with 50km/100km/100mi/24h)
- Holvik 451km Taipei with 12h/100mi/24h splits
- Zakrzewski 411km Taipei with 12h/100mi/24h
- Rex 3 races (BUFF, UltraPark, Athens with 12h/24h)
- Tonstad UltraPark with 24h split
- Tkachuk 435km Vinnitsa with 6h/12h splits

**6-Day Performances (8 total)**
- Zaborskii 1047km 6-day WR with 24h/48h/72h splits
- Bonne 1045km #2 all-time with 100km/100mi/24h/48h/72h splits (richest 6d data)
- Eckert 970km women's WR with 24h/48h/72h splits
- Rex 930km, Herron 901km, Lawson 920km with 24h/48h splits
- Kouros 1036km and 635mi already from Session 1

**12h Performance (1)**
- Bitter 168.8km 12h WR with 50km/50mi/100km/100mi splits

**Additional 24h Performances**
- Soochow/Taipei: Hara 285km (2014), Ishikawa 279km (2019), Herron 263km, Odani 264km, Shevchenko 242km (all 2024), Gore 270km (2024)
- Desert Solstice 2020 field: Montgomery, Camastro, Hearn, Lewis
- Bitter: 3 Desert Solstice/Dome races with splits

### Key Findings

- **Sekiya dominance at Soochow:** Ryoichi Sekiya ran Soochow/Taipei 24h 12 times (2001-2018), with 6 performances above 260km. His 2011 race has the richest splits: 50km/50mi/100km/12h/100mi.
- **Lizak's Desert Solstice consistency:** Marisa Lizak ran Desert Solstice 5 times (2019-2024) with rich 50km/100km/12h/100mi splits every year. Her pace patterns show remarkable year-over-year consistency.
- **48h pacing patterns:** Top 48h athletes cover ~55-60% of total distance in first 24h. Bereznowska: 230/427=54%, Bonne: 265/465=57%, Fudali: 252/433=58%.
- **6-day pacing:** Bonne covered 238/411/570/1045 (24h/48h/72h/6d), showing ~40% of total distance in first 24h, ~55% by 48h, ~55% by 72h. Significant tail-end volume.
- **Multi-distance athletes:** Many runners appear across 24h, 48h, and 6d. Bereznowska (#5 24h, #1 48h), Rex (#37 24h, #4 48h, #2 6d), Herron (#4 24h, #2 48h, #3 6d).

### Session 3 Totals
- **489 performances** across **71 races** and **5 distances** (24h, 48h, 6d, 12h, 100mi)
- **7 commits** pushed to repo
- Complete coverage of all-time top 50 men and women in 24h

---

## 2026-03-21 — Session 4: Multi-Distance Expansion

### Approach
Systematic sweep of all-time top-20 lists for all 5 distance categories (48h, 6d, 12h, 100mi) from DUV. Individual athlete profile fetches for split data.

### 48h Batch (43→55 performances)
New athletes added: Otaki (5 Taipei + 3 Surgères races, richest 48h data), Boussiquet (3 Surgères), Mangan (Brno + Surgères), Rusek (Surgères 1995 + Brno), Piotrowski (GOMU 2025), Kocourek (Brno 1998/2000), Marchesi (4 races, Athens has 12h/24h splits), Fatton (EMU 2017), Berces (Surgères 2003/2005), Reutovich (Brno 2002 + Surgères 2003), Matos (Mantiqueira 2018), Huang (5 Taipei races with 6h/12h/24h/50km/50mi/100km/100mi splits — richest 48h data in dataset), Falbo (48h Dome 2014).

### 6d Batch (8→33 performances)
New athletes: Boussiquet (La Rochelle 1984/85/92 — historic 1000km+ era), Mainix (La Rochelle 1986/92), Zarei (Gateshead 1990), Chaigne (Antibes 2012 + Balatonfüred 2014), Kocourek (Colac 1999), Schwerk (Erkrath 2007 WR-era + 3 EMU/Balatonfüred with 24h/48h splits), Byambaa (Hirosaki 2025 + Dome 2021 + Sri Chinmoy 2022), Fejes (EMU 2015 + Dome 2014/2019 with 24h/48h/72h splits), Maraz (GOMU 2024 + EMU 2022 with 24h/48h/72h), Masanova (GOMU 2025 with 24h/48h/72h), Huang (Hirosaki 2025), Bjerre (Åbybro 2025).

### 12h Batch (1→22 performances)
New athletes: Sorokin (Spartanion 2022 WR 177.41km), Bitter (Dome 2019 + Equalizer 2025), Piotrowski (SLO24 2023 + Bad Blumau 2021), Lipiäinen (Kokkola 2023 WR-era + 2 Joensuu with 6h/100km splits), Stelmach (Spartanion 2023), Nakata (Taipei 2022/2023), Pont Chafer (Barcelona 2023 with 6h split), Rüeger (SLO12 2023), Olsen (Ottawa 2013), Perez Serrano (Louny 2023 with 6h/50km/100km + SLO12 2024), Honkala (Sparta 2023), Zhalybin (St Petersburg 2006), Ailenei (Barcelona 2022 with 6h/100km/100mi splits), Tarnutzer (Barcelona 2022 with 6h/100km), Berg (Gothenburg 2025 with 50mi/6h/100km).

### 100mi Batch (5→16 performances)
New athletes: Sorokin (Lupatotissima 2022 WR 11:12:13 + Centurion 2021 with 50km/50mi/100km splits), Bitter (Dome 2024 with 50km/100km + DS 2015), Olsson (Tunnel Hill 2023), Kharitonov (Crystal Palace 2002 with 50km/100km splits), Paulson (Jackpot 2026 WR 12:19:34 + 2024), Jennings (Tunnel Hill 2025), Trason (Sri Chinmoy 1991), Slaby (DS 2016).

### Key Insights
- **Huang is the Taipei 48h queen:** 8 Taipei races (2017-2026) with the richest intermediate split data of any 48h athlete. 7 checkpoints per race including 50km/50mi/100km/100mi time-to-distance plus 6h/12h/24h distance splits.
- **La Rochelle 1992 was a golden year:** Boussiquet (1034km), Mainix (1007km), and Zarei (974km) all ran 6-day at La Rochelle in 1992. Three 900km+ performances in the same race.
- **33 multi-distance athletes** now span 2-3 distance categories, enabling cross-distance pacing analysis.
- **Otaki's Surgères longevity:** 4 Surgères + 6 Taipei 48h races from 2005-2025, with his best (426km) at Surgères 2007 showing 126km at 12h → 234km at 24h → 191km in second 24h.

### Session 4 Totals (Final)
- **627 performances** across **128 races** and **5 distances**
- 24h: 459, 48h: 74, 6d: 42, 12h: 27, 100mi: 25
- **409 unique runners**, **44 nationalities**, year range 1975-2026
- **33 multi-distance athletes**, 9 spanning 3+ distances
- Camille Herron spans all 5 distances (unique in dataset)
- **227 performances** with 7-24 checkpoints (rich hourly data)
- **11 commits** pushed

### Next Steps — Updated Priority Order

**Immediate:**
1. ✅ All top-50 men/women 24h — DONE
2. ✅ 48h top-20 — DONE
3. ✅ 6d top-20 — DONE
4. ✅ 12h top-20 — DONE
5. ✅ 100mi top-20 — DONE
6. RaceResult per-lap data — Desert Solstice 2019-2022 via Playwright
7. JUA Jingu Gaien hourly PDFs — per-runner per-hour lap counts

**Medium term:**
8. Soochow full-field DUV results — 19 editions, 964 finishers
9. BreizhChrono per-lap — Albi 2019 + 2025 via Playwright
10. Bob Hearn blog pace charts — embedded PNG analysis
11. Across the Years archives — RaceResult per-lap via Playwright
12. More 48h/6d/12h profiles beyond top-20

**Requires outreach:**
13. Contact Aravaipa Running — Desert Solstice/ATY/Jackpot chip data
14. Contact IAU — championship per-lap archives
15. Contact Bob Hearn — custom timing extracts

**Long-term:**
16. Kouros hourly splits from books/coaching materials
17. Academic papers with raw pacing data
18. National federation all-time lists
