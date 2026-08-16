import tseslint from "@typescript-eslint/eslint-plugin";
import parser from "@typescript-eslint/parser";
export default [
  {
    files: ["packages/pi-science/{src,tests}/**/*.ts"],
    languageOptions: { parser, parserOptions: { project: "./tsconfig.json" } },
    plugins: { "@typescript-eslint": tseslint },
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-floating-promises": "error",
    },
  },
];
