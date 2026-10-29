import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: ["dist", "node_modules", "src/api/types.gen.ts", "playwright-report", "test-results"],
  },
  {
    files: ["**/*.{ts,tsx,js}"],
    extends: [js.configs.recommended, ...tseslint.configs.strict],
    languageOptions: {
      ecmaVersion: 2023,
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "@typescript-eslint/no-explicit-any": "error",
      "no-restricted-syntax": [
        "error",
        {
          // §21: colors come only from theme tokens (web/src/theme/tokens.css)
          selector: "Literal[value=/#[0-9a-fA-F]{3,8}\\b/]",
          message: "Use a color token from theme/tokens.css, not a hex literal.",
        },
        {
          // §17.11: no interval animation; motion comes from rAF, useFrame or Motion
          selector: "CallExpression[callee.name='setInterval']",
          message: "No setInterval (SPEC §17.11): use requestAnimationFrame or useFrame.",
        },
      ],
    },
  },
);
