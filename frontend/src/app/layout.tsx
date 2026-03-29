import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI视频生成平台",
  description: "基于AI的智能视频生成工具",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-gray-50">{children}</body>
    </html>
  );
}
