import type { Metadata } from "next";
import { DM_Mono, Manrope } from "next/font/google";
import "./globals.css";

const sans = Manrope({ variable: "--font-sans", subsets: ["latin"] });
const mono = DM_Mono({ variable: "--font-mono", weight: ["400", "500"], subsets: ["latin"] });

export const metadata: Metadata = {
  title: "NYC Taxi Intelligence — Data Product Case Study",
  description: "From 100M+ taxi records to an auditable urban demand decision system.",
  openGraph: {
    title: "NYC Taxi Intelligence",
    description: "A governed NYC taxi data product: engineering, evidence, forecasting, and safe operations.",
    type: "website",
    images: [{ url: "/og.png", width: 1536, height: 1024, alt: "NYC Taxi Intelligence" }],
  },
  twitter: { card: "summary_large_image", images: ["/og.png"] },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${sans.variable} ${mono.variable}`}>{children}</body>
    </html>
  );
}
