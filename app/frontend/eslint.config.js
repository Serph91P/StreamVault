import pluginVue from 'eslint-plugin-vue'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'
import tseslint from 'typescript-eslint'
import vueParser from 'vue-eslint-parser'

export default [
  {
    name: 'app/files-to-lint',
    files: ['**/*.{ts,mts,tsx,vue}'],
  },

  {
    name: 'app/files-to-ignore',
    ignores: [
      '**/dist/**',
      '**/dist-ssr/**',
      '**/coverage/**',
      '**/public/**',
      '**/node_modules/**',
      '**/*.d.ts',
    ],
  },

  ...pluginVue.configs['flat/essential'],
  ...tseslint.configs.recommended,

  // Restore the Vue parser after typescript-eslint's base config and delegate
  // TypeScript script blocks to the official TypeScript parser.
  ...pluginVue.configs['flat/base'],
  {
    name: 'app/vue-typescript-parser',
    files: ['**/*.vue'],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: {
          ts: tseslint.parser,
          tsx: tseslint.parser,
        },
        ecmaVersion: 2024,
        extraFileExtensions: ['.vue'],
      },
    },
  },
  skipFormatting,

  // Project-specific rule overrides
  {
    name: 'app/rule-overrides',
    rules: {
      // Allow `any` in specific cases (API responses, event handlers)
      '@typescript-eslint/no-explicit-any': 'warn',
      // Allow unused vars with underscore prefix, and allow catch block errors
      '@typescript-eslint/no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrors: 'none',  // Allow unused error variables in catch blocks
      }],
      // Allow single-word component names for common utilities
      'vue/multi-word-component-names': 'off',
      // Don't require lang attribute on script tags
      'vue/block-lang': 'off',
    },
  },
]
