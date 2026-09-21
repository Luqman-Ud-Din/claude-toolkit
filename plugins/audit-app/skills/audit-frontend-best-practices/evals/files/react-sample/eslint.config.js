import reactHooks from 'eslint-plugin-react-hooks';

export default [
  { files: ['**/*.{ts,tsx}'], plugins: { 'react-hooks': reactHooks }, rules: reactHooks.configs.recommended.rules },
];
