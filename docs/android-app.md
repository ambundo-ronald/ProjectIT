# Techy App for Android (Play Store)

One app on the Play Store serves every company that runs Techy. It is also the customers' plant app: a customer account signs in and lands on its plant app, as on the web ([customer app](customer-app.md#on-an-android-phone)). Contractors (external technicians) use it too, and land on their own app ([contractors](contractors.md)). On first open, the person types their company's Techy address (for example `ops.yourcompany.com`), then signs in with their usual email and password. It is the same app as the web version, so technicians, managers and customers each see their own apps.

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

## Updates

- **Play updates the app by itself.** Phones with *auto-update apps* on (the default) get new versions within a day or two, usually on Wi-Fi.
- **The app also asks.** Each time it opens, it asks Play whether a newer version exists, and shows a bar: **Update** downloads in the background, then **Restart** installs it.
- **Too old for the site.** The site states the oldest app it works with (`MIN_APP_VERSION` in `projectit/app_links.py`). An app older than that opens Play's full-screen update straight away. An APK installed by hand, which Play can't update, is sent to the Play Store instead.
- **Server changes need no new app.** Changes to the Python side reach everyone as soon as the site is updated. Only screen changes need a new app version.

## Links open the app

- **Android App Links.** Links to `https://erp.norwawater.com/techy-app/…`, in WhatsApp, email or SMS, open straight in the app on the right screen.
  - Android trusts the site once `/.well-known/assetlinks.json` lists the app's signing keys. Paste them in **Techy Ops Settings → Android App Fingerprints**.
  - The host is set in `android/app/build.gradle` (`appLinkHost`).
- **Open in the app.** Every company's website shows a small **Open in the app** bar on Android phones, once **Techy Ops Settings → Android App Link** is set.
  - It opens the installed app on the same screen, or the Play Store if the app isn't installed.
  - It uses `techyapp://open?site=…&path=…`, so it works for any company's site without setup.
- **Sign-in first.** If the phone is signed out, or signed in to another company, the app switches to the link's site, asks the person to sign in, then opens the screen.

## Privacy and account deletion

- **Privacy policy:** `/techy-privacy` on each site. It's also linked from the sign-in screen and the account menus.
- **Deleting an account:**
  - In the app: **Account → Delete my account** (for staff, it's in the menu under their name).
  - On the web: `/techy-delete-account`.
  - Either way, the company's System Managers are told by notification and email.
- **Location and camera:** the first time the app needs either, it says what it is for, before Android asks for the permission.

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

Everything Play Console asks for is in [mobile/store/README.md](../mobile/store/README.md):
- listing texts and images;
- the data safety, content rating and app access answers;
- the release and App Links steps.

## Where things are

| | |
|---|---|
| `mobile/capacitor.config.json` | App ID and name, phone requests through native HTTP |
| `mobile/android/` | The Android project. App icons and splash screen are in `app/src/main/res/` (drawn from `mobile/icon-src/`) |
| `mobile/src/data/native.js` | Company address, sign-in token, signed links, links opening in the browser, Back button, status bar |
| `projectit/device_auth.py` | Sign-in for phones, the device token check, signed links |
| `Techy Device` (DocType) | The signed-in phones |
