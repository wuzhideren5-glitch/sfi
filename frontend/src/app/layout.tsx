import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "求职导航官 - 港中深",
  description: "香港中文大学（深圳）商科研究生 AI 求职助手",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">{children}</body>
    </html>
  );
}
