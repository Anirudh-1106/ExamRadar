# Google Play release checklist

Nothing is submitted without the owner's approval.

## Data safety form (draft answers)

| Question | Answer |
|---|---|
| Does the app collect or share user data? | Collects. Does not share. |
| Data types collected | Personal info, optional: date of birth, category, qualifications (only with matching alerts on). App activity: saved exams and progress. Device IDs: push token. |
| Is data encrypted in transit? | Yes |
| Can users request deletion? | Yes, in the app (Settings, Delete all my data) |
| Is collection optional? | Yes. The app works without any of it. |
| Purpose | App functionality (reminders, eligibility), personalisation (matching alerts) |
| Location, contacts, photos, files | Not collected. Photos chosen for the photo check never leave the phone. |

## Government information policy

- [x] Every exam page links to its official source.
- [x] A non-affiliation disclaimer appears on onboarding, on About, at the foot of Home, and on every exam page.
- [ ] Store listing text states the app is independent and names its sources.
- [ ] The developer account name does not imply government affiliation.

## Build and signing

- [ ] Create a release keystore and store it outside the repository (`android/key.properties` is git-ignored).
- [ ] Switch `buildTypes.release.signingConfig` to the release key.
- [ ] Remove `android:usesCleartextTraffic="true"` once the API is on HTTPS.
- [ ] Build an app bundle: `flutter build appbundle --dart-define=API_BASE_URL=https://...`.
- [ ] Target the API level Google Play requires at submission time.
- [ ] Add `google-services.json` if push is enabled.

## Content and quality

- [ ] Native-speaker review of Malayalam strings (legal-review L14).
- [ ] Privacy policy published at a public URL (served at `/privacy` by the API).
- [ ] Screenshots: `docs/screenshots` (regenerate with real data before listing).
- [ ] Test on a low-end Android 7 or 8 phone and a recent phone.
- [ ] Content rating questionnaire: no violence, no user-generated content shared publicly.
- [ ] Ads declaration: no ads.
