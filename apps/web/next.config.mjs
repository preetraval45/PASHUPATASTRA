/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Deployed on Vercel; the API runs on AWS (see docs/DEPLOYMENT.md).
  env: { NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL },
};

export default nextConfig;
