import pluginVue from 'eslint-plugin-vue'
import vueTsEslintConfig from '@vue/eslint-config-typescript'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'

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
  ...vueTsEslintConfig(),
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
