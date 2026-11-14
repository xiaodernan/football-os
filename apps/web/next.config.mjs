import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin('./i18n/request.ts');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // The container build copies .next/standalone verbatim; standalone keeps the runtime
  // image free of the full build dependency tree. Dev and CI behaviour are unchanged.
  output: "standalone",
  // Lets a second instance (CI, a parallel dev server) build into its own cache dir.
  distDir: process.env.NEXT_DIST_DIR ?? '.next',
  eslint: {
    // `npm run lint` is the lint gate; the build stays focused on types + rendering.
    ignoreDuringBuilds: true,
  },
  // The API tier already ships the same set (app/core/response_headers.py); the web tier was the
  // only place a reader's browser got nothing. Fingerprinted `/_next/static/*` keeps its long
  // immutable life (Next sets it); these cover every store the browser can navigate.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "X-DNS-Prefetch-Control", value: "on" },
        ],
      },
    ];
  },
};

export default withNextIntl(nextConfig);