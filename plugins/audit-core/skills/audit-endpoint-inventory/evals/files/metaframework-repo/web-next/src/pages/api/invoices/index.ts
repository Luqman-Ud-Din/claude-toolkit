import type { NextApiRequest, NextApiResponse } from "next";
import { z } from "zod";
import { prisma } from "../../../lib/db";

const CreateInvoice = z.object({ companyId: z.string(), total: z.number() });

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method === "GET") {
    const companyId = req.query.companyId as string;
    const invoices = await prisma.invoice.findMany({ where: { companyId } });
    return res.status(200).json(invoices);
  }
  if (req.method === "POST") {
    const input = CreateInvoice.parse(req.body);
    const invoice = await prisma.invoice.create({ data: input });
    return res.status(201).json(invoice);
  }
  res.setHeader("Allow", ["GET", "POST"]);
  return res.status(405).json({ error: "method not allowed" });
}
