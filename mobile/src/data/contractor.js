/**
 * The contractor app (/contractor): external technicians and small companies with crews (projectit/contractors.py).
 * Owners see pay; owners and leads accept jobs and choose crew; crew do the jobs given to them.
 */
import { reactive } from 'vue'
import { api } from './ops'

export const contractor = reactive({ me: null, error: '' })

let loading = null
export function loadContractor(force = false) {
  if (!loading || force) {
    loading = api('projectit.contractors.me')
      .then((me) => {
        contractor.me = me
        contractor.error = ''
        return me
      })
      .catch((e) => {
        contractor.error = e.message
        loading = null
        throw e
      })
  }
  return loading
}

export const ROLE_LABEL = { Owner: 'Owner', Lead: 'Lead', Crew: 'Crew' }
export const PAY_TYPES = ['Fixed', 'Hourly', 'Per unit']
export const PAY_TYPE_LABEL = {
  Fixed: 'Fixed price',
  Hourly: 'Per hour',
  'Per unit': 'Per unit',
  Milestone: 'Milestone',
  Reimbursement: 'Bought on site',
  Deduction: 'Deduction',
}
export const LINE_STYLE = {
  Draft: 'bg-gray-100 text-gray-700',
  Approved: 'bg-green-100 text-green-800',
  'On hold': 'bg-amber-100 text-amber-800',
  Billed: 'bg-blue-100 text-blue-800',
  Paid: 'bg-brand-100 text-brand-800',
}
export const LINE_LABEL = { Draft: 'Waiting for approval', Approved: 'Approved', 'On hold': 'On hold', Billed: 'Billed', Paid: 'Paid' }

/** Money in the site's currency, without decimals when there are none. */
export function money(value, currency) {
  const n = Number(value || 0)
  try {
    return new Intl.NumberFormat(undefined, { style: currency ? 'currency' : 'decimal', currency: currency || undefined, maximumFractionDigits: n % 1 ? 2 : 0 }).format(n)
  } catch (e) {
    return `${currency || ''} ${n.toFixed(n % 1 ? 2 : 0)}`.trim()
  }
}

/** The phone's location, with messages a person can act on. */
export function getLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('This device cannot share its location, which is required to check in and out.'))
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => resolve({ latitude: coords.latitude, longitude: coords.longitude }),
      (e) =>
        reject(
          new Error(
            e.code === 1
              ? 'Allow location access for this app, then try again. Your location is recorded with each check-in and check-out.'
              : e.code === 3
                ? 'Getting your location took too long. Move to an open area and try again.'
                : 'Your location could not be determined. Check that location services are on and try again.',
          ),
        ),
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 },
    )
  })
}
