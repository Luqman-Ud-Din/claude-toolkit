import { json, redirect, type ActionFunctionArgs, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { prisma } from "~/db.server";
import { requireUserId } from "~/session.server";

export async function loader({ params }: LoaderFunctionArgs) {
  const lines = await prisma.orderLine.findMany({ where: { orderId: params.id } });
  return json({ lines });
}

export async function action({ request, params }: ActionFunctionArgs) {
  const userId = await requireUserId(request);
  const form = await request.formData();
  const note = String(form.get("note") ?? "");
  await prisma.order.update({ where: { id: params.id, userId }, data: { note } });
  return redirect(`/orders/${params.id}`);
}

export default function OrderPage() {
  const { lines } = useLoaderData<typeof loader>();
  return (
    <ul>
      {lines.map((line) => (
        <li key={line.id}>{line.sku}</li>
      ))}
    </ul>
  );
}
