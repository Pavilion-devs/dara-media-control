import {
  BarChart3,
  FileCheck2,
  Images,
  ListOrdered,
  ShieldCheck,
  Wand2,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Also highlight for nested routes such as /assets/{id}. */
  prefix?: string;
};

/**
 * Operator surfaces. Only routes that exist are listed — a nav entry that 404s
 * is worse than a missing one. Runs joins when its page lands; share creation
 * belongs on the asset being shared rather than as a destination of its own,
 * since the API has no endpoint to list issued shares.
 */
export const appNav: NavItem[] = [
  { href: "/studio", label: "Studio", icon: Wand2 },
  { href: "/runs", label: "Runs", icon: ListOrdered },
  { href: "/assets/ast_nw_003", label: "Assets", icon: Images, prefix: "/assets" },
  { href: "/ledger", label: "Ledger", icon: BarChart3 },
  { href: "/policies", label: "Policies", icon: ShieldCheck },
];

/** Public trust surfaces — no operator chrome around these. */
export const publicNav: NavItem[] = [
  { href: "/verify", label: "Verify", icon: FileCheck2 },
];

export function isActive(pathname: string, item: NavItem) {
  if (item.prefix) return pathname.startsWith(item.prefix);
  return pathname === item.href;
}
