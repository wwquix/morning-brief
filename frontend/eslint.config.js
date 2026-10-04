import js from "@eslint/js";
import globals from "globals";
import react from "eslint-plugin-react";

export default [
  { ignores: ["dist/**", "node_modules/**"] },
  js.configs.recommended,
  {
    ...react.configs.flat.recommended,
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ...react.configs.flat.recommended.languageOptions,
      globals: globals.browser
    },
    settings: { react: { version: "detect" } },
    rules: {
      ...react.configs.flat.recommended.rules,
      "react/react-in-jsx-scope": "off",
      "react/prop-types": "off"
    }
  },
  { files: ["*.config.js"], languageOptions: { globals: globals.node } },
  { files: ["e2e/*.js"], languageOptions: { globals: { ...globals.node, ...globals.browser } } }
];
