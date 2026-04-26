import type { Metadata, Viewport } from "next";
import { InstallPrompt } from "@/ui/overlays/InstallPrompt";
import { PwaUpdater } from "@/ui/overlays/PwaUpdater";
import { RunningNotification } from "@/ui/overlays/RunningNotification";
import { Navigation } from "@/ui/layout/Navigation";
import { Toaster } from "@/ui/overlays/Toaster";
import "./globals.css";

export const metadata: Metadata = {
  title: "Orca",
  description: "Platform streaming anime premium minimalis — cepat, elegan, gratis.",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Orca",
  },
};

export const viewport: Viewport = {
  themeColor: "#000000",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" className="h-full">
      <body className="min-h-full bg-black text-white flex flex-col">
        <RunningNotification />
        <div className="flex-1 relative">
          <Navigation>
            {children}
          </Navigation>
        </div>
        <Toaster />
        <InstallPrompt />
        <PwaUpdater />
      </body>
    </html>
  );
}

