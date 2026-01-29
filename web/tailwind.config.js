/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ['Inter', 'sans-serif'],
            },
            colors: {
                background: "#09090b",
                surface: "#18181b",
                primary: "#fafafa",
                secondary: "#a1a1aa",
                accent: "#3b82f6",
            }
        },
    },
    plugins: [],
}
