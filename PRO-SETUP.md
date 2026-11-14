# DevicePulse Pro — guided Google Play setup

Prepared 12 November 2026. **Not activated:** no Play Console or RevenueCat dashboard changes were made. The Android source update is a downloadable release candidate, not a signed AAB or deployed service. The Lovable website remains unchanged.

## Suggested launch pricing — not approved or configured

- Canada: **CA$3.99 / month** and **CA$29.99 / year**.
- Annual savings versus twelve monthly payments: approximately 37%; equivalent to CA$2.50/month, billed yearly.
- This is a launch recommendation, not market research or a revenue forecast. A modest price fits the actual scope: guidance, progress tracking and sharing, not full-device cleaning. Review AI operating costs after launch.
- No free trial or introductory offer is proposed. Approve prices and Canada as the pricing anchor before activating plans. Other countries use Google Play’s localized prices, reviewed by you before activation.

## What subscribers receive

1. Personal AI Coach conversations and saved conversation history (existing provider must be configured and tested).
2. Cleanup journal with recorded dates and measured space changes.
3. Shareable progress reports based on actual readings and history.
4. Family dashboard for voluntarily shared readings; each participating member currently needs Pro. This is **not one subscription covering the whole family**, and remote deletion is unavailable.
5. Weekly storage reset: measured check, individual download review, safe cache cleanup guidance.
6. Battery habits review: Android usage review, cautious background settings, next-day comparison.
7. Monthly privacy tune-up: permission review, updates and DevicePulse session review.

The three routines save user-controlled checkmarks to the account. They never claim an automatic scan or delete personal files. Free storage readings, manual DevicePulse cache cleanup, available battery readings and Android guidance stay free. Duplicate scanning, large-file scanning, scheduled cleanup, RAM boosting and battery-health measurement are **not paid launch promises**.

## 1. Google Play Console

Open **DevicePulse → Monetize with Play → Products → Subscriptions**. Confirm the package is `ca.verolane.devicepulse` and an internal-test build is available. If subscriptions already exist, reuse compatible products instead of creating duplicates: product IDs cannot simply be renamed afterward.

Proposed setup uses **one subscription with two auto-renewing base plans**:

| Setting | Value |
|---|---|
| Subscription product ID | `devicepulse_pro` |
| Subscription name | DevicePulse Pro |
| Monthly base plan ID | `monthly` |
| Monthly billing period | 1 month, auto-renewing |
| Annual base plan ID | `yearly` |
| Annual billing period | 1 year, auto-renewing |
| Benefits | Personal Coach; cleanup journal; progress reports; family sharing; guided care routines |
| Trial / introductory offer | None for launch |

Enter approved pricing, review country availability and Google’s tax-inclusive/localized amounts, then activate both base plans. Do not describe personal-file deletion, scans that do not exist, unlimited AI, or a shared family subscription. Google’s purchase sheet supplies the final localized charge.

Product/base-plan setup reference: https://www.revenuecat.com/docs/getting-started/entitlements/android-products

## 2. RevenueCat

1. Open the existing RevenueCat project and Android app. Verify the Android package matches the Play app.
2. Complete the Google Play service-account setup in RevenueCat’s current guide. Upload the service-account JSON **directly to RevenueCat**, never to chat or the app. Grant only the access listed in the guide. New credentials can take time to become valid.
3. Import both Google Play base plans. RevenueCat may show identifiers with product/base-plan suffixes; use the dashboard’s actual imported identifiers, not guessed strings.
4. Attach **both** imported products to entitlement **`pro`**.
5. In an offering (suggested `default`), map monthly to the **Monthly** package and yearly to the **Annual** package. Set that offering as current. The app filters to monthly/annual packages and reads localized prices from RevenueCat.
6. Verify the existing public `goog_…` SDK key in `frontend/eas.json` belongs to this RevenueCat Android app. Replace it with the actual public Android key if necessary. Do not use a Test Store key for the Play build.
7. Check RevenueCat restore/transfer behavior deliberately. Purchases belong to the app account signed in during checkout. Do not silently transfer a family member’s purchase; explain the selected policy to users and test account switching.

Credential guide: https://www.revenuecat.com/docs/service-credentials/creating-play-service-credentials

