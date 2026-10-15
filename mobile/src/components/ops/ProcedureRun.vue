<template>
  <div>
    <div class="px-5 pb-3 pt-1">
      <div class="flex items-center justify-between gap-3 text-xs">
        <span class="font-medium text-gray-600">{{ answered }} of {{ total }} answered</span>
        <span class="flex items-center gap-3">
          <span v-if="failed" class="inline-flex items-center gap-1 font-semibold text-red-600"><FeatherIcon name="alert-octagon" class="h-3.5 w-3.5" />{{ failed }} failed</span>
          <span v-if="missing" class="font-medium text-amber-700">{{ missing }} required left</span>
          <span v-else-if="total" class="inline-flex items-center gap-1 font-semibold text-green-600"><FeatherIcon name="check-circle" class="h-3.5 w-3.5" />Required steps done</span>
        </span>
      </div>
      <div class="mt-2 flex h-1.5 overflow-hidden rounded-full bg-gray-100" role="progressbar" :aria-valuenow="answered" :aria-valuemax="total" aria-label="Procedure progress">
        <div class="bg-green-500 transition-all" :style="{ width: pct(answered - failed) }" />
        <div class="bg-red-500 transition-all" :style="{ width: pct(failed) }" />
      </div>
    </div>

    <ol class="border-t border-gray-100">
      <template v-for="step in numbered" :key="step.name">
        <li v-if="step.field_type === 'Heading'" class="border-b border-gray-100 bg-gray-50/80 px-5 pb-2 pt-4">
          <h3 class="text-[13px] font-semibold uppercase tracking-wide text-gray-600">{{ step.label }}</h3>
          <p v-if="step.help" class="mt-0.5 text-xs text-gray-500">{{ step.help }}</p>
        </li>
        <li
          v-else
          :id="`step-${step.name}`"
          class="flex gap-3 border-b border-gray-100 px-5 py-4 transition-colors last:border-b-0"
          :class="[step.failed ? 'bg-red-50/60' : '', highlight === step.name ? 'ring-2 ring-inset ring-amber-400' : '']"
        >
          <span class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold" :class="badge(step)">
            <FeatherIcon v-if="step.failed" name="x" class="h-3.5 w-3.5" />
            <FeatherIcon v-else-if="step.value" name="check" class="h-3.5 w-3.5" />
            <template v-else>{{ step.n }}</template>
          </span>
          <div class="min-w-0 flex-1">
            <p class="text-[15px] font-medium leading-snug text-gray-900">
              {{ step.label }}<span v-if="step.required" class="ml-0.5 text-red-500" title="Required">*</span>
            </p>
            <p v-if="step.help" class="mt-0.5 whitespace-pre-line text-[13px] text-gray-500">{{ step.help }}</p>

            <div class="mt-2.5">
              <!-- Checkbox -->
              <label v-if="step.field_type === 'Checkbox'" class="inline-flex min-h-[2.5rem] cursor-pointer items-center gap-2.5 rounded-lg border px-3 text-sm font-medium transition-colors" :class="[step.value ? 'border-green-300 bg-green-50 text-green-800' : 'border-gray-300 bg-white text-gray-700', locked ? 'cursor-default' : 'hover:border-gray-400']">
                <input type="checkbox" class="h-5 w-5 rounded-md border-gray-300 text-green-600 focus:ring-green-500" :checked="!!step.value" :disabled="locked" @change="emitAnswer(step, $event.target.checked ? '1' : '')" />
                {{ step.value ? 'Done' : 'Mark done' }}
              </label>

              <!-- Pass/Fail, Yes/No/N/A, Multiple choice -->
              <div v-else-if="choices(step)" class="flex flex-wrap gap-2" role="radiogroup" :aria-label="step.label">
                <button
                  v-for="c in choices(step)"
                  :key="c"
                  type="button"
                  role="radio"
                  :aria-checked="step.value === c"
                  :disabled="locked"
                  class="inline-flex h-10 min-w-[4.5rem] items-center justify-center gap-1.5 rounded-lg border px-3.5 text-sm font-semibold transition-colors disabled:cursor-default"
                  :class="choiceTone(step, c)"
                  @click="emitAnswer(step, step.value === c ? '' : c)"
                >
                  <FeatherIcon v-if="c === 'Pass'" name="check" class="h-4 w-4" />
                  <FeatherIcon v-else-if="c === 'Fail'" name="x" class="h-4 w-4" />{{ c }}
                </button>
              </div>

              <!-- Number -->
              <div v-else-if="step.field_type === 'Number'" class="flex flex-wrap items-center gap-2">
                <div class="flex items-center overflow-hidden rounded-lg border bg-white focus-within:ring-2 focus-within:ring-brand-500/20" :class="step.failed ? 'border-red-400' : 'border-gray-300 focus-within:border-brand-500'">
                  <input type="text" inputmode="decimal" class="h-10 w-28 border-0 bg-transparent px-3 text-[15px] font-semibold tabular-nums focus:ring-0" :value="step.value" :disabled="locked" :aria-label="step.label" placeholder="0" @change="emitAnswer(step, $event.target.value.replace(',', '.'))" @keydown.enter.prevent="$event.target.blur()" />
                  <span v-if="step.unit" class="pr-3 text-sm text-gray-500">{{ step.unit }}</span>
                </div>
                <span v-if="rangeText(step)" class="text-xs" :class="step.failed ? 'font-semibold text-red-600' : 'text-gray-500'">{{ step.failed ? 'Out of range' : 'Expected' }} {{ rangeText(step) }}</span>
                <span v-if="step.meter" class="inline-flex items-center gap-1 text-xs" :class="step.meter_reading ? 'text-green-700' : 'text-gray-500'"><FeatherIcon name="activity" class="h-3.5 w-3.5" />{{ step.meter_reading ? `Saved to ${step.meter}` : `Saves to ${step.meter}` }}</span>
              </div>

              <!-- Text -->
              <textarea v-else-if="step.field_type === 'Text'" class="input min-h-[4.5rem]" rows="2" maxlength="2000" :value="step.value" :disabled="locked" :aria-label="step.label" placeholder="Type your answer" @change="emitAnswer(step, $event.target.value)" />

              <!-- Photo / Signature -->
              <div v-else-if="step.field_type === 'Photo' || step.field_type === 'Signature'" class="flex flex-wrap items-center gap-3">
                <a v-if="step.value && !preview" :href="step.value" target="_blank" rel="noopener" class="block overflow-hidden rounded-lg border border-gray-200 bg-white" :class="step.field_type === 'Signature' ? 'h-16 w-40' : 'h-20 w-20'">
                  <img :src="step.value" :alt="step.field_type === 'Signature' ? 'Signature' : step.label" class="h-full w-full" :class="step.field_type === 'Signature' ? 'object-contain' : 'object-cover'" />
                </a>
                <span v-else-if="step.value" class="inline-flex h-10 items-center gap-1.5 rounded-lg bg-green-50 px-3 text-sm font-medium text-green-800"><FeatherIcon name="check" class="h-4 w-4" />{{ step.field_type === 'Signature' ? 'Signed' : 'Photo added' }}</span>
                <template v-if="!locked">
                  <PhotoButtons v-if="step.field_type === 'Photo'" :camera-label="step.value ? 'Retake' : 'Take photo'" :busy="!!saving[step.name]" @photos="(list) => photo(step, list)" @error="(e) => emit('error', e)" />
                  <button v-else type="button" class="btn btn-secondary" @click="signing = step"><FeatherIcon name="edit-3" class="h-4 w-4" />{{ step.value ? 'Sign again' : 'Sign' }}</button>
                  <button v-if="step.value" type="button" class="btn btn-ghost btn-sm text-gray-500" @click="emitAnswer(step, '')">Clear</button>
                </template>
              </div>
            </div>

            <p v-if="step.failed && step.follow_up_work_order" class="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-red-700">
              <FeatherIcon name="corner-down-right" class="h-3.5 w-3.5" />Follow-up raised <LinkChip kind="work-order" :name="step.follow_up_work_order" />
            </p>
            <p v-else-if="step.failed && step.create_follow_up && preview" class="mt-2 text-xs text-red-700">A follow-up work order will be raised.</p>
            <p v-if="step.answered_by && step.value" class="mt-1.5 text-[11px] text-gray-400">{{ step.answered_by }} · {{ fromNow(step.answered_on) }}</p>
          </div>
          <FeatherIcon v-if="saving[step.name] && step.field_type !== 'Photo'" name="loader" class="mt-1 h-4 w-4 shrink-0 animate-spin text-gray-400" aria-label="Saving" />
        </li>
      </template>
    </ol>
    <SignaturePad :model-value="!!signing" :label="signing?.label" @update:model-value="(v) => !v && (signing = null)" @signed="(png) => emit('answer', signing, { value: '1', photo: png })" />
  </div>
