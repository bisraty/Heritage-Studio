import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Heritage Studio",
  description: "Turn treasured family memories into short films.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
