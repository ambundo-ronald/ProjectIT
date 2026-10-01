import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'

export function benchPort(startDirectory) {
  let directory = path.resolve(startDirectory)
  while (true) {
    const config = path.join(directory, 'sites', 'common_site_config.json')
    if (existsSync(config) && existsSync(path.join(directory, 'apps'))) {
      return JSON.parse(readFileSync(config, 'utf8')).webserver_port || 8000
    }
    const parent = path.dirname(directory)
    if (parent === directory) return 8000
    directory = parent
  }
}

export function frappeProxy(startDirectory) {
  return {
    '^/(api|assets|files|private|login|desk|app)(/|$)': {
      target: process.env.FRAPPE_URL || `http://127.0.0.1:${benchPort(startDirectory)}`,
      // Keep the incoming site hostname for Frappe's multi-site resolution.
      changeOrigin: false,
      ws: true,
    },
  }
}
