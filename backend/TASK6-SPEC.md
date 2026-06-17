# Task 6 — Linking Health Data to Environment + Geolocation

**Status:** Design / spec for review. Nothing built yet.

**Goal (المهمة 6):** ربط البيانات الصحية بالبيانات البيئية والموقع الجغرافي —
take each pilgrim's health risk and **modulate it by where they physically are and the
environmental conditions there**, producing a *contextual, dynamic* risk that Task 7
(الخريطة الحرارية) paints on the map.

> Baseline health risk says *who* is fragile. Task 6 says *who is fragile **and standing
> in a dangerous place right now***. A أصفر diabetic in عرفات at 46°م / ازدحام عالٍ
> should surface as أحمر — that escalation is the whole point of this task.

Decisions locked for this spec:
- **Location source:** real device GPS, **constant location access** (foreground +
  background) from the pilgrim's phone, reported continuously to the backend.
- **Environment source:** per-zone **mock feed** (seeded, time-varying allowed). No
  external weather API.
- **Risk colors:** 3 levels — `green` / `yellow` / `red` (per challenge criteria).

---

## 1. The three pieces

```
 ┌─────────────────┐     ┌──────────────────┐     ┌────────────────────┐
 │ health baseline │     │ pilgrim location │     │ zone environment   │
 │ (Task 3/5 risk) │     │ (live device GPS)│     │ (per-zone mock feed)│
 └────────┬────────┘     └────────┬─────────┘     └─────────┬──────────┘
          │                       │  → derive zone          │
          │                       ▼                         │
          │              ┌──────────────────┐               │
          └─────────────▶│  LINKAGE RULE    │◀──────────────┘
                         │  health × env    │
                         └────────┬─────────┘
                                  ▼
                    adjusted risk level + factors[]
                       (consumed by Task 7 map)
```

