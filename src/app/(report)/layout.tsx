import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "../globals.css";

// Separate root layout: the niche report is a personal document, not part of the
// Customer Feedback / RoleCraft product, so it has no product Header/Footer (spec D-01, C-02).
const inter = Inter({
  subsets: ["latin", "cyrillic"],
  display: "swap",
});

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function ReportLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" className="h-full">
      <body className={`${inter.className} min-h-full bg-slate-50 font-sans text-slate-900 antialiased`}>
        {children}
      </body>
    </html>
  );
}
