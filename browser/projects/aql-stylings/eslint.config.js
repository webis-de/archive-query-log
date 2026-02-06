const baseConfig = require("../../eslint.config.js");

module.exports = [
  ...baseConfig,
  {
    files: ["projects/aql-stylings/**/*.ts", "projects/aql-stylings/**/*.html"],
  },
];

