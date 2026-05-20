"use client"
import { useEffect } from "react"
import { useRouter, usePathname } from "next/navigation"
import Link from "next/link"
import { Providers } from "@/app/providers"

const NAV = [
  { href: "/dashboard",  label: "Dashboard" },
  { href: "/review",     label: "Revisión"  },
  { href: "/campaigns",  label: "Campañas"  },
]

function Sidebar() {
  const pathname = usePathname()
  const router   = useRouter()

  function logout() {
    localStorage.removeItem("boids_token")
    router.push("/login")
  }

  return (
    <aside className="w-52 shrink-0 border-r bg-card flex flex-col">
      <div className="px-5 py-4 border-b">
        <span className="font-semibold text-sm">Boids AI</span>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {NAV.map(item => (
          <Link
            key={item.href}
            href={item.href}
            className={`block rounded-lg px-3 py-2 text-sm transition-colors ${
              pathname === item.href
                ? "bg-primary/10 text-primary font-medium"
                : "text-muted-foreground hover:bg-muted"
            }`}
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="p-3 border-t">
        <button
          onClick={logout}
          className="w-full rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted text-left"
        >
          Cerrar sesión
        </button>
      </div>
    </aside>
  )
}

function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter()

  useEffect(() => {
    if (!localStorage.getItem("boids_token")) {
      router.replace("/login")
    }
  }, [router])

  return <>{children}</>
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <AuthGuard>
        <div className="flex h-screen overflow-hidden bg-background">
          <Sidebar />
          <main className="flex-1 overflow-y-auto">
            {children}
          </main>
        </div>
      </AuthGuard>
    </Providers>
  )
}
