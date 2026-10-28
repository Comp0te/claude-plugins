#!/usr/bin/env bash
set -eu
mkdir -p src test
cat > package.json <<'SCAFFOLD_EOF'
{
  "name": "settings",
  "private": true,
  "scripts": {
    "test": "node --test"
  }
}
SCAFFOLD_EOF

cat > src/settings.js <<'SCAFFOLD_EOF'
const settings = {
  theme: 'light',
  fontSize: 14,
  notifications: true,
  language: 'en',
  timezone: 'UTC',
}

const getTheme = () => settings.theme
const getFontSize = () => settings.fontSize
const getNotifications = () => settings.notifications
const getLanguage = () => settings.language
const getTimezone = () => settings.timezone

function normalizeLocale(input) {
  const trimmed = String(input || '').trim()
  if (!trimmed) return 'en-US'
  const [language, region] = trimmed.replace(/_/g, '-').split('-')
  return region ? `${language.toLowerCase()}-${region.toUpperCase()}` : language.toLowerCase()
}

module.exports = {
  getTheme,
  getFontSize,
  getNotifications,
  getLanguage,
  getTimezone,
  normalizeLocale,
}
SCAFFOLD_EOF
