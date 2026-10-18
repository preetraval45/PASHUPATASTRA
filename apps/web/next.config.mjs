/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Deployed on Vercel; the API runs on AWS (see docs/DEPLOYMENT.md).
  env: { NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL },
  // The drill list became the Training page (RP-55). A real 308 rather than a
  // redirect from inside a rendered page, so old links and crawlers are told
  // where it went before anything renders. Individual drills keep their URLs.
  async redirects() {
    return [{ source: "/blue-team", destination: "/training", permanent: true }];
  },
};

export default nextConfig;
