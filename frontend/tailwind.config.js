/** Tailwind theme tokens — exact same palette as the existing :root tokens in src/index.css.
 *  No new colors introduced; utilities reference the identical hex values. */
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        canvas: '#edf0f6',
        surface: '#ffffff',
        heading: '#131c2e',
        ink: '#243041',
        muted: '#66748c',
        primary: {
          DEFAULT: '#4338ca',
          dark: '#3730a3',
          soft: '#eeedfd',
        },
        accent: {
          DEFAULT: '#047857',
          soft: '#e3f5ee',
        },
        line: '#dfe5ee',
        success: '#15803d',
        warning: {
          DEFAULT: '#b45309',
          soft: '#fef3c7',
        },
        danger: {
          DEFAULT: '#b91c1c',
          soft: '#fee2e2',
        },
        info: {
          DEFAULT: '#0284c7',
          soft: '#e0f2fe',
        },
      },
      fontFamily: {
        display: ['Sora', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
      },
      borderRadius: {
        card: '10px',
      },
      boxShadow: {
        sm: '0 1px 3px rgba(19, 28, 46, 0.06), 0 1px 2px rgba(19, 28, 46, 0.04)',
        md: '0 4px 12px rgba(19, 28, 46, 0.08), 0 2px 4px rgba(19, 28, 46, 0.04)',
        lg: '0 8px 24px rgba(19, 28, 46, 0.10), 0 4px 8px rgba(19, 28, 46, 0.06)',
      },
    },
  },
  plugins: [],
};
