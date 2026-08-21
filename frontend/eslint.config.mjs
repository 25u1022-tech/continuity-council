import js from "@eslint/js";
import reactPlugin from "eslint-plugin-react";
import reactHooksPlugin from "eslint-plugin-react-hooks";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    files: ["src/**/*.{js,jsx}"],
    plugins: {
      react: reactPlugin,
      "react-hooks": reactHooksPlugin,
    },
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.jest,
        React: "writable",
        process: "readonly",
      },
    },
    rules: {
      "no-undef": "error",
      "no-unused-vars": "off",
      "react/jsx-uses-vars": "error",
      "react/jsx-no-undef": "error",
    },
    settings: {
      react: {
        version: "detect",
      },
    },
  },
];
