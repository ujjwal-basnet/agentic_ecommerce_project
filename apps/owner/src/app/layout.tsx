import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SmartShop Owner Dashboard",
  description: "Owner analytics & inventory management",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
