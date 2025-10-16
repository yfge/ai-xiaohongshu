/** @type {import('@commitlint/types').UserConfig} */
module.exports = {
  rules: {
    "type-enum": [
      2,
      "always",
      [
        "build",
        "chore",
        "ci",
        "docs",
        "feat",
        "fix",
        "perf",
        "refactor",
        "revert",
        "style",
        "test"
      ]
    ],
    "scope-empty": [2, "never"],
    "subject-empty": [2, "never"],
    "subject-case": [2, "never", ["sentence-case"]],
    "header-max-length": [2, "always", 72]
  }
};
