import daisyui from 'daisyui';

export default {
  content: ['./src/**/*.{html,svelte,ts,js}'],
  theme: { 
    extend: {
      colors: {
        'primary': '#AED5F2',    // Light blue
        'secondary': '#1D232A',  // Dark gray/black
        'accent': '#CAFF8A',     // Light green
      }
    } 
  },
  plugins: [daisyui],
  daisyui: {
    themes: [
      {
        musicseerr: {
          "primary": "#AED5F2",      // Light blue
          "secondary": "#1D232A",    // Dark gray/black
          "accent": "#CAFF8A",       // Light green
          "neutral": "#1D232A",      // Using your dark color
          "base-100": "#ffffff",     // White background
          "base-200": "#f5f5f5",     // Light gray
          "base-300": "#e5e5e5",     // Medium gray
          "info": "#AED5F2",         // Using your light blue
          "success": "#CAFF8A",      // Using your light green
          "warning": "#fbbf24",      // Standard warning yellow
          "error": "#f87171",        // Standard error red
        },
      },
    ],
  },
};