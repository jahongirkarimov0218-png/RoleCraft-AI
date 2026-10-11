import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "PromptGraphify",
  description:
    "Static analysis of LLM prompts: knowledge graph, execution DAG and diagnostics. Community-built; not affiliated with Graphify Labs.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
