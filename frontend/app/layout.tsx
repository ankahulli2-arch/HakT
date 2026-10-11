import type { Metadata } from "next";
import "./globals.css";

export const metadata = {
  title: "ФСП · Платформа подбора ИТ-специалистов",
  description: "Обратная механика подбора: кандидат подтверждает уровень тестом, работодатель приглашает первым",
  manifest: "/manifest.json",
  icons: { icon: "/icons/icon-192.png", apple: "/icons/icon-192.png" },
  themeColor: "#5e2b8e",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body
        className="antialiased"
      >
        {children}
      </body>
    </html>
  );
}
