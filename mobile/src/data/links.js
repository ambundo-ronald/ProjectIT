import { reactive } from 'vue'
import { api } from './ops'
import { myApps } from './apps'

/** Linkable documents. Messages store links as [[kind:name]]; the composer inserts them. */
export const LINK_KINDS = [
  { kind: 'task', label: 'Tasks', one: 'Task', icon: 'check-square', words: ['task', 'tasks'] },
  { kind: 'work-order', label: 'Work orders', one: 'Work order', icon: 'tool', words: ['wo', 'work order', 'workorder', 'work orders'] },
  { kind: 'project', label: 'Projects', one: 'Project', icon: 'folder', words: ['project', 'projects'] },
  { kind: 'equipment', label: 'Equipment', one: 'Equipment', icon: 'droplet', words: ['equipment', 'machine', 'ro'] },
  { kind: 'asset', label: 'Assets', one: 'Asset', icon: 'box', words: ['asset', 'assets'] },
  { kind: 'request', label: 'Requests', one: 'Request', icon: 'alert-triangle', words: ['request', 'requests'] },
]
export const KIND = Object.fromEntries(LINK_KINDS.map((k) => [k.kind, k]))
export const linkToken = (kind, name) => `[[${kind}:${name}]]`

/** Typed keyword -> kind, e.g. "project" -> project. Longest first so "work order" wins over "work". */
export const KEYWORDS = LINK_KINDS.flatMap((k) => k.words.map((w) => [w, k.kind])).sort((a, b) => b[0].length - a[0].length)

/** 'kind:name' -> { title, detail } once resolved; null when missing or not visible to this user. */
export const linkInfo = reactive({})
let pending = new Set()
let timer = null

/** Queue references for one batched lookup. */
export function resolveLinks(refs) {
  for (const ref of refs) if (!(ref in linkInfo) && !pending.has(ref)) pending.add(ref)
  if (!pending.size || timer) return
  timer = setTimeout(async () => {
    const batch = [...pending]
    pending = new Set()
    timer = null
    try {
      const found = await api('projectit.links.resolve_links', { refs: batch })
      for (const ref of batch) linkInfo[ref] = found[ref] || null
    } catch (e) {
      /* leave unresolved; chips still show the ID */
    }
  }, 30)
}

const cache = new Map()
export async function searchLinks(kind, txt = '') {
  const key = `${kind}|${txt.toLowerCase()}`
  if (!cache.has(key)) {
    cache.set(key, api('projectit.links.search_links', { kind, txt }).then((rows) => {
      for (const r of rows) linkInfo[`${r.kind}:${r.name}`] = { title: r.title, detail: r.detail }
      setTimeout(() => cache.delete(key), 60000)
      return rows
    }).catch((e) => {
      cache.delete(key)
      throw e
    }))
  }
  return cache.get(key)
}

const has = (module) => (myApps.value || []).some((a) => a.module === module)

/** Where a link opens: an in-app route when the user has that app, otherwise the ERPNext Desk form. */
export function linkTarget(kind, name) {
  const desk = (doctype) => ({ href: `/desk/${doctype}/${encodeURIComponent(name)}` })
  switch (kind) {
    case 'work-order':
      return has('Ops') ? { to: { name: 'OpsWorkOrder', params: { name } } } : desk('task')
    case 'asset':
      return has('Ops') ? { to: { name: 'OpsAsset', params: { name } } } : desk('asset')
    case 'equipment':
      return has('Ops') ? { to: { name: 'OpsEquipmentDetail', params: { name } } } : desk('techy-equipment')
    case 'request':
      return has('Ops') ? { to: { name: 'OpsRequests', query: { open: name } } } : desk('issue')
    case 'task':
      if (has('WorkIT')) return { to: { name: 'MyTasks', query: { task: name } } }
      return has('ManageIT') ? { to: { name: 'ManageTasks', query: { task: name } } } : desk('task')
    case 'project':
      return has('ManageIT') ? { to: { name: 'ManageProject', params: { project: name } } } : desk('project')
  }
  return desk(kind)
}
