// @ts-check
import { defineConfig } from 'astro/config';

import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';
import node from '@astrojs/node';

// https://astro.build/config
export default defineConfig({
  output: 'server',  // Enable SSR for query param support
  adapter: node({
    mode: 'middleware'
  }),
  integrations: [react()],

  vite: {
    plugins: [tailwindcss()]
  }
});