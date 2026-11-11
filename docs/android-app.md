# Techy App for Android (Play Store)

One app on the Play Store serves every company that runs Techy. On first open, the person types their company's Techy address (for example `ops.yourcompany.com`), then signs in with their usual email and password. It is the same app as the web version, so technicians, managers and customers each see their own apps.

## How it differs from the web app

- **The app is on the phone.** It opens with no signal at all, and the day's work is already saved on the phone. See [Offline mode](ops.md#offline-mode).
- **Signing in.**
  - Each phone gets its own sign-in, which stays signed in until someone signs out.
  - Every signed-in phone appears in Desk under **Techy Device**. To sign one out straight away (a lost phone, someone leaving), tick **Signed Out**.
  - Disabling a user signs out all their phones.
- **Photos and PDFs.** Service reports, monthly reports and Excel exports open in the phone's browser through a link that works for one day. Links to Desk open there too.
- **Not in the phone app yet:**
  - live updates (chat messages and presence refresh when you open a screen);
  - notifications on the phone (they need Firebase, which is the next step);
  - two-factor sign-in (people who use it get a clear message).

## What a company needs

- Techy (this app) on its ERPNext site, reachable over **https** from the internet.
- Nothing else: no CORS settings, because the app makes its own requests.
- A manager can review offline check-ins in **Employee Checkin** (device *Techy App (offline)*), and can turn offline check-in off in **Work Time Settings**.

## Building

You need Node 24 and Android Studio (it brings Java and the Android SDK).

```bash
cd mobile
npm run build:android           # web app for the phone (dist-native), copied into android/
cd android
./gradlew assembleDebug          # app/build/outputs/apk/debug/app-debug.apk, to install on a test phone
./gradlew bundleRelease          # app/build/outputs/bundle/release/app-release.aab, for the Play Store
```

On Windows, set these first in Git Bash:
- `JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"`
- `ANDROID_HOME="$LOCALAPPDATA/Android/Sdk"`

To try it on a phone:
1. Turn on **Developer options → USB debugging**.
2. Plug the phone in.
3. Run `adb install -r app/build/outputs/apk/debug/app-debug.apk`.

You can also open `mobile/android` in Android Studio and press Run.

### Signing for the Play Store

The Play Store keeps the real signing key (Play App Signing). You sign each upload with your own **upload key**:

1. Make the key once and keep it safe, outside git. If it is lost, Google can reset it, but that takes days.
   ```bash
   keytool -genkeypair -v -keystore techy-upload.jks -alias techy-upload -keyalg RSA -keysize 2048 -validity 10000
   ```
2. Create `mobile/android/keystore.properties`, which git ignores:
   ```properties
   storeFile=../techy-upload.jks
   storePassword=…
   keyAlias=techy-upload
   keyPassword=…
   ```
3. Run `./gradlew bundleRelease`. It now produces a signed `app-release.aab`.

### Each new version

1. Raise `versionCode` (by 1) and `versionName` in `android/app/build.gradle`.
2. Set `nativeVersion` in `mobile/package.json` to the same version.
3. Run `npm run build:android`, then `./gradlew bundleRelease`.
4. Upload the `.aab` in Play Console.

Changes to the server side (the Python app) reach everyone as soon as the site is updated. Only screen changes need a new app version.

## Publishing on the Play Store

1. **Developer account.** Create a [Play Console](https://play.google.com/console) account in the company's name: a one-off US$25, plus identity checks.
   - A new *personal* account must run a closed test with at least 12 testers for 14 days before it can publish.
   - An *organisation* account skips this, but needs a D-U-N-S number.
2. **The app's ID**, `com.techyapp.field`, is permanent once uploaded. To change it, edit `appId` in `mobile/capacitor.config.json` and `applicationId`/`namespace` in `android/app/build.gradle` *before* the first upload, then run `npx cap sync android`.
3. **Store listing:**
   - name: Techy App;
   - short description;
   - the 512×512 icon (`mobile/public/icons/icon-512.png`);
   - a 1024×500 feature graphic;
   - at least two phone screenshots.
4. **Privacy policy URL.** It is required because the app uses the camera and location.
5. **Data safety form.** What the app collects, all of it sent only to the company's own Techy site:

   | Data | Why | Optional? |
   |---|---|---|
   | Name, email | Sign-in, showing who did what | No |
   | Precise location | Recorded with each check-in and check-out | Required for check-in |
   | Photos | Job, check-in and site photos the person takes | Yes |
   | App activity (jobs, readings, messages) | The work itself | No |

   - It is encrypted in transit (https).
   - Users can ask their company to delete their account.
   - Nothing is shared with third parties or used for ads.
6. **App access.** Reviewers can't sign in without an account, so give them a demo site address and a demo login, for example a technician account on a demo site.
7. **Release.** Start with *Internal testing*, which reaches up to 100 testers by email within minutes. Then *Closed testing*, then *Production*.

## Where things are

| | |
|---|---|
| `mobile/capacitor.config.json` | App ID and name, phone requests through native HTTP |
| `mobile/android/` | The Android project. App icons and splash screen are in `app/src/main/res/` (drawn from `mobile/icon-src/`) |
| `mobile/src/data/native.js` | Company address, sign-in token, signed links, links opening in the browser, Back button, status bar |
| `projectit/device_auth.py` | Sign-in for phones, the device token check, signed links |
| `Techy Device` (DocType) | The signed-in phones |
