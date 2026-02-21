export const TIER_CONFIG = {
  HOT:     { className: 'tier-hot',     label: 'HOT',     hex: '#ef4444' },
  WARM:    { className: 'tier-warm',    label: 'WARM',    hex: '#f59e0b' },
  NURTURE: { className: 'tier-nurture', label: 'NURTURE', hex: '#3b82f6' },
  HOLD:    { className: 'tier-hold',    label: 'HOLD',    hex: '#9ca3af' },
}

export function getTierConfig(tier) {
  return TIER_CONFIG[(tier || 'HOLD').toUpperCase()] || TIER_CONFIG.HOLD
}
