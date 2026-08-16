# NutriSpend — Deployment Plan

The full path from the current (working, local) state to a deployed, installable
app. Two halves that deploy independently:

- **Backend** → GitHub repo → **Render** (native Python web service).
- **Android** → **release build (local `gradlew`)** → sideload / Firebase.

> **Git scope:** only the *backend* needs a GitHub repo (Render deploys from git).
> The Android app is built locally — no git required for it.

Legend: `[ ]` you do it · `[C]` Claude can do it in this repo · `[R]` on Render dashboard

---

## Phase 1 — Backend prep (code)  ✅ done in this repo
- `[C]` `render.yaml` blueprint (build/start/health/env) — **done**
- `[C]` `.env.example` documenting required vars — **done**
- `[C]` Confirm Alembic + config read the DB URL from env vars (not just `.env`) — **done**
- `[C]` Confirm `.env` is gitignored — **done**
- `[ ]` *(optional, later)* rate-limit `/chat` to cap LLM spend

Already in place from earlier work: `/health` (DB ping), request/DB/LLM
observability middleware, JWT auth, migrations `0001`–`0003`.

## Phase 2 — Backend deploy (Render)
1. `[ ]` Generate a strong prod JWT secret:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
2. `[ ]` Put the backend on GitHub (this reverses the old local-only rule):
   ```bash
   git init && git add -A && git commit -m "NutriSpend backend"
   git branch -M main
   git remote add origin git@github.com:<you>/nutrispend-api.git
   git push -u origin main
   ```
   (Confirm `.env` is NOT in the commit — it's gitignored.)
3. `[R]` Render → **New → Blueprint**, point at the repo (`render.yaml` is detected).
4. `[R]` Set the secret env vars (marked `sync:false`): `DATABASE_URL`
   (Supabase pooler, port 6543), `LLM_API_KEY`, `JWT_SECRET` (from step 1).
5. `[R]` Deploy. Start command runs `alembic upgrade head` then boots uvicorn.
6. `[ ]` Verify: open `https://<service>.onrender.com/health` → DB status OK.
   ```bash
   curl https://<service>.onrender.com/health
   ```
7. `[ ]` Note the final URL (Render may add a suffix if the name is taken).

> Free tier note: the service **sleeps after ~15 min idle**; the first request
> then cold-starts (~30–60s). The app's 90s call timeout absorbs this.

## Phase 3 — Android release build (code)  ✅ done in this repo
- `[C]` `BASE_URL` is now build-type driven: debug → `localhost:8055`,
  release → the Render URL — **done** (`app/build.gradle.kts`)
- `[C]` Conditional release signing from `keystore.properties` — **done**
- `[C]` `buildConfig` feature enabled; proguard keep-rules present — **done**
- `[ ]` **Update the release URL** in `app/build.gradle.kts` (`buildConfigField
  "BASE_URL"`) to the real Render URL from Phase 2, step 7.
- `[ ]` Bump `versionCode` / `versionName` for each release.

## Phase 4 — Signing & build
1. `[ ]` Create a release keystore (**back this file up — losing it means you can
   never update the app**):
   ```bash
   keytool -genkeypair -v -keystore nutrispend-release.jks \
     -keyalg RSA -keysize 2048 -validity 10000 -alias nutrispend
   ```
2. `[ ]` Create `keystore.properties` in the Android project root (gitignored):
   ```properties
   storeFile=nutrispend-release.jks
   storePassword=********
   keyAlias=nutrispend
   keyPassword=********
   ```
3. `[ ]` Build the signed release:
   ```bash
   ./gradlew assembleRelease      # APK for sideloading
   # or: ./gradlew bundleRelease  # AAB for Play Store
   ```
4. `[ ]` Install & smoke-test the release build against the live backend:
   ```bash
   adb install app/build/outputs/apk/release/app-release.apk
   ```
   (Release behaves differently from debug — sign up, chat, log, check charts.)

## Phase 5 — Distribution  (pick one)
- `[ ]` **Sideload** the signed APK to your device (simplest).
- `[ ]` **Firebase App Distribution** — invite testers by email, get crash reports.
- `[ ]` **Play Store** — needs a $25 account, privacy policy, data-safety form,
  store listing (icon ✅, screenshots, description). Start with the *internal
  testing* track.

## Phase 6 — Post-launch
- `[ ]` Crash reporting (Firebase Crashlytics or Sentry).
- `[ ]` Backend uptime ping + watch Render logs.
- `[ ]` Iterate: TTS voice replies, MCP server, IST-timezone hardening
  (currently hardcoded in `app/api/tracking.py`).

---

## Manual steps only you can do
Creating the Render account/service, generating & safeguarding the keystore,
GitHub auth, and any Play Store / Firebase setup. Claude can prepare every file
and tell you the exact commands, but can't create those external accounts.
