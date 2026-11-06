import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

/**
 * Flat ESLint config for the Tauri/React frontend.
 *
 * The `src/components/ui/**` tree is vendored shadcn/ui code and is excluded
 * so upstream churn does not create noise in this repository's lint run.
 */
export default tseslint.config(
  {
    ignores: [
      "dist/**",
      "node_modules/**",
      "src/components/ui/**",
      "src-tauri/target/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    plugins: { "react-hooks": reactHooks },
    rules: reactHooks.configs.recommended.rules,
  },
  {
    languageOptions: {
      globals: {
        window: "readonly",
        document: "readonly",
        navigator: "readonly",
        console: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        URL: "readonly",
        Blob: "readonly",
        File: "readonly",
        FileReader: "readonly",
        AudioContext: "readonly",
      },
    },
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-explicit-any": "warn",
      "no-undef": "off",
      // React Compiler advisories. These flag optimisation opportunities in
      // patterns that are already correct and ship today (data fetching in an
      // effect, refs read during render). They are reported as warnings so a
      // refactor can address them incrementally without changing behaviour.
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/incompatible-library": "warn",
    },
  },
);
