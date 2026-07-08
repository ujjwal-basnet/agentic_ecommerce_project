import type { Metadata } from "next";
import { Manrope, Inter } from "next/font/google";
import "./globals.css";
import { AppGate } from "@/components/AppGate";

const manrope = Manrope({ subsets: ["latin"], variable: "--font-manrope" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "SmartShop",
  description: "AI-powered shopping assistant",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${manrope.variable} ${inter.variable}`}>
      <body className="min-h-screen bg-surface text-on-surface font-body antialiased">
        <AppGate>{children}</AppGate>
      </body>
    </html>
  );
}
