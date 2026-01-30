import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    root: "..",
    rules: {
      "*.md": {
        loaders: ["raw-loader"],
        as: "*.js",
      },
    },
  },
  env: {
    API_BASE_URL: process.env.API_BASE_URL,
  },
};

export default nextConfig;