</template>
<script setup>
import { ref, computed } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import LinkChip from './LinkChip.vue'
import SignaturePad from './SignaturePad.vue'
import { fromNow } from '@/data/ops'
import PhotoButtons from './PhotoButtons.vue'
import { rangeText } from '@/data/procedures'

const props = defineProps({
  steps: { type: Array, required: true },
  locked: Boolean, // read-only (closed work order or no write access)
  preview: Boolean, // builder preview: answers stay local
  saving: { type: Object, default: () => ({}) }, // step name -> true while saving
  highlight: String, // step name to draw attention to
})
const emit = defineEmits(['answer', 'error'])
const signing = ref(null)

const numbered = computed(() => {
  let n = 0
  return props.steps.map((s) => ({ ...s, n: s.field_type === 'Heading' ? null : ++n }))
})
const answerable = computed(() => props.steps.filter((s) => s.field_type !== 'Heading'))
const total = computed(() => answerable.value.length)
const answered = computed(() => answerable.value.filter((s) => s.value).length)
const failed = computed(() => answerable.value.filter((s) => s.failed).length)
const missing = computed(() => answerable.value.filter((s) => s.required && !s.value).length)
const pct = (n) => `${total.value ? (n / total.value) * 100 : 0}%`

const CHOICES = { 'Pass/Fail': ['Pass', 'Fail'], 'Yes/No/N/A': ['Yes', 'No', 'N/A'] }
const choices = (step) => CHOICES[step.field_type] || (step.field_type === 'Multiple Choice' ? (step.options || '').split('\n').filter(Boolean) : null)
function choiceTone(step, c) {
  if (step.value !== c) return 'border-gray-300 bg-white text-gray-700 enabled:hover:border-gray-400 enabled:hover:bg-gray-50'
  if (c === 'Pass' || c === 'Yes') return 'border-green-500 bg-green-500 text-white'
  if (c === 'Fail') return 'border-red-500 bg-red-500 text-white'
  if (c === 'No') return 'border-amber-500 bg-amber-500 text-white'
  return 'border-brand-600 bg-brand-600 text-white'
}
function badge(step) {
  if (step.failed) return 'bg-red-500 text-white'
  if (step.value) return 'bg-green-500 text-white'
  return 'bg-gray-100 text-gray-500'
}

const emitAnswer = (step, value) => emit('answer', step, { value })
function photo(step, list) {
  emit('answer', step, { value: '1', photo: list[0].content })
  URL.revokeObjectURL(list[0].preview)
}
</script>
