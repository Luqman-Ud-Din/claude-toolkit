import { createCookieSessionStorage, redirect } from "@remix-run/node";

const storage = createCookieSessionStorage({
  cookie: { name: "__session", secrets: [process.env.SESSION_SECRET ?? ""], httpOnly: true },
});

export async function requireUserId(request: Request): Promise<string> {
  const session = await storage.getSession(request.headers.get("Cookie"));
  const userId = session.get("userId");
  if (!userId) {
    throw redirect("/login");
  }
  return userId;
}
