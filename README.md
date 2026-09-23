# DevicePulse

DevicePulse by Verolane Digital Solutions is an Expo/React Native device-health app backed by a FastAPI and MongoDB service.

## Release identity

- Android package: `ca.verolane.devicepulse`
- iOS bundle identifier: `ca.verolane.devicepulse`
- Expo slug and URL scheme: `devicepulse`
- Current release: `1.0.1` (`versionCode`/`buildNumber` 4)

## Local verification

```bash
cd frontend
npm ci
npm run check
EXPO_PUBLIC_BACKEND_URL=http://localhost:8001 npm run build:web
```

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
MONGO_URL=mongodb://localhost:27017 DB_NAME=devicepulse \
  .venv/bin/uvicorn backend.server:app --host 0.0.0.0 --port 8001
```

Copy the two `.env.example` files to `.env` and fill in deployment values. Never commit API keys or database credentials.

## Android builds

After signing in to Expo and linking the project:

```bash
cd frontend
npx eas-cli build --platform android --profile preview
npx eas-cli build --platform android --profile production
```

The preview profile creates an APK. The production profile creates the AAB for Google Play.

## Readiness

The production health check is `GET /api/healthz`. It returns 200 only when the API can reach MongoDB.
