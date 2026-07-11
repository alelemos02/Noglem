import type { MetadataRoute } from "next"
import { site } from "@/lib/site"

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/dashboard", "/api", "/sign-in", "/sign-up", "/verify-invite"],
    },
    sitemap: `${site.url}/sitemap.xml`,
  }
}
