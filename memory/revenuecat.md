# RevenueCat — integrated (2026-08-17)
This file is a memory aid for interacting with the user's RevenueCat account via the integration proxy later.

## Identifiers (from /setup response — verbatim)
- rc_project_id: proj6d262295
- apple_app_id: app632094d7b6
- play_app_id: appdaccc8e232
- entitlement_lookup_key: pro
- offering_lookup_key: default
- Packages (package -> product_id, current price):
  - $rc_monthly -> prod0fdaac9c03  ($9.99 / P1M, trial: none)
  - $rc_annual  -> prod86399064b4  ($79.99 / P1Y, trial: P1W / 7-day free trial)
- Dashboard: https://app.revenuecat.com/projects/proj6d262295
- App identifiers: ios.bundleIdentifier = com.emergent.verolanepulse.e73nen ; android.package = ca.verolane.devicepulse (Play package updated 2026-08-18; RC Play app re-provisioned via /setup, SDK keys unchanged)

## Status check
curl -sS -H "$AUTH" "$INTEGRATION_PROXY_URL/internal/revenuecat/projects/070d8d35-bc49-4ca1-adcf-136d3378f31a/status"
(project_state was "connected" at setup; if project_state < project_created, re-fetch the RevenueCat playbook via the integration expert.)

## Later product updates (integration proxy ONLY — NEVER call RevenueCat REST API)
- Change price/duration/trial OR add a package (upsert):
  POST $INTEGRATION_PROXY_URL/internal/revenuecat/projects/070d8d35-bc49-4ca1-adcf-136d3378f31a/products
  body: {"products":[{"package":"$rc_monthly","price":14.99,"currency":"USD","period":"P1M","trial":"P1W","prices":[{"amount_micros":14990000,"currency":"USD"}]}]}
  (amount_micros = price × 1,000,000; omit "trial" for none)
- Remove a package:
  DELETE $INTEGRATION_PROXY_URL/internal/revenuecat/projects/070d8d35-bc49-4ca1-adcf-136d3378f31a/products/%24rc_monthly
- Recover identifiers / repopulate .env: re-run the idempotent /setup call.
- All /internal/revenuecat/* calls need header: Authorization: Bearer <emergent key> (kept out of this file / in env only).

## Going LIVE — store-side steps (USER does these; Emergent cannot)
Needed only for REAL purchases in published builds (Test Store needs none):
1. Upload App Store Connect API key (.p8) and Google Play service-account JSON to the RevenueCat dashboard.
2. Set up payment profiles in App Store Connect and Play Console.
3. Create matching IAP products using the SAME product IDs shown in the RevenueCat dashboard.
4. Make a release build, test via TestFlight / Play internal testing, then submit for review.
All steps are also in the FAQ section of the payments panel.

## Implementation notes (this app)
- SDK init at module scope in app/_layout.tsx (initializeRevenueCat) wrapped in try/catch.
- Wrapped app in QueryClientProvider + SubscriptionProvider (src/lib/revenuecat.tsx).
- Purchases.logIn(user.user_id) / logOut() bound to Emergent Google Auth in src/AuthContext.tsx.
- Paywall (app/paywall.tsx) uses useSubscription(): real packages, no hardcoded prices, confirm modal, Restore button, unavailable + isSubscribed states.
- Pro gating is CLIENT-SIDE ONLY via customerInfo.entitlements.active["pro"]; no backend is_pro fields or webhooks.
