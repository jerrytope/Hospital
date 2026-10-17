/** Design tokens for the site. Change brand colours and fonts here. */
module.exports = {
  content: ["./templates/**/*.html", "./apps/**/templates/**/*.html", "./apps/**/*.py", "./static/js/**/*.js"],
  // Classes built from template variables, which the scanner cannot see.
  safelist: ["grid-cols-1", "grid-cols-2", "grid-cols-3", "grid-cols-4", "md:grid-cols-1", "md:grid-cols-2", "md:grid-cols-3", "lg:grid-cols-3", "lg:grid-cols-4"],
  theme: {
    screens: { sm: "480px", md: "768px", lg: "1024px", xl: "1200px", "2xl": "1440px" },
    extend: {
      colors: {
        brand: {
          dark: "#0B2545", // headings, header text, footer
          DEFAULT: "#13599E", // links, secondary buttons
          light: "#22A6D8", // highlights, eyebrows
          mist: "#EEF4FA", // tinted section backgrounds
        },
        accent: { DEFAULT: "#E8532B", dark: "#C9401C" }, // donate buttons only
        ok: "#2E9E6B",
        warn: "#F2B33D",
        danger: "#D64545",
        ink: "#2B2F36",
        muted: "#5F6672",
        line: "#E3E7ED",
      },
      fontFamily: {
        sans: ['"Source Sans 3"', "Helvetica Neue", "Arial", "sans-serif"],
        display: ["Montserrat", "Helvetica Neue", "Arial", "sans-serif"],
        serif: ['"Noto Serif"', "Georgia", "serif"],
      },
      maxWidth: { site: "1240px" },
      boxShadow: { card: "0 1px 2px rgba(11,37,69,.06), 0 8px 24px rgba(11,37,69,.08)" },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
