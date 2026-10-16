# App icon sources

The Techy App icon (the white T with the teal arrow on navy), drawn on a 512 grid. The PNGs in `public/icons/` are rendered from these:

| Source | PNG | Used for |
|---|---|---|
| `any.svg` | `icon-192.png`, `icon-512.png`, `favicon-32.png` | Android app list and install prompts, desktop, browser tab |
| `maskable.svg` | `maskable-192.png`, `maskable-512.png` | Android home screen. It fills the square because Android crops it to a circle or squircle; the marks stay inside the middle 80%. |
| `apple.svg` | `apple-touch-icon.png` (180) | iPhone and iPad home screen. A full square, because iOS rounds the corners and shows transparency as black. |
| `badge.svg` | `badge-96.png` | Android notification badge. It's white on transparent, because only the shape is shown. |

`public/techy-app.svg` is the same icon, used for the browser tab and in the app. After editing a source, render it to PNG at the sizes above with transparency kept, for example by screenshotting it at that size in a browser.
