import { redirect } from "next/navigation";

/** The first sign-in page lived here; it is now /login, with /signup beside it. Kept so old invite links work. */
export default async function SignInPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const params = await searchParams;
  const query = new URLSearchParams(Object.entries(params).filter((e): e is [string, string] => typeof e[1] === "string"));
  redirect(params.invite ? `/signup?${query}` : `/login${query.size ? `?${query}` : ""}`);
}
