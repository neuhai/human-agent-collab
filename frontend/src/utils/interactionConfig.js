/**
 * Match setup.vue pathToConfigKey: last segment with first char lowercased.
 * @param {string} path
 * @returns {string|null}
 */
function pathToConfigKey(path) {
  if (!path || typeof path !== 'string') return null
  const parts = path.split('.')
  const key = parts.length >= 2 ? parts[parts.length - 1] : parts[0]
  return key ? key.charAt(0).toLowerCase() + key.slice(1) : null
}

/**
 * Read one interaction param from session.interaction, which may be flat
 * ({ typeIndicator: 'enabled' }) or nested ({ "Information Flow": [ { path, default, value? } ] }).
 * @param {Record<string, unknown>|null|undefined} interaction
 * @param {string} paramKey — e.g. 'typeIndicator' (same key as setup saves)
 * @returns {unknown}
 */
export function getInteractionParam(interaction, paramKey) {
  if (!interaction || typeof interaction !== 'object') return undefined
  if (Object.prototype.hasOwnProperty.call(interaction, paramKey)) {
    return interaction[paramKey]
  }
  for (const v of Object.values(interaction)) {
    if (!Array.isArray(v)) continue
    for (const item of v) {
      if (!item || typeof item !== 'object') continue
      const pathKey = item.path ? pathToConfigKey(item.path) : null
      if (pathKey === paramKey) {
        return item.value !== undefined ? item.value : item.default
      }
      if (item.label && typeof item.label === 'string') {
        const labelKey = item.label.toLowerCase().replace(/\s+/g, '').replace(/[^a-z0-9]/g, '')
        const want = String(paramKey).toLowerCase().replace(/[^a-z0-9]/g, '')
        if (labelKey === want) {
          return item.value !== undefined ? item.value : item.default
        }
      }
    }
  }
  return undefined
}

/**
 * Whether "Type Indicator" is on (setup stores 'enabled' / 'not_enabled' for boolean options).
 */
export function isTypeIndicatorEnabled(interaction) {
  const v = getInteractionParam(interaction, 'typeIndicator')
  if (v === true) return true
  if (typeof v !== 'string') return false
  const n = v.toLowerCase().replace(/\s+/g, '_')
  return n === 'enabled'
}
