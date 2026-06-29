/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['mapbox-gl'],
  images: {
    domains: ['api.mapbox.com'],
  },
};

export default nextConfig;
