import { ref } from 'vue'
import { api } from './ops'

/** Step types a procedure can ask for, in builder order. */
export const STEP_TYPES = [
  { type: 'Checkbox', label: 'Checkbox', icon: 'check-square', hint: 'Tick when done' },
  { type: 'Pass/Fail', label: 'Pass / Fail', icon: 'shield', hint: 'Inspection result; Fail can raise a follow-up' },
  { type: 'Yes/No/N/A', label: 'Yes / No / N/A', icon: 'help-circle', hint: 'A quick question' },
  { type: 'Number', label: 'Number', icon: 'hash', hint: 'A reading, with an optional safe range' },
  { type: 'Text', label: 'Text', icon: 'align-left', hint: 'Notes or a free answer' },
  { type: 'Multiple Choice', label: 'Multiple choice', icon: 'list', hint: 'Pick one of your choices' },
  { type: 'Photo', label: 'Photo', icon: 'camera', hint: 'Evidence photo from the camera' },
  { type: 'Signature', label: 'Signature', icon: 'edit-3', hint: 'Sign off on screen' },
  { type: 'Heading', label: 'Section heading', icon: 'type', hint: 'Groups the steps below it' },
]
export const STEP_TYPE = Object.fromEntries(STEP_TYPES.map((t) => [t.type, t]))
export const CATEGORIES = ['Corrective', 'Preventive', 'Inspection', 'Safety', 'Other']

/** "4–6 bar", "≥ 4 bar", "≤ 6 bar" or "" for a Number step. */
export function rangeText(step) {
  const unit = step.unit ? ` ${step.unit}` : ''
  const lo = step.min_value
  const hi = step.max_value
  if (lo !== '' && lo != null && hi !== '' && hi != null) return `${lo}–${hi}${unit}`
  if (lo !== '' && lo != null) return `≥ ${lo}${unit}`
  if (hi !== '' && hi != null) return `≤ ${hi}${unit}`
  return ''
}

/** Active procedures for pickers; loaded once per page view. */
export const procedureList = ref(null)
let loading = null
export function loadProcedures(force = false) {
  if (force) loading = null
  loading ||= api('projectit.procedures.list_procedures')
    .then((r) => (procedureList.value = r.procedures))
    .catch((e) => {
      loading = null
      procedureList.value = []
      throw e
    })
  return loading
}

const step = (field_type, label, extra = {}) => ({ field_type, label, help: '', required: 0, options: '', min_value: '', max_value: '', unit: '', create_follow_up: 0, ...extra })

/** Starting points for the builder; managers edit them before saving. */
export const STARTERS = [
  {
    key: 'pump',
    title: 'Pump monthly inspection',
    category: 'Preventive',
    description: 'Monthly condition check for centrifugal pumps.',
    steps: [
      step('Heading', 'Safety'),
      step('Checkbox', 'Isolate the pump and apply lock-out / tag-out', { required: 1, help: 'Verify zero energy before touching the pump.' }),
      step('Heading', 'Readings'),
      step('Number', 'Discharge pressure', { required: 1, min_value: '4', max_value: '6', unit: 'bar', create_follow_up: 1 }),
      step('Number', 'Motor temperature', { required: 1, max_value: '80', unit: '°C', create_follow_up: 1 }),
      step('Pass/Fail', 'Mechanical seal shows no leakage', { required: 1, create_follow_up: 1 }),
      step('Yes/No/N/A', 'Unusual noise or vibration?'),
      step('Heading', 'Finish'),
      step('Photo', 'Photo of the pump after service', { required: 1 }),
      step('Text', 'Notes for the next technician'),
      step('Signature', 'Technician sign-off', { required: 1 }),
    ],
  },
  {
    key: 'loto',
    title: 'Electrical isolation (LOTO)',
    category: 'Safety',
    description: 'Lock-out / tag-out before electrical work.',
    steps: [
      step('Checkbox', 'Notify affected staff of the shutdown', { required: 1 }),
      step('Checkbox', 'Switch off and isolate at the main breaker', { required: 1 }),
      step('Checkbox', 'Apply personal lock and danger tag', { required: 1 }),
      step('Photo', 'Photo of lock and tag in place', { required: 1 }),
      step('Pass/Fail', 'Voltage tester confirms zero energy', { required: 1, create_follow_up: 1 }),
      step('Signature', 'Authorised person sign-off', { required: 1 }),
    ],
  },
  {
    key: 'extinguisher',
    title: 'Fire extinguisher monthly check',
    category: 'Inspection',
    description: 'Monthly visual inspection.',
    steps: [
      step('Pass/Fail', 'Pressure gauge in the green zone', { required: 1, create_follow_up: 1 }),
      step('Yes/No/N/A', 'Safety pin and tamper seal intact', { required: 1 }),
      step('Multiple Choice', 'Access to the extinguisher', { required: 1, options: 'Clear\nPartly blocked\nBlocked' }),
      step('Signature', 'Inspector sign-off', { required: 1 }),
    ],
  },
]
