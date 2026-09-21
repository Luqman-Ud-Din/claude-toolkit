import { prisma } from "../../utils/db";

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, "id");
  const order = await prisma.order.findUnique({ where: { id } });
  if (!order) {
    throw createError({ statusCode: 404, statusMessage: "Order not found" });
  }
  return order;
});
