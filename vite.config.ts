import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({ plugins: [react()], build: {target:'chrome80'}, server: { port:7780, strictPort:true, proxy: { '/api': {target:'http://127.0.0.1:7779',changeOrigin:false} } } });
