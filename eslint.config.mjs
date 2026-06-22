import js from '@eslint/js';
import globals from 'globals';
import prettier from 'eslint-config-prettier';

// Flat config (ESLint 9). Lints the WhatsApp bridge JS and the landing-page JS.
// Prettier owns formatting — eslint-config-prettier disables stylistic rules so
// the two never conflict. Run: npm run lint
export default [
  {
    ignores: ['node_modules/**', '**/node_modules/**', 'data/**', 'backups/**', '**/*.min.js'],
  },

  js.configs.recommended,

  // Node.js bridge sources (ES modules)
  {
    files: ['bridge/**/*.js', 'bridge/**/*.mjs', 'patches/whatsapp-bridge.js'],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      globals: { ...globals.node },
    },
    rules: {
      'no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrors: 'all',
          caughtErrorsIgnorePattern: '^_',
        },
      ],
      'no-undef': 'error',
      // Empty catch blocks are a deliberate pattern in the bridge (best-effort
      // cleanup, fire-and-forget logging) — allow them, flag other empty blocks.
      'no-empty': ['error', { allowEmptyCatch: true }],
      eqeqeq: ['error', 'smart'],
      'no-var': 'error',
      // 'all': only flag a destructuring as const-able when EVERY binding is —
      // avoids forcing a `let {a,b}` split when one member is reassigned.
      'prefer-const': ['error', { destructuring: 'all' }],
    },
  },

  // Browser landing-page script
  {
    files: ['assets/**/*.js'],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'script',
      globals: { ...globals.browser },
    },
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },

  prettier,
];
