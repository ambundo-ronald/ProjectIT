<template>
  <section class="mx-auto max-w-6xl space-y-5 p-4 md:p-8">
    <PageHeader title="Reports" subtitle="How the maintenance work is going and whether service contracts pay.">
      <button class="btn btn-secondary" @click="openCodes"><FeatherIcon name="tag" class="h-4 w-4" /><span class="hidden sm:inline">Failure codes</span></button>
    </PageHeader>
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="segmented" role="group" aria-label="Period">
        <button v-for="p in PERIODS" :key="p.days" :aria-pressed="days === p.days" :disabled="busy" @click="days = p.days; load()">{{ p.label }}</button>
      </div>
      <p v-if="r" class="text-xs text-gray-500">{{ formatDate(r.start) }} – {{ formatDate(r.end) }}</p>
    </div>
    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="!r && busy" class="grid grid-cols-2 gap-3 md:grid-cols-4"><div v-for="i in 8" :key="i" class="h-24 animate-pulse rounded-xl bg-gray-200/70" /></div>

    <template v-if="r">
      <div class="grid grid-cols-2 gap-3 md:grid-cols-4" :class="busy && 'opacity-60'">
        <div v-for="t in tiles" :key="t.label" class="card p-4">
          <p class="text-xs font-medium text-gray-500">{{ t.label }}</p>
          <p class="mt-1 text-[26px] font-semibold leading-tight tabular-nums" :class="t.tone">{{ t.value }}</p>
          <p class="mt-0.5 text-xs" :class="t.subTone || 'text-gray-500'">{{ t.sub }}</p>
        </div>
      </div>

      <div class="card overflow-hidden">
        <div class="card-header flex-wrap gap-2">
          <h2 class="card-title">Jobs opened and completed</h2>
          <span class="flex items-center gap-3 text-xs text-gray-500">
            <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-sm bg-brand-200" />Opened</span>
            <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-sm bg-brand-600" />Completed</span>
          </span>
        </div>
        <div class="flex h-48 items-end gap-1 px-4 pb-2 pt-5 sm:gap-2 md:px-5" role="img" :aria-label="chartLabel">
          <div v-for="c in r.chart" :key="c.label" class="flex h-full min-w-0 flex-1 flex-col justify-end">
            <div class="flex flex-1 items-end justify-center gap-0.5">
              <div class="w-1/2 max-w-[18px] rounded-t bg-brand-200" :style="{ height: bar(c.created) }" :title="`${c.label}: ${c.created} opened`" />
              <div class="w-1/2 max-w-[18px] rounded-t bg-brand-600" :style="{ height: bar(c.completed) }" :title="`${c.label}: ${c.completed} completed`" />
            </div>
            <p class="mt-1.5 truncate text-center text-[10px] text-gray-500">{{ c.label }}</p>
          </div>
        </div>
      </div>

      <div class="grid gap-5 md:grid-cols-2">
        <div class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Preventive maintenance</h2><span class="text-xs text-gray-500">Due in this period</span></div>
          <div class="space-y-4 p-5">
            <div v-if="pmTotal" class="flex h-3 overflow-hidden rounded-full bg-gray-100">
              <div v-for="s in pmParts" :key="s.label" :class="s.bar" :style="{ width: `${(100 * s.value) / pmTotal}%` }" />
            </div>
            <dl class="grid grid-cols-4 gap-2 text-center">
              <div v-for="s in pmParts" :key="s.label"><dd class="text-lg font-semibold tabular-nums" :class="s.text">{{ s.value }}</dd><dt class="text-xs text-gray-500">{{ s.label }}</dt></div>
            </dl>
            <ul v-if="r.pm.late_jobs.length" class="divide-y divide-gray-100 border-t border-gray-100 text-sm">
              <li v-for="j in r.pm.late_jobs" :key="j.name" class="flex items-center justify-between gap-3 py-2">
                <router-link :to="{ name: 'OpsWorkOrder', params: { name: j.name } }" class="min-w-0 truncate hover:text-brand-700">{{ j.subject }}</router-link>
                <span class="shrink-0 text-xs" :class="j.state === 'Missed' ? 'font-semibold text-red-600' : 'text-amber-700'">{{ j.state }} · due {{ formatDate(j.due) }}</span>
              </li>
            </ul>
            <p v-else-if="!pmTotal" class="text-sm text-gray-500">No preventive jobs were due in this period.</p>
          </div>
        </div>

        <div class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Requests</h2><router-link :to="{ name: 'OpsRequests' }" class="text-xs font-medium text-brand-600 hover:underline">Open requests</router-link></div>
          <dl class="grid grid-cols-2 gap-3 p-5 sm:grid-cols-4">
            <div v-for="s in requestStats" :key="s.label" class="rounded-lg bg-gray-50 px-3 py-2.5"><dd class="text-lg font-semibold tabular-nums">{{ s.value }}</dd><dt class="text-xs text-gray-500">{{ s.label }}</dt></div>
          </dl>
          <div class="border-t border-gray-100 px-5 py-4">
            <h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">By type of job</h3>
            <table class="w-full text-sm">
              <thead class="text-left text-xs text-gray-500"><tr><th class="py-1 font-medium">Type</th><th class="py-1 text-right font-medium">Opened</th><th class="py-1 text-right font-medium">Done</th><th class="py-1 text-right font-medium">Avg time</th></tr></thead>
              <tbody class="divide-y divide-gray-100">
                <tr v-for="c in r.categories" :key="c.category"><td class="py-1.5">{{ c.category }}</td><td class="py-1.5 text-right tabular-nums">{{ c.created }}</td><td class="py-1.5 text-right tabular-nums">{{ c.completed }}</td><td class="py-1.5 text-right tabular-nums text-gray-600">{{ duration(c.avg_hours) }}</td></tr>
                <tr v-if="!r.categories.length"><td colspan="4" class="py-2 text-gray-500">No jobs in this period.</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="card overflow-hidden">
        <div class="card-header flex-wrap gap-2"><h2 class="card-title">Technician scorecard</h2><span class="text-xs text-gray-500">Work completed in the period and how well it was done</span></div>
        <div v-if="best" class="flex items-center gap-3 border-b border-gray-100 bg-green-50/60 px-5 py-3 text-sm">
          <UserAvatar :name="best.full_name" :image="best.image" size="sm" />
          <p class="min-w-0"><b>{{ best.full_name }}</b> has the best score this period: <b class="tabular-nums">{{ best.score }}</b> from {{ best.completed }} job{{ best.completed === 1 ? '' : 's' }}.</p>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full min-w-[56rem] text-sm">
            <thead class="border-b border-gray-100 text-left text-xs text-gray-500">
              <tr>
                <th class="px-5 py-2 font-medium">Person</th>
                <th class="px-3 py-2 text-center font-medium">Score</th>
                <th class="px-3 py-2 text-right font-medium">Completed</th>
                <th class="px-3 py-2 text-right font-medium" title="Finished by the due date">On time</th>
                <th class="px-3 py-2 text-right font-medium" :title="`Repairs where the machine needed no other repair within ${r.scoring.repeat_days} days`">Fixed first time</th>
                <th class="px-3 py-2 text-right font-medium" title="Jobs that went back to work after review or completion">Sent back</th>
                <th class="px-3 py-2 text-right font-medium" title="Repairs with a problem and a cause code">Coded</th>
                <th class="px-3 py-2 text-right font-medium">Avg time to finish</th>
                <th class="px-3 py-2 text-right font-medium" title="Hours logged per completed job">Hours / job</th>
                <th class="px-5 py-2 text-right font-medium">Open (overdue)</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <template v-for="t in r.technicians" :key="t.user">
                <tr class="cursor-pointer hover:bg-gray-50" :aria-expanded="open === t.user" @click="open = open === t.user ? '' : t.user">
                  <td class="px-5 py-2.5">
                    <button class="flex items-center gap-2.5 text-left" :aria-label="`${t.full_name}: show the jobs behind the score`" @click.stop="open = open === t.user ? '' : t.user">
                      <UserAvatar :name="t.full_name" :image="t.image" size="sm" /><span class="truncate font-medium">{{ t.full_name }}</span>
                      <FeatherIcon v-if="t.issues.length" :name="open === t.user ? 'chevron-up' : 'chevron-down'" class="h-3.5 w-3.5 text-gray-400" />
                    </button>
                  </td>
                  <td class="px-3 py-2.5 text-center">
                    <span v-if="t.score !== null" class="inline-block min-w-[2.5rem] rounded-md px-1.5 py-0.5 text-sm font-bold tabular-nums" :class="scoreTone(t.score)">{{ t.score }}</span>
                    <span v-else class="text-xs text-gray-400" :title="`Scored after ${r.scoring.min_jobs} completed jobs`">–</span>
                  </td>
                  <td class="px-3 py-2.5 text-right tabular-nums">{{ t.completed }}</td>
                  <td class="px-3 py-2.5 text-right"><Rate :value="t.on_time_rate" :part="t.on_time" :whole="t.due" /></td>
                  <td class="px-3 py-2.5 text-right"><Rate :value="t.first_fix_rate" :part="t.first_fix" :whole="t.fixes" /></td>
                  <td class="px-3 py-2.5 text-right tabular-nums" :class="t.reopened ? 'font-semibold text-amber-700' : 'text-gray-500'">{{ t.completed ? t.reopened : '–' }}</td>
                  <td class="px-3 py-2.5 text-right"><Rate :value="t.coded_rate" :part="t.coded" :whole="t.repairs" /></td>
                  <td class="px-3 py-2.5 text-right tabular-nums text-gray-600">{{ duration(t.avg_hours) }}</td>
                  <td class="px-3 py-2.5 text-right tabular-nums text-gray-600">{{ t.hours_per_job ?? '–' }}</td>
                  <td class="px-5 py-2.5 text-right tabular-nums">{{ t.open }}<span v-if="t.overdue" class="ml-1 font-semibold text-red-600">({{ t.overdue }})</span></td>
                </tr>
                <tr v-if="open === t.user">
                  <td colspan="10" class="bg-gray-50 px-5 py-3">
                    <p v-if="!t.issues.length" class="text-sm text-gray-600">Nothing counted against {{ t.full_name }} in this period.</p>
                    <template v-else>
                      <p class="section-label mb-2">Jobs that lowered the score</p>
                      <ul class="space-y-1.5">
                        <li v-for="i in t.issues" :key="`${i.kind}-${i.name}`" class="flex flex-wrap items-baseline gap-x-2 text-sm">
                          <span class="w-28 shrink-0 rounded px-1.5 text-center text-[11px] font-semibold" :class="ISSUES[i.kind].tone">{{ ISSUES[i.kind].label }}</span>
                          <router-link :to="{ name: 'OpsWorkOrder', params: { name: i.name } }" class="min-w-0 truncate font-medium hover:text-brand-700">{{ i.subject }}</router-link>
                          <span class="text-xs text-gray-500">{{ i.detail }}<template v-if="i.other"> · <router-link :to="{ name: 'OpsWorkOrder', params: { name: i.other } }" class="text-brand-600 hover:underline">see the next repair</router-link></template></span>
                        </li>
                      </ul>
                    </template>
                  </td>
                </tr>
              </template>
              <tr v-if="!r.technicians.length"><td colspan="10" class="px-5 py-3 text-gray-500">No assigned jobs in this period.</td></tr>
            </tbody>
          </table>
        </div>
        <p class="border-t border-gray-100 px-5 py-3 text-xs text-gray-500">
          The score is out of 100: on time counts {{ r.scoring.weights.on_time }}, fixed first time {{ r.scoring.weights.first_fix }} (no other repair on the same machine within {{ r.scoring.repeat_days }} days), not sent back {{ r.scoring.weights.no_rework }} and coded repairs {{ r.scoring.weights.coded }}. Only the measures that apply to someone's jobs count. People with fewer than {{ r.scoring.min_jobs }} completed jobs in the period are not scored. Click a person to see the jobs behind their score.
        </p>
      </div>

      <div class="grid gap-5 lg:grid-cols-2">
        <div class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Downtime</h2><span class="text-xs text-gray-500">Machines marked down on jobs</span></div>
          <div class="grid grid-cols-3 divide-x divide-gray-100 border-b border-gray-100 text-center">
            <div class="p-3"><p class="text-lg font-semibold tabular-nums">{{ duration(r.downtime.hours) }}</p><p class="text-xs text-gray-500">Total down</p></div>
            <div class="p-3"><p class="text-lg font-semibold tabular-nums">{{ r.downtime.stops }}</p><p class="text-xs text-gray-500">Stoppages</p></div>
            <div class="p-3"><p class="text-lg font-semibold tabular-nums">{{ duration(r.downtime.mttr) }}</p><p class="text-xs text-gray-500">Avg time to repair</p></div>
          </div>
          <ul class="divide-y divide-gray-100">
            <li v-for="m in r.downtime.machines" :key="m.name">
              <router-link :to="m.kind === 'equipment' ? { name: 'OpsEquipmentDetail', params: { name: m.name } } : { name: 'OpsAsset', params: { name: m.name } }" class="flex items-center gap-3 px-5 py-3 hover:bg-gray-50">
                <span class="min-w-0 flex-1"><span class="block truncate font-medium">{{ m.label }}<span v-if="m.down_now" class="ml-2 rounded bg-red-50 px-1.5 text-[11px] font-semibold text-red-700">Down now</span></span><span class="block truncate text-xs text-gray-500">{{ m.where }} · {{ m.stops }} stoppage{{ m.stops === 1 ? '' : 's' }}</span></span>
                <span class="shrink-0 text-right text-xs"><span class="block font-semibold tabular-nums text-gray-900">{{ duration(m.hours) }} down</span><span class="block tabular-nums" :class="m.availability < 95 ? 'text-red-600' : 'text-gray-500'">{{ m.availability }}% available</span></span>
              </router-link>
            </li>
            <li v-if="!r.downtime.machines.length" class="px-5 py-3 text-sm text-gray-500">No machine downtime recorded in this period.</li>
          </ul>
        </div>
        <div class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Failures</h2><span class="text-xs text-gray-500">{{ r.failures.repairs ? `${r.failures.coded} of ${r.failures.repairs} repairs coded` : 'Codes on completed jobs' }}</span></div>
          <div class="grid gap-5 p-5 sm:grid-cols-2">
            <div v-for="g in [{ key: 'problems', label: 'Top problems', bar: 'bg-red-400' }, { key: 'causes', label: 'Top causes', bar: 'bg-amber-400' }]" :key="g.key">
              <p class="section-label mb-2">{{ g.label }}</p>
              <ul class="space-y-2">
                <li v-for="c in r.failures[g.key]" :key="c.code" class="text-sm">
                  <div class="flex justify-between gap-2"><span class="truncate">{{ c.title }}</span><span class="tabular-nums text-gray-600">{{ c.jobs }}</span></div>
                  <div class="mt-1 h-1.5 rounded-full bg-gray-100"><div class="h-1.5 rounded-full" :class="g.bar" :style="{ width: `${(100 * c.jobs) / r.failures[g.key][0].jobs}%` }" /></div>
                </li>
                <li v-if="!r.failures[g.key].length" class="text-sm text-gray-500">None recorded.</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <div class="card overflow-hidden">
        <div class="card-header"><h2 class="card-title">Machines with the most repairs</h2><span class="text-xs text-gray-500">Repeat breakdowns are worth a closer look</span></div>
        <ul class="divide-y divide-gray-100">
          <li v-for="m in r.machines" :key="m.name">
            <router-link :to="m.kind === 'equipment' ? { name: 'OpsEquipmentDetail', params: { name: m.name } } : { name: 'OpsAsset', params: { name: m.name } }" class="flex items-center gap-3 px-5 py-3 hover:bg-gray-50">
              <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm font-bold tabular-nums" :class="m.repairs > 2 ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-800'">{{ m.repairs }}</span>
              <span class="min-w-0 flex-1"><span class="block truncate font-medium">{{ m.label }}</span><span class="block truncate text-xs text-gray-500">{{ m.where }}</span></span>
              <span class="shrink-0 text-xs text-gray-500">{{ m.avg_hours !== null ? `${duration(m.avg_hours)} to fix` : 'Not fixed yet' }}</span>
            </router-link>
          </li>
          <li v-if="!r.machines.length" class="px-5 py-3 text-sm text-gray-500">No repairs on machines in this period.</li>
        </ul>
      </div>

      <div class="card overflow-hidden">
        <div class="card-header"><h2 class="card-title">Service contract profit</h2><span class="text-xs text-gray-500">Money in vs money out for the period</span></div>
        <p v-if="!r.contracts.labour_cost_rate" class="mx-5 mt-4 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">Labour isn't costed yet. Set <b>Labour Cost per Hour</b> in <a href="/desk/techy-ops-settings" target="_blank" rel="noopener" class="underline">Techy Ops Settings</a> to include technicians' time.</p>
        <div class="overflow-x-auto">
          <table class="w-full min-w-[44rem] text-sm">
            <thead class="border-b border-gray-100 text-left text-xs text-gray-500">
              <tr><th class="px-5 py-2 font-medium">Contract</th><th class="px-3 py-2 text-right font-medium">Jobs</th><th class="px-3 py-2 text-right font-medium">Subscription</th><th class="px-3 py-2 text-right font-medium">Extra billed</th><th class="px-3 py-2 text-right font-medium">Parts cost</th><th class="px-3 py-2 text-right font-medium">Labour cost</th><th class="px-5 py-2 text-right font-medium">Profit</th></tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="c in r.contracts.rows" :key="c.name">
                <td class="px-5 py-2.5"><router-link :to="{ name: 'OpsContract', params: { name: c.name } }" class="font-medium hover:text-brand-700">{{ c.customer_name }}</router-link><span class="block text-xs text-gray-500">{{ c.title }} · {{ c.state }}</span></td>
                <td class="px-3 py-2.5 text-right tabular-nums">{{ c.jobs }}</td>
                <td class="px-3 py-2.5 text-right tabular-nums">{{ money(c.subscription) }}</td>
                <td class="px-3 py-2.5 text-right tabular-nums">{{ money(c.extra) }}</td>
                <td class="px-3 py-2.5 text-right tabular-nums text-gray-600">{{ money(c.parts_cost) }}</td>
                <td class="px-3 py-2.5 text-right tabular-nums text-gray-600">{{ money(c.labour_cost) }}<span v-if="c.labour_hours" class="block text-[11px] text-gray-400">{{ c.labour_hours }} h</span></td>
                <td class="px-5 py-2.5 text-right tabular-nums font-semibold" :class="c.profit < 0 ? 'text-red-600' : c.profit > 0 ? 'text-green-700' : 'text-gray-500'">{{ money(c.profit) }}<span v-if="c.margin !== null" class="block text-[11px] font-medium">{{ c.margin }}%</span></td>
              </tr>
              <tr v-if="!r.contracts.rows.length"><td colspan="7" class="px-5 py-3 text-gray-500">No service contracts ran in this period.</td></tr>
            </tbody>
          </table>
        </div>
        <p class="border-t border-gray-100 px-5 py-3 text-xs text-gray-500">Money in is the contract's submitted subscription invoices plus submitted invoices for extra work on its machines. Money out is the parts issued at stock cost plus labour hours at your cost per hour.</p>
      </div>
    </template>
    <Modal v-model="showCodes" title="Failure codes" subtitle="Technicians pick these on jobs: what was wrong, why, and what fixed it." size="lg">
      <div v-if="!codesLoading && !allCodes.length" class="rounded-lg border border-dashed border-gray-300 p-4 text-center text-sm text-gray-600">
        No codes yet.
        <button class="btn btn-secondary btn-sm mt-2" :disabled="savingCode" @click="addDefaults">Add common water-treatment codes</button>
      </div>
      <div v-for="k in ['Problem', 'Cause', 'Remedy']" v-else :key="k" class="mb-4">
        <p class="section-label mb-1">{{ k === 'Problem' ? 'Problems' : k === 'Cause' ? 'Causes' : 'Remedies' }}</p>
        <ul class="divide-y divide-gray-100 rounded-lg border border-gray-200">
          <li v-for="c in codes[k]" :key="c.code" class="flex items-center gap-3 px-3 py-2 text-sm" :class="c.disabled ? 'text-gray-400' : ''">
            <span class="w-32 shrink-0 truncate font-mono text-xs">{{ c.code }}</span>
            <span class="min-w-0 flex-1 truncate">{{ c.title }}</span>
            <button class="btn btn-ghost btn-sm" :disabled="savingCode" @click="saveCode({ ...c, disabled: c.disabled ? 0 : 1 })">{{ c.disabled ? 'Enable' : 'Disable' }}</button>
          </li>
        </ul>
      </div>
      <form class="mt-2 grid gap-2 border-t border-gray-100 pt-4 sm:grid-cols-[8rem_1fr_7rem_auto]" @submit.prevent="saveCode({ ...newCode, disabled: 0 })">
        <input v-model="newCode.code" required maxlength="40" class="input font-mono uppercase" placeholder="CODE" aria-label="New code" />
        <input v-model="newCode.title" required maxlength="140" class="input" placeholder="Title, e.g. Pump seal leaking" aria-label="New code title" />
        <select v-model="newCode.kind" class="input" aria-label="New code kind"><option>Problem</option><option>Cause</option><option>Remedy</option></select>
        <button class="btn btn-primary" :disabled="savingCode">Add</button>
      </form>
      <p v-if="codeError" role="alert" class="mt-2 text-sm text-red-600">{{ codeError }}</p>
    </Modal>
  </section>