## 3. Deploy the Python service before building

Apply the updated `backend/` to the existing service host. Keep the current authentication and MongoDB setup. Configure privately:

```text
ENVIRONMENT=production
REVENUECAT_SECRET_API_KEY=<RevenueCat private API key authorized for subscriber reads>
REVENUECAT_ENTITLEMENT_ID=pro
REVENUECAT_ALLOW_SANDBOX=false
EMERGENT_LLM_KEY=<existing Coach provider credential>
```

Keep all private values only in the service host’s secret settings. The existing AI integration package and model must be available in the service environment; the supplied Python requirements do not establish that, and live Coach inference remains unverified.

For Play license-tester purchases use a **separate test service/database** with `REVENUECAT_ALLOW_SANDBOX=true`. Never enable it on the production service to accommodate testing. Point a test EAS build’s `EXPO_PUBLIC_BACKEND_URL` to that test service; restore the production URL for release.

Every live Pro operation now queries canonical RevenueCat subscriber state for the authenticated user. A stored `is_pro` or client Boolean cannot authorize access. Access requires a current Google Play subscription (including a provider-reported valid grace period). Expiration/refund changes take effect at the next protected operation without waiting for an app restart; the UI refreshes every minute and on foreground. Cancellation retains the paid term. Verification outages fail closed with a recoverable error. This deliberately trades offline availability and request cost for simple current verification; no webhook is required for this version.

API model reference: https://www.revenuecat.com/docs/api-v1/customer-info-model

## 4. Apply the Android source update

Use this updated archive instead of the older real-readings archive; it includes those fixes plus Pro changes. Merge the supplied `frontend/` and `backend/` into the Android repository using your normal development tools. Do not copy dependencies or generated output. No GitHub changes were pushed here.

Subscribers reach the new **DevicePulse Pro** screen from Optimize or Settings. Purchase and restore only show Pro active after the service verifies it. If the store received payment but verification is pending, use **Retry purchase verification**, not another purchase. Restore remains visible when the offering is unavailable.

Before a production upload, verify EAS ownership, public SDK key and service URL, and use a versionCode higher than the last uploaded build. The existing production profile auto-increments the version code; confirm the resulting value in the EAS build record.

```bash
cd frontend
npm ci
npx eas-cli login
npx eas-cli build --platform android --profile production
```

This creates the signed AAB through your Expo account. The Android export checked here is not an AAB.

## 5. Required real-device release checks

- Install the Play internal-track build with a license tester account and the test service.
- Free user can measure storage and use safe manual cache cleanup; direct Pro requests are denied.
- Buy monthly and yearly separately with test accounts: the localized charge and billing period are correct, and Pro opens only after verification.
- Save a routine checkmark, close/reopen the screen and confirm it remains; another account cannot see it.
- Coach gives a real provider response and history reads back. If the provider is missing, the app reports unavailable rather than pretending to personalize.
- Reports use real data and public sharing is deliberate. Family readings are consented and dated; no remote-clean success is promised.
- Restore a valid purchase; test canceled checkout, pending approval, network failure and retry without repurchase.
- Test cancellation, accelerated expiry, refund/revocation and account switching. No old account’s cached Pro unlock remains.
- Test sandbox purchases against production: they must be rejected.
- Confirm privacy/terms URLs work and explain recurring billing, data use and deletion. Account deletion does not cancel Google Play billing; users must cancel in Google Play.
- Run `python -m pytest tests/test_verified_pro.py` after installing `backend/requirements-dev.txt`.

## Verification performed here

- 17 isolated subscription/Pro tests passed with mocked RevenueCat and MongoDB; these are not real purchases.
- Android source type check passed; Expo doctor passed 18/18; Android JavaScript export succeeded.
- Real-reading smoke checks still show unavailable before readings, actual submitted values afterward and retired simulated endpoints returning 410.
- **Not verified:** Play/RevenueCat account configuration, real payment, hosted deployment, native screen rendering, live Coach provider or signed AAB. Older service tests describe retired simulated features and are not a current release acceptance suite.

## Next actions for Jeff

Approve the suggested prices (or choose different amounts), apply the Play and RevenueCat settings above, deploy the updated service, and build/install the internal-test AAB before selling Pro publicly.