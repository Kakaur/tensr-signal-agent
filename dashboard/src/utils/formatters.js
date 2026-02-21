export function formatDate(dateStr) {
  if (!dateStr) return '—'
  if (/^\d{4}$/.test(dateStr)) return dateStr
  try {
    const d = new Date(dateStr)
    // "MMM DD" format e.g. "Dec 15"
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  } catch {
    return dateStr
  }
}

export function formatDateTime(dateStr) {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    if (Number.isNaN(d.getTime())) return dateStr
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

export function formatSignalType(type) {
  if (!type) return '—'
  return type.charAt(0).toUpperCase() + type.slice(1)
}

export function formatDomain(domain) {
  const MAP = {
    ai_transformation:        'AI Transformation',
    ai_implementation:        'AI Implementation',
    agentic_automation:       'Agentic Automation',
    industrial_automation:    'Industrial Automation',
    digital_product_passport: 'Digital Product Passport',
    sovereign_cloud:          'Sovereign Cloud',
    tokenized_rwa:            'Tokenized RWA',
    smart_city:               'Smart City',
    ai_compliance_risk:       'AI Compliance / Risk',
    stablecoin:               'Stablecoin',
    digital_assets:           'Digital Assets',
    other:                    'Other',
  }
  return MAP[domain] || (domain ? domain.replace(/_/g, ' ') : '—')
}

export function formatInstitutionTier(tier) {
  const MAP = {
    mid_tier:   'Mid-tier',
    community:  'Community',
    fintech:    'Fintech',
    industrial: 'Industrial',
    top_tier:   'Top-tier',
    tier1:      'Tier 1',
  }
  return MAP[tier] || tier || '—'
}

// Returns blank string (not "Unknown") for unknown seniority — keeps UI clean
export function formatSeniority(seniority) {
  if (!seniority || seniority.toLowerCase() === 'unknown') return ''
  return seniority
}
