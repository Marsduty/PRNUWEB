import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "成像设备指纹智能取证与比对分析平台",
  description: "基于成像设备指纹的图像取证工作台"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        {children}
        <a className="icp-footer-link" href="https://beian.miit.gov.cn/" target="_blank" rel="noreferrer">
          皖ICP备2026018644号
        </a>
      </body>
    </html>
  );
}
