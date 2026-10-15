/** Who pays for work on customer equipment, from its warranty and contract end dates. */
export const COVERAGE = {
  Warranty: { label: 'Under warranty', short: 'Warranty', icon: 'shield', tone: 'bg-green-50 text-green-700 ring-green-200' },
  Contract: { label: 'Service contract', short: 'Contract', icon: 'file-text', tone: 'bg-brand-50 text-brand-700 ring-brand-200' },
  Chargeable: { label: 'Chargeable', short: 'Chargeable', icon: 'credit-card', tone: 'bg-amber-50 text-amber-800 ring-amber-200' },
  Pending: { label: 'Warranty from commissioning', short: 'Not commissioned', icon: 'clock', tone: 'bg-violet-50 text-violet-700 ring-violet-200' },
}

export const EQUIPMENT_STATUS = {
  'Awaiting installation': 'bg-violet-50 text-violet-700',
  Active: 'bg-green-50 text-green-700',
  'Out of service': 'bg-red-50 text-red-700',
  Decommissioned: 'bg-gray-100 text-gray-600',
  Cancelled: 'bg-gray-100 text-gray-500',
}

/** Google Maps search for an address block from the API. */
export function mapLink(address) {
  if (!address) return ''
  const q = [address.address_line1, address.address_line2, address.city, address.country].filter(Boolean).join(', ')
  return q ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}` : ''
}
