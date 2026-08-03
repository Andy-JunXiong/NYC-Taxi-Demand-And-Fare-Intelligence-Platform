import type { Metadata } from "next";
import { DM_Mono, Manrope } from "next/font/google";
import { headers } from "next/headers";
import "./globals.css";

const sans = Manrope({ variable: "--font-sans", subsets: ["latin"] });
const mono = DM_Mono({ variable: "--font-mono", weight: ["400", "500"], subsets: ["latin"] });

const fallbackOrigin = "https://nyc-taxi-intelligence.maki83794676.chatgpt.site";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const forwardedHost = requestHeaders.get("x-forwarded-host")?.split(",")[0]?.trim();
  const requestHost = forwardedHost ?? requestHeaders.get("host");
  const forwardedProtocol = requestHeaders.get("x-forwarded-proto")?.split(",")[0]?.trim();
  const protocol = forwardedProtocol === "http" ? "http" : "https";
  const safeHost = requestHost && /^[a-z0-9.-]+(?::\d+)?$/i.test(requestHost) ? requestHost : null;
  const origin = safeHost ? `${protocol}://${safeHost}` : fallbackOrigin;
  const imageUrl = new URL("/og.png", origin).toString();

  return {
    metadataBase: new URL(origin),
    title: "NYC Taxi Intelligence — Data Product Case Study",
    description: "From 100M+ taxi records to an auditable urban demand decision system.",
    openGraph: {
      title: "NYC Taxi Intelligence",
      description: "A governed NYC taxi data product: engineering, evidence, forecasting, and safe operations.",
      type: "website",
      url: origin,
      images: [{ url: imageUrl, width: 1536, height: 1024, alt: "NYC Taxi Intelligence" }],
    },
    twitter: { card: "summary_large_image", images: [imageUrl] },
  };
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${sans.variable} ${mono.variable}`}>{children}</body>
    </html>
  );
}
