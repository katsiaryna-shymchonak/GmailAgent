import js from '@eslint/js';
import globals from 'globals';
import pluginImport from 'eslint-plugin-import';
import pluginN from 'eslint-plugin-n';
import pluginPromise from 'eslint-plugin-promise';
import prettier from 'eslint-config-prettier';

export default [
  {
    ignores: ['node_modules/', '**/dist/**', '**/.github/**', '**/build/**', 'eslint.config.js'],
  },
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: 'module', // ✅ switched from 'script' to 'module'
      globals: {
        ...globals.browser,
        chrome: 'readonly',
      },
    },
    plugins: {
      import: pluginImport,
      n: pluginN,
      promise: pluginPromise,
    },
    rules: {
      'no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrors: 'none' },
      ],
      'no-console': 'off',
      'import/no-unresolved': 'off',
      'n/no-missing-import': 'off',
    },
  },
  prettier,
];
