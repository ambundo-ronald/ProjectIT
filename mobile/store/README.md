# Play Store submission pack: Techy App

Everything Play Console asks for, ready to copy in. The images are in [`images/`](images/). The app's build steps are in [docs/android-app.md](../../docs/android-app.md).

## App details

| Field | Value |
|---|---|
| App name | Techy App |
| Package | `com.techyapp.field` (permanent once uploaded) |
| Category | Business |
| Tags | Field service, Productivity, Business management |
| Contact email | your support email (shown publicly on the listing) |
| Website | your company website |
| Privacy policy | `https://erp.norwawater.com/techy-privacy` |
| Account deletion page | `https://erp.norwawater.com/techy-delete-account` |
| Price | Free, no ads, no in-app purchases |

### Short description (80 characters at most)

> Field service for your team, contractors and customers. Works offline.

### Full description

> Techy App is the field-service app for companies that install and maintain equipment. It works with your company's own Techy site, so everyone works from the same jobs, machines and records.
>
> **For technicians**
> • Your work orders, checklists and procedures on your phone
> • Readings, photos and the customer's signature on the job
> • Job timer, parts requests and failure codes
> • Check in and out at sites with a photo and your location
> • Works without signal: changes are sent when you are back online
>
> **For managers**
> • Every job, request and machine in one place
> • Dispatch, preventive maintenance and service contracts
> • Reports on jobs, machine health and costs
> • Who is on site right now, staff and contractors
>
> **For contractors**
> • Accept the jobs offered to you and choose your crew
> • Check in at sites, log what you bought, report your work
> • See your pay: waiting, approved, billed and paid
>
> **For customers**
> • Log your plant's daily readings
> • Follow how your plant is running
> • Ask for service and see every visit and report
>
> You need an account from a company that uses Techy. Open the app, type your company's Techy address, and sign in with the email and password your company gave you.

### Release notes (1.1.0)

> • Contractors: jobs, site check-in and pay
> • Links to Techy open in the app
> • Asks to update when a new version is out
> • Delete my account, and the privacy policy, in the app

## Graphics

| Asset | File | Play's rule |
|---|---|---|
| App icon | `../public/icons/icon-512.png` | 512 × 512 PNG |
| Feature graphic | `images/feature-graphic.png` | 1024 × 500 |
| Phone screenshots | `images/phone-01…08-*.png` | 2 to 8, 1080 × 1920 |
| 10-inch tablet screenshots | `images/tablet-01…02-*.png` | optional, 1920 × 1200 |

The screenshots come from the dev site's demo data, so there are no real customers in them. To make them again, run `scratchpad/shots/store.js` against a running dev site.

## App content (Policy → App content)

**Privacy policy:** the URL above.

**App access:** choose *All or some functionality is restricted*. Give the reviewers a demo login, without which they can't get past sign-in:
- Company address: your demo or live site, for example `erp.norwawater.com`.
- Email and password: a technician account made for review, with a demo project and jobs. Switch it off after review.
- Instructions: "Type the company address, tap Continue, then sign in."

**Ads:** No.

**Content rating:** in the questionnaire, the category is *Utility, Productivity, Communication, or Other*. Answer **No** to everything: violence, sexual content, language, drugs, gambling, user-generated content shared publicly, and location shared with other users. Explain that staff see check-ins only inside their own company. The result is *Everyone* / *PEGI 3*.

**Target audience:** 18 and over. Children are not the audience.

**News app:** No. **COVID-19 app:** No. **Government app:** No. **Financial features:** None.

**Data safety:**

| Question | Answer |
|---|---|
| Does the app collect or share user data? | Collects: yes. Shares with third parties: **no** |
| Encrypted in transit? | Yes (https only) |
| Can users ask for their data to be deleted? | Yes: in the app (Account → Delete my account) and at the account deletion page |
| Personal info: name, email, phone | Collected · required · for app functionality and account management |
| Location: precise location | Collected · required for check-in · for app functionality. Only when checking in or out, never in the background |
| Photos | Collected · optional · for app functionality |
| App activity: other user-generated content (jobs, readings, messages) | Collected · required · for app functionality |
| Device or other IDs | Not collected (the device's name only labels the user's own signed-in phones) |
| Is the data processed ephemerally? | No: it is stored on the company's site |

**Sensitive permissions:**
- **Location:** foreground only. The app asks only when someone checks in, after an in-app explanation (prominent disclosure). No declaration form is needed, because there is no background location.
- **Camera:** normal runtime permission, after an in-app explanation.
- **Photos and videos:** the app uses the system photo picker and does not request `READ_MEDIA_IMAGES`, so no declaration is needed.

## Technical checks (done for 1.1.0)

- **Target API 36** (Android 16), **minimum API 24**, as Play requires for new apps and updates.
- **Android App Bundle** (`.aab`), signed with your upload key, using Play App Signing.
- **No native libraries**, so the 16 KB page-size rule is met.
- **Permissions:** internet, camera, and fine and coarse location only. No background location, no storage permissions.
- **Backups off** (`allowBackup=false`): sign-in keys never leave the phone.
- **Cleartext traffic off:** https only.
- **Edge to edge:** content sits clear of the status bar and the gesture bar.
- **Updates:** Play's in-app update screen (`@capawesome/capacitor-app-update`).
- **Links:** App Links verify against `https://erp.norwawater.com/.well-known/assetlinks.json`.

## Releasing

1. **Version.** Raise `versionCode` and `versionName` in `android/app/build.gradle`, and set `nativeVersion` in `package.json` to the same.
2. **Build:** `npm run build:android`, then in `android/` run `./gradlew bundleRelease`. This needs `keystore.properties` (see docs/android-app.md).
3. **Upload.** In Play Console → Testing → *Internal testing*, upload `app/build/outputs/bundle/release/app-release.aab`, add testers, and roll out.
4. **Turn on App Links (once):**
   1. In Play Console → *Setup → App signing*, copy both **SHA-256** fingerprints: the app signing key and the upload key.
   2. On each company site, paste them into **Techy Ops Settings → Android App Fingerprints**, one per line.
   3. Check that `https://<site>/.well-known/assetlinks.json` lists them.
   4. On a phone, go to *Settings → Apps → Techy App → Open by default*. The site should show as verified.
5. **Show "Open in the app" on the website.** Set **Techy Ops Settings → Android App Link** to the Play Store link.
6. **Move up the tracks.** Go from Internal to Closed, then to Production. A new personal developer account must run a closed test with 12 testers for 14 days before Production.