Task 6 **owns** location + environment + the linkage rule. It **consumes** a baseline
health-risk score (Task 3's model). Until Task 3 exists, baseline is a clearly-marked
stub (§5).

---

## 2. Data model (new)

App: `apps/pilgrims/` (or a new `apps/geo/` — see Open Questions).

### 2.1 `PilgrimLocation`
Live + historical positions. One row per reported fix; "current" = latest by `recorded_at`.

| field         | type                         | notes                                  |
|---------------|------------------------------|----------------------------------------|
| `pilgrim`     | FK → Pilgrim, `related_name="locations"` | |
| `latitude`    | DecimalField(9,6)            |                                        |
| `longitude`   | DecimalField(9,6)            |                                        |
| `accuracy_m`  | FloatField, null             | GPS accuracy in meters                 |
| `zone`        | CharField(choices=ZONES), blank | derived server-side from lat/lng    |
| `recorded_at` | DateTimeField(db_index)      | device timestamp                       |
| `created_at`  | DateTimeField(auto_now_add)  | server receipt time                    |

Index: `(pilgrim, -recorded_at)`. Consider capping history (keep latest N or last 6h).

### 2.2 `ZoneEnvironment`
One row = an environmental reading for a zone at a time. "Current" = latest per zone.

| field           | type                       | notes                                |
|-----------------|----------------------------|--------------------------------------|
| `zone`          | CharField(choices=ZONES, db_index) |                              |
| `temperature_c` | FloatField                 | dry-bulb °C                          |
| `humidity_pct`  | PositiveSmallIntegerField  | 0–100                                |
| `heat_index_c`  | FloatField                 | computed from temp+humidity (§4.1)   |
| `crowd_level`   | CharField(choices=low/medium/high/extreme) |                      |
| `recorded_at`   | DateTimeField(db_index)    |                                      |

### 2.3 Zones (constants)
4 fixed Hajj zones, center + radius (point-in-radius is enough; polygons optional later).
Centers align with the mobile `map.tsx` `SITES`:

| key          | label (ar) | center lat, lng      | radius (m) |
|--------------|-----------|----------------------|------------|
| `haram`      | الحرم      | 21.4225, 39.8262     | ~1200      |
| `mina`       | منى        | 21.4133, 39.8940     | ~2500      |
| `muzdalifah` | مزدلفة     | 21.3770, 39.9355     | ~2500      |
| `arafat`     | عرفات      | 21.3545, 39.9840     | ~3000      |

`zone_for(lat, lng)` → nearest center within its radius, else `"outside"`.

---

## 3. Linkage rule (the heart of Task 6)

`assess(pilgrim) -> { level, score, factors[] }`

```
baseline   = baseline_health_score(pilgrim)        # 0..1   (Task 3 / stub §5)
env        = current_environment(zone_of(pilgrim)) # ZoneEnvironment or None
vuln       = heat_vulnerability(pilgrim)           # 0..1   (how dangerous heat is for them)

env_sev    = environment_severity(env)             # 0..1   (§4.2)
amplify    = env_sev * vuln * MAX_BOOST            # MAX_BOOST ≈ 0.6
adjusted   = clamp(baseline + (1 - baseline) * amplify, 0, 1)

level      = green  if adjusted < 0.34
             yellow if adjusted < 0.67
             red    otherwise
```

Key properties:
- If the pilgrim is in a calm zone (`env_sev≈0`) → `adjusted ≈ baseline`. No false escalation.
- A robust young pilgrim (`vuln≈0`) is barely moved even in harsh environment.
- A fragile pilgrim in a harsh, crowded zone gets pushed toward `red`.
- `(1 - baseline)` term means escalation has headroom — never overflows past 1.

### `factors[]` — for decision support (Task 9) and the map callout
Human-readable Arabic reasons, e.g.:
- `"حالة قلبية مزمنة"` (from health)
- `"مؤشر حرارة 47°م في عرفات"` (from env+location)
- `"ازدحام عالٍ"` (from env)
- `"آخر موقع منذ 8 دقائق"` (staleness flag if location is old)

---

## 4. Environment math

### 4.1 Heat index
Standard heat-index (Rothfusz) approximation from `temperature_c` + `humidity_pct`,
or a documented simplified curve. Stored on the row so it's not recomputed everywhere.

### 4.2 `environment_severity(env) -> 0..1`
Weighted blend, normalized:
```
heat_norm  = clamp((heat_index_c - 32) / (54 - 32), 0, 1)   # 32°→0, 54°→1
crowd_norm = {low:0, medium:0.4, high:0.75, extreme:1.0}[crowd_level]
hum_norm   = clamp((humidity_pct - 30) / (90 - 30), 0, 1)

env_sev = 0.55*heat_norm + 0.30*crowd_norm + 0.15*hum_norm
```
Weights are tunable; heat dominates because it's the primary Hajj mortality driver.

---

## 5. Baseline health score (stub until Task 3)

Task 6 must not block on the risk model. Define:
```
baseline_health_score(pilgrim) -> 0..1
heat_vulnerability(pilgrim)    -> 0..1
```
Stub implementation derives from `HealthProfile` + age:
- chronic cardiac / respiratory / renal keywords in `diseases_text` → raise both
- diabetes / hypertension → raise baseline moderately, vulnerability moderately
- age ≥ 65 → raise vulnerability
- empty / healthy profile → low

Mark clearly: **replace `baseline_health_score` with Task 3 model output when available.**
`heat_vulnerability` stays in Task 6 (it's an environment-interaction concept).

---

## 6. API (for the app + Task 7 map)

| method | path                                      | purpose                                   |
|--------|-------------------------------------------|-------------------------------------------|
| POST   | `/api/pilgrims/<patient_id>/location/`    | device reports a GPS fix (lat,lng,acc,ts) |
| GET    | `/api/map/pilgrims/`                       | all pilgrims w/ latest location + adjusted risk + factors → feeds heat map |
| GET    | `/api/zones/environment/`                 | current env per zone (for dashboard env row + heat tint) |

`GET /api/map/pilgrims/` response item (replaces mobile mock `PILGRIMS`):
```json
{
  "patient_id": "A1B2C3D4E5F6",
  "full_name": "محمد الفارسي",
  "lat": 21.4225, "lng": 39.8262,
  "zone": "haram",
  "risk": "red",
  "score": 0.81,
  "factors": ["حالة قلبية مزمنة", "مؤشر حرارة 46°م", "ازدحام عالٍ"],
  "location_age_seconds": 42
}
```

---

## 7. Mobile side — constant location access

The pilgrim app reports position continuously. Using `expo-location`:

- **Permissions:** foreground + **background** location
  (`requestForegroundPermissionsAsync` → `requestBackgroundPermissionsAsync`).
  `app.json`: `NSLocationWhenInUseUsageDescription`,
  `NSLocationAlwaysAndWhenInUseUsageDescription`, Android
  `ACCESS_BACKGROUND_LOCATION`, `expo-location` plugin with background mode.
- **Tracking:** `Location.startLocationUpdatesAsync` backed by a `TaskManager` task
  (survives backgrounding), with a distance/time interval (e.g. every 30–60s or 25m).
- **Reporting:** task POSTs each fix to `/api/pilgrims/<patient_id>/location/`. Buffer
  + retry when offline.
- **UX/consent:** explicit screen explaining *why* constant location is needed
  (safety / rapid medical response), since iOS/Android will gate background GPS hard.

> Note: "constant location access" is a real privacy + battery commitment and an App
> Store review point. The consent screen + a clear purpose string are mandatory, not
> optional.

---

## 8. Demo seed data

- `ZoneEnvironment`: seed each zone with plausible values; make عرفات/منى harsh
  (45–47°م, humidity 55–65%, crowd high/extreme) and الحرم moderate. Optional management
  command to "advance" the scenario (peak-of-day spike) for a live demo.
- `PilgrimLocation`: seed latest fixes spread across the 4 zones (mirror the 20 mock
  pins already in `map.tsx`) so `/api/map/pilgrims/` returns a populated heat map even
  before any real device reports in.

---

## 9. How Task 7 consumes this

`map.tsx` today hardcodes `PILGRIMS` and computes heat purely from `risk`. After Task 6:
- `PILGRIMS` ← `GET /api/map/pilgrims/` (real linked risk, not just health risk)
- dashboard env row (`44°م · 62% رطوبة · عالٍ ازدحام`) ← `GET /api/zones/environment/`
- callout shows `factors[]` → instant "why is this person red" for the medical team

No change to the map's *visual* design is required — only its data source.

---

## 10. Open questions before build

1. **App placement** — extend `apps/pilgrims/` or create `apps/geo/` for location +
   environment? (Leaning `apps/geo/` to keep the pilgrim app focused.)
2. **Location history retention** — keep full history, or only latest + short trail?
   (Privacy + DB size.)
3. **Recompute timing** — assess risk on read (per `GET /api/map/pilgrims/`) or on each
   location/env write (cached)? On-read is simplest for the demo.
4. **Who carries the app** — every pilgrim (mass background GPS) vs. a wristband/beacon
   model. Spec assumes pilgrim-phone GPS per your call; worth confirming for the story.
5. **Baseline ownership** — confirm Task 3 will later supply `baseline_health_score`, so
   the stub stays swappable.