</template>
<script setup>
import { ref, reactive, computed, onMounted, h } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import Modal from '@/components/ops/Modal.vue'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import { api, formatDate } from '@/data/ops'

const PERIODS = [{ days: 7, label: '7 days' }, { days: 30, label: '30 days' }, { days: 90, label: '90 days' }, { days: 365, label: '12 months' }]
const days = ref(30)
const r = ref(null)
const busy = ref(false)
const error = ref('')

const money = (n) => {
  const currency = r.value?.currency || 'KES'
  try {
    return Number(n || 0).toLocaleString(undefined, { style: 'currency', currency, maximumFractionDigits: 0 })
  } catch (e) {
    return `${currency} ${Math.round(n || 0).toLocaleString()}`
  }
}
const duration = (h) => {
  if (h === null || h === undefined) return '–'
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} min`
  if (h < 48) return `${h.toFixed(h < 10 ? 1 : 0)} h`
  return `${(h / 24).toFixed(1)} days`
}
function change(now, before, lowerIsBetter = false, neutral = false) {
  if (before === null || before === undefined || now === null || now === undefined) return {}
  if (!before) return now ? { sub: 'None in the prior period' } : { sub: 'Same as the prior period' }
  const pct = Math.round((100 * (now - before)) / before)
  if (!pct) return { sub: 'Same as the prior period' }
  const good = lowerIsBetter ? pct < 0 : pct > 0
  return { sub: `${pct > 0 ? '▲' : '▼'} ${Math.abs(pct)}% vs prior period`, subTone: neutral ? 'text-gray-500' : good ? 'text-green-700' : 'text-red-600' }
}

// Technician scorecard -------------------------------------------------------------------------------------------
const open = ref('')
const ISSUES = {
  late: { label: 'Late', tone: 'bg-amber-100 text-amber-800' },
  repeat: { label: 'Repaired again', tone: 'bg-red-100 text-red-700' },
  reopened: { label: 'Sent back', tone: 'bg-orange-100 text-orange-800' },
  uncoded: { label: 'Not coded', tone: 'bg-gray-200 text-gray-700' },
}
const scoreTone = (n) => (n >= 85 ? 'bg-green-100 text-green-800' : n >= 70 ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-700')
const best = computed(() => {
  const scored = (r.value?.technicians || []).filter((t) => t.score !== null)
  return scored.length > 1 ? scored[0] : null
})
// A percentage with the counts behind it ("67%", "2 of 3").
const Rate = (props) =>
  props.value === null || props.value === undefined
    ? h('span', { class: 'text-gray-400' }, '–')
    : h('span', { class: 'tabular-nums' }, [
        h('span', { class: props.value >= 85 ? 'text-gray-900' : props.value >= 70 ? 'text-amber-700' : 'font-semibold text-red-600' }, `${props.value}%`),
        h('span', { class: 'block text-[11px] text-gray-400' }, `${props.part} of ${props.whole}`),
      ])
Rate.props = ['value', 'part', 'whole']

const tiles = computed(() => {
  const w = r.value.work
  const p = r.value.previous
  const pm = r.value.pm
  return [
    { label: 'Jobs completed', value: w.completed, ...change(w.completed, p.completed) },
    { label: 'Jobs opened', value: w.created, ...change(w.created, p.created, false, true) },
    { label: 'Open now', value: w.open, sub: w.overdue ? `${w.overdue} overdue` : 'None overdue', subTone: w.overdue ? 'font-semibold text-red-600' : 'text-green-700' },
    { label: 'Avg time to fix (repairs)', value: duration(w.repair_hours), ...change(w.repair_hours, p.repair_hours, true) },
    { label: 'Avg time to start', value: duration(w.response_hours), sub: 'From opened to work started' },
    { label: 'PM done on time', value: pm.compliance === null ? '–' : `${pm.compliance}%`, tone: pm.compliance === null ? '' : pm.compliance >= 90 ? 'text-green-700' : pm.compliance >= 70 ? 'text-amber-700' : 'text-red-600', sub: `${pm.on_time + pm.late + pm.missed} due so far` },
    { label: 'Requests received', value: r.value.requests.received, sub: `${r.value.requests.pending} waiting for review` },
    { label: 'Contract profit', value: money(r.value.contracts.rows.reduce((s, c) => s + c.profit, 0)), tone: r.value.contracts.rows.reduce((s, c) => s + c.profit, 0) < 0 ? 'text-red-600' : '', sub: `${r.value.contracts.rows.length} contract${r.value.contracts.rows.length === 1 ? '' : 's'}` },
  ]
})
const peak = computed(() => Math.max(1, ...r.value.chart.map((c) => Math.max(c.created, c.completed))))
const bar = (n) => (n ? `${Math.max(4, (100 * n) / peak.value)}%` : '0')
const chartLabel = computed(() => r.value.chart.map((c) => `${c.label}: ${c.created} opened, ${c.completed} completed`).join('; '))
const pmParts = computed(() => [
  { label: 'On time', value: r.value.pm.on_time, bar: 'bg-green-500', text: 'text-green-700' },
  { label: 'Late', value: r.value.pm.late, bar: 'bg-amber-400', text: 'text-amber-700' },
  { label: 'Missed', value: r.value.pm.missed, bar: 'bg-red-500', text: 'text-red-600' },
  { label: 'Upcoming', value: r.value.pm.upcoming, bar: 'bg-gray-300', text: 'text-gray-600' },
])
const pmTotal = computed(() => pmParts.value.reduce((s, p) => s + p.value, 0))
const requestStats = computed(() => [
  { label: 'Received', value: r.value.requests.received },
  { label: 'Turned into jobs', value: r.value.requests.approved },
  { label: 'Declined', value: r.value.requests.declined },
  { label: 'Waiting', value: r.value.requests.pending },
])

// Failure codes ----------------------------------------------------------------------------------------------
const showCodes = ref(false)
const codes = reactive({ Problem: [], Cause: [], Remedy: [] })
const allCodes = computed(() => [...codes.Problem, ...codes.Cause, ...codes.Remedy])
const codesLoading = ref(false)
const savingCode = ref(false)
const codeError = ref('')
const newCode = reactive({ code: '', title: '', kind: 'Problem' })
async function openCodes() {
  showCodes.value = true
  codesLoading.value = true
  try {
    Object.assign(codes, await api('projectit.failures.options', { include_disabled: 1 }))
  } catch (e) {
    codeError.value = e.message
  } finally {
    codesLoading.value = false
  }
}
async function codeCall(method, args = {}) {
  savingCode.value = true
  codeError.value = ''
  try {
    Object.assign(codes, await api(method, args))
    return true
  } catch (e) {
    codeError.value = e.message
    return false
  } finally {
    savingCode.value = false
  }
}
const addDefaults = () => codeCall('projectit.failures.add_defaults')
async function saveCode(c) {
  if (await codeCall('projectit.failures.save_code', { code: c.code, title: c.title, kind: c.kind, description: c.description || null, disabled: c.disabled })) {
    if (c === newCode || c.code === newCode.code) Object.assign(newCode, { code: '', title: '' })
  }
}

async function load() {
  busy.value = true
  error.value = ''
  try {
    r.value = await api('projectit.reports.dashboard', { days: days.value })
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>
