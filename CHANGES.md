# DevicePulse — real readings only

Every number the app shows now comes from the phone. Anything Android doesn't expose shows "--" or a guide to Android Settings.

## Server (backend/server.py)
- New `POST /api/device/readings`: the phone sends measured storage total/free, app cache, battery %, charging. Validated (free ≤ total, battery 0–100).
- Removed the fixed fake snapshot (128 GB / 94.2 GB used / battery 54% / "1 minor issue") and the invented junk/growth estimators.
- Daily Pulse, widget summary, device health, family scores and shared reports use the latest real reading, or return null when none exists. Days with no reading are not cached.
- Forecast uses the measured free-space slope (needs 2+ readings at least a day apart), otherwise null.
- Health trend uses weekly real readings; no invented baseline.
- `/device/clean` no longer returns made-up before/after scores.
- Smart nudges: no invented security issue; "space to reclaim" uses measured cache only.
- Now return HTTP 410 (were random/simulated): /device/scan, /device/storage, /device/cache-breakdown, /device/duplicates(+/scan, /remove), /device/large-files(+/scan, /delete), /device/battery(+/optimize), /device/memory(+/boost), /device/security(+/scan, /findings/{id}/resolve), /family/remote-clean/{id}, /autoclean/run-if-due, /forecast/quick-fix.
- New test: backend/tests/test_real_readings.py (needs `pip install mongomock-motor`).

## App (frontend/)
- src/deviceStorage.ts: no fallback score of 70; no predicted post-clean score; new `reportReading()` and `tryScanLocalDevice()`.
- src/api.ts: added `postReading`; removed clients for retired endpoints.
- Home, Smart Scan and after-cleanup results send the real reading.
- Widget preview, cleanup report, guest and trends show "--" / "Run a Smart Scan" instead of fake values.

## Checks run
- Expo Doctor 18/18, TypeScript clean, Android bundle export OK.
- Server: before any reading → all null; after a reading of 125 GB / 31 GB free / 81% → score 82, 75% used, battery 81; retired endpoints → 410.
- Not yet run on a real phone.

## Deploy
1. Deploy backend to Render first (same env vars).
2. `cd frontend && eas build --platform android --profile production` (versionCode auto-increments).
3. Old database rows: existing `pulse_daily`/`cleanup_reports` docs were made from fake numbers; delete them (`db.pulse_daily.deleteMany({})`, regenerate reports) before release.
4. Paywall still advertises the duplicate finder / large-file list — those screens are Android guides now, so update the Pro perks text before submitting.
