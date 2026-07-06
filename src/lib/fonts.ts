import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";

// Identidade "instrumento de precisão": duas famílias apenas.
// Sans para interface e headings; Mono para dados, tags e microlabels.
export const fontSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex-sans",
  display: "swap",
});

export const fontMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
});
