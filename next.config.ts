import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // Support larger PDF uploads when requests pass through Next.js proxy/routes.
    proxyClientMaxBodySize: "50mb",
  },
};

export default nextConfig;
