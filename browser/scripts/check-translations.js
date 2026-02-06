#!/usr/bin/env node
/**
 * Translation Validation Script
 * Checks if all translation files have the same keys as the base English translation
 */

const fs = require('fs');
const path = require('path');

const translationsDir = path.join(__dirname, '../src/assets/i18n');
const baseFile = 'en.json';

/**
 * Recursively get all keys from a nested object
 * @param {Object} obj - The object to extract keys from
 * @param {string} prefix - The prefix for nested keys
 * @returns {string[]} - Array of dot-notation keys
 */
function getAllKeys(obj, prefix = '') {
  let keys = [];
  for (const key in obj) {
    const newPrefix = prefix ? `${prefix}.${key}` : key;
    if (typeof obj[key] === 'object' && obj[key] !== null && !Array.isArray(obj[key])) {
      keys = keys.concat(getAllKeys(obj[key], newPrefix));
    } else {
      keys.push(newPrefix);
    }
  }
  return keys;
}

/**
 * Main validation function
 */
function validateTranslations() {
  console.log('🔍 Validating translation files...\n');

  // Read base translation file
  const basePath = path.join(translationsDir, baseFile);
  if (!fs.existsSync(basePath)) {
    console.error(`❌ Base file ${baseFile} not found!`);
    process.exit(1);
  }

  const baseTranslations = JSON.parse(fs.readFileSync(basePath, 'utf8'));
  const baseKeys = getAllKeys(baseTranslations).sort();

  console.log(`📄 Base file (${baseFile}) has ${baseKeys.length} keys\n`);

  let hasErrors = false;

  // Check all other translation files
  const files = fs.readdirSync(translationsDir);
  files.forEach(file => {
    if (file === baseFile || !file.endsWith('.json')) return;

    const filePath = path.join(translationsDir, file);
    const translation = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    const translationKeys = getAllKeys(translation).sort();

    console.log(`📄 Checking ${file}...`);

    // Find missing keys
    const missingKeys = baseKeys.filter(k => !translationKeys.includes(k));

    // Find extra keys (keys in translation but not in base)
    const extraKeys = translationKeys.filter(k => !baseKeys.includes(k));

    if (missingKeys.length > 0) {
      hasErrors = true;
      console.error(`   ❌ Missing ${missingKeys.length} keys:`);
      missingKeys.forEach(k => console.log(`      - ${k}`));
    }

    if (extraKeys.length > 0) {
      hasErrors = true;
      console.warn(`   ⚠️  Extra ${extraKeys.length} keys (not in base):`);
      extraKeys.forEach(k => console.log(`      - ${k}`));
    }

    if (missingKeys.length === 0 && extraKeys.length === 0) {
      console.log(`   ✅ Complete (${translationKeys.length} keys)\n`);
    } else {
      console.log('');
    }
  });

  if (hasErrors) {
    console.error('\n❌ Translation validation failed!');
    console.error('Please ensure all translation files have the same keys.\n');
    process.exit(1);
  } else {
    console.log('\n✅ All translation files are valid!\n');
  }
}

// Run validation
try {
  validateTranslations();
} catch (error) {
  console.error('❌ Error during validation:', error.message);
  process.exit(1);
}
