import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Orca',
    short_name: 'Orca',
    description: 'Platform streaming anime premium minimalis — cepat, elegan, gratis.',
    start_url: '/',
    display: 'standalone',
    background_color: '#000000',
    theme_color: '#000000',
    icons: [
      {
        src: '/api/icon?size=192&dark=true',
        sizes: '192x192',
        type: 'image/png',
      },
      {
        src: '/api/icon?size=512&dark=true',
        sizes: '512x512',
        type: 'image/png',
      },
    ],
  };
}