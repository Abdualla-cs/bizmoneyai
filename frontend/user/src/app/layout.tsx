import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "BizMoneyAI - AI-Driven Business Finance",
  description: "Track income, expenses, and receive AI-powered insights for your business.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
