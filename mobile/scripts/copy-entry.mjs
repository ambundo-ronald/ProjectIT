import { mkdir, copyFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const www = new URL('../../projectit/www/', import.meta.url)
await mkdir(www, { recursive: true })
const entry = new URL('../../projectit/public/projectit/index.html', import.meta.url)
for (const name of ['techy-app.html', 'projectit.html']) {
  await copyFile(entry, new URL(name, www))
}
console.log(`Techy App entry points copied to ${fileURLToPath(www)}`)
