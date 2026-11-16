import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { AdminConsole } from "@/components/AdminConsole";
import { pageMetadata } from "@/lib/site";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("admin");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/admin",
  });
}

export default function AdminPage() {
  return <AdminConsole />;
}
