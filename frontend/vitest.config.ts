import { defineConfig } from 'vitest/config'
import baseConfig from './vite.config.ts'

export default defineConfig({
  ...baseConfig,
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
    restoreMocks: true,
  },
})
