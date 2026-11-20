import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';
import jsxA11y from 'eslint-plugin-jsx-a11y';

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  // eslint-config-next registers the jsx-a11y plugin; turn on its full recommended set.
  { files: ['**/*.{jsx,tsx}'], rules: jsxA11y.flatConfigs.recommended.rules },
  // Feature and app code draws controls and tables with the shared components (src/components), never raw elements.
  {
    files: ['src/features/**/*.{jsx,tsx}', 'src/app/**/*.{jsx,tsx}'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: 'JSXOpeningElement[name.type="JSXIdentifier"][name.name=/^(button|input|select|textarea|table)$/]',
          message: 'Use the shared component from @/components (Button, TextField, Select, TextArea, Table, ...) instead of a raw control or table.',
        },
      ],
    },
  },
  globalIgnores(['.next/**', 'node_modules/**', 'playwright-report/**', 'test-results/**', 'next-env.d.ts', 'src/api/schema.d.ts']),
]);
