import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "../globals.css";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Customer Feedback Intelligence | Semantic Feedback Analyzer",
  description:
    "Production-grade customer feedback intelligence platform that analyzes sentiment, extracts top strategic insights, and generates actionable problem-solution matrices.",
  keywords: [
    "Customer Feedback",
    "Sentiment Analysis",
    "Product Intelligence",
    "SaaS",
    "Next.js",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full">
      <body className={`${inter.className} flex min-h-full flex-col bg-slate-50 font-sans text-slate-900 antialiased selection:bg-slate-900 selection:text-white`}>
        <Header />
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
