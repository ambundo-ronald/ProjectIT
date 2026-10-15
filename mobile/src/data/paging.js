import { ref, computed, watch } from 'vue'

// Per-viewer conveniences only: storage can be missing (private windows), so every access is guarded.
function stored(key, fallback) {
  try {
    return localStorage.getItem(key) ?? fallback
  } catch (e) {
    return fallback
  }
}
function store(key, value) {
  try {
    localStorage.setItem(key, value)
  } catch (e) {
    /* storage unavailable */
  }
}

/** A remembered Cards / List choice for one page. */
export function useView(key, fallback = 'cards') {
  const view = ref(['cards', 'list'].includes(stored(`techy_view_${key}`)) ? stored(`techy_view_${key}`) : fallback)
  watch(view, (v) => store(`techy_view_${key}`, v))
  return view
}

/** A remembered page size, shared by every paged list. */
export function usePageLength() {
  const n = Number(stored('techy_page_length', 25))
  const size = ref([25, 50, 100].includes(n) ? n : 25)
  watch(size, (v) => store('techy_page_length', v))
  return size
}

/**
 * Client-side pages over a list the page already holds. Back to page 1 when any of `resetOn` (search,
 * filters) or the page size changes; a refreshed list keeps the current page, or its last page if it shrank.
 */
export function usePaged(rows, resetOn = []) {
  const pageLength = usePageLength()
  const start = ref(0)
  watch([pageLength, ...resetOn], () => (start.value = 0))
  watch(rows, (list) => {
    if (start.value >= list.length) start.value = Math.max(0, Math.floor((list.length - 1) / pageLength.value) * pageLength.value)
  })
  const total = computed(() => rows.value.length)
  const paged = computed(() => rows.value.slice(start.value, start.value + pageLength.value))
  return { start, pageLength, total, paged }
}
