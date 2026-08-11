import { createMDX } from 'fumadocs-mdx/next';

const withMDX = createMDX();

/** @type {import('next').NextConfig} */
const config = {
  reactStrictMode: true,
  async redirects() {
    return [
      { source: '/mac', destination: '/apps/macos', permanent: true },
      { source: '/guides/mac', destination: '/apps/macos', permanent: true },
      { source: '/guides/ui', destination: '/web/composer', permanent: true },
      { source: '/cli', destination: '/cli/terminal', permanent: true },
      { source: '/cli/quickstart', destination: '/quickstart', permanent: true },
      { source: '/cli/interactive', destination: '/cli/terminal', permanent: true },
      { source: '/guides/cli', destination: '/cli/terminal', permanent: true },
      { source: '/guides', destination: '/web/composer', permanent: true },
      { source: '/web', destination: '/web/composer', permanent: true },
      { source: '/get-started', destination: '/quickstart', permanent: true },
      {
        source: '/get-started/quickstart',
        destination: '/quickstart',
        permanent: true,
      },
      {
        source: '/get-started/configuration',
        destination: '/configuration',
        permanent: true,
      },
      { source: '/extend', destination: '/skills', permanent: true },
      { source: '/skills-and-mcps', destination: '/skills', permanent: true },
      {
        source: '/web/models-and-tools',
        destination: '/models',
        permanent: true,
      },
    ];
  },
};

export default withMDX(config);
