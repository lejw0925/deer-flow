import "@/styles/globals.css";

import { type Metadata, type Viewport } from "next";

import { ThemeProvider } from "@/components/theme-provider";
import { DEFAULT_LOCALE } from "@/core/i18n/locale";

export const metadata: Metadata = {
  title: "DeerFlow",
  description: "A LangChain-based framework for building super agents.",
};

// Viewport configuration. ``viewport-fit=cover`` is required to make
// ``env(safe-area-inset-*)`` return non-zero values on iPhone notch /
// Dynamic Island devices. ``interactive-widget=resizes-content`` asks
// Chromium to shrink the layout viewport when the virtual keyboard opens
// so ``dvh`` / ``100dvh`` measurements reflect the available area
// (iOS Safari ignores this directive — we cover that case in JS via the
// visualViewport API, see src/hooks/use-visual-viewport.ts).
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang={DEFAULT_LOCALE}
      suppressContentEditableWarning
      suppressHydrationWarning
    >
      <body>
        <ThemeProvider attribute="class" enableSystem disableTransitionOnChange>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
