import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Every page is per-student and live (session, listings, deal status), so pages
  // render per request; Cache Components would add nothing here.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  images: {
    // Listing photos are short-lived presigned S3 URLs; avatars come from Discord.
    remotePatterns: [
      { protocol: "https", hostname: "*.s3.amazonaws.com" },
      { protocol: "https", hostname: "*.s3.us-east-2.amazonaws.com" },
      { protocol: "https", hostname: "cdn.discordapp.com" },
    ],
  },
};

export default nextConfig;
