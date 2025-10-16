/** @type {import('eslint').Linter.Config} */
module.exports = {
  extends: ["next", "next/core-web-vitals"],
  rules: {
    "@next/next/no-html-link-for-pages": "off"
  }
};
