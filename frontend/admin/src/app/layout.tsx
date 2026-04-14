import "./globals.css";
import type { Metadata } from "next";

import ProtectedAdminRoute from "@/components/ProtectedAdminRoute";
import ReactQueryProvider from "@/components/ReactQueryProvider";
import { AdminSessionProvider } from "@/hooks/useAdminSession";

export const metadata: Metadata = {
  title: "BizMoneyAI Admin",
  description: "Admin frontend for BizMoneyAI",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <ReactQueryProvider>
          <AdminSessionProvider>
            <ProtectedAdminRoute>{children}</ProtectedAdminRoute>
          </AdminSessionProvider>
        </ReactQueryProvider>
      </body>
    </html>
  );
}
