// Turn server rows into SearchSelect options, so every project or task field searches the same way.

// Projects: search by name, code (PROJ-0125) or customer.
export const projectOptions = (rows) =>
  (rows || []).map((p) => ({
    value: p.name,
    label: p.project_name || p.name,
    sub: [p.name, p.customer].filter(Boolean).join(' · '),
  }))

// Tasks: search by subject or task code.
export const taskOptions = (rows) =>
  (rows || []).map((t) => ({ value: t.name, label: t.subject || t.name, sub: t.name }))
