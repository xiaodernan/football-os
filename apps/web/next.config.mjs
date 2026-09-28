import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin('./i18n/request.ts');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Lets a second instance (CI, a parallel dev server) build into its own cache dir.
  distDir: process.env.NEXT_DIST_DIR ?? '.next',
  eslint: {
    // `npm run lint` is the lint gate; the build stays focused on types + rendering.
    ignoreDuringBuilds: true,
  },
};

export default withNextIntl(nextConfig);