"use server";

import { getServerSession } from "next-auth";
import { revalidatePath } from "next/cache";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/db";

export async function cancelOrder(orderId: string) {
  const session = await getServerSession(authOptions);
  if (!session) {
    throw new Error("unauthorized");
  }
  await prisma.order.update({ where: { id: orderId, userId: session.user.id }, data: { status: "cancelled" } });
  revalidatePath("/orders");
}
