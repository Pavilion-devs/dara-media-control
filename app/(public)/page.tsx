import { redirect } from "next/navigation";

/**
 * The zero-spend Studio replay is Dara's judge entry point. The full product
 * story remains available at /about without putting a marketing step in front
 * of the working control plane.
 */
export default function HomePage() {
  redirect("/studio");
}
