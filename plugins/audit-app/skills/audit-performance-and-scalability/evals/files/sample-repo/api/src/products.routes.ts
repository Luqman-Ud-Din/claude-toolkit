import { Router } from 'express';
import { PrismaClient } from '@prisma/client';

export const productsRouter = Router();
const prisma = new PrismaClient();

// PERF (PAYLOAD + UNBOUNDED): full entities, every column incl. description and image blobs,
// no select, no take - and app.ts has no compression, so the whole thing goes out raw.
productsRouter.get('/products', async (req, res) => {
  res.json(await prisma.product.findMany({ where: { companyId: Number(req.query.companyId) } }));
});

// OK: paged, projected - must NOT be flagged.
productsRouter.get('/products/summary', async (req, res) => {
  const page = Number(req.query.page ?? 1);
  const take = Math.min(Number(req.query.pageSize ?? 20), 100);
  const items = await prisma.product.findMany({
    where: { companyId: Number(req.query.companyId) },
    select: { id: true, name: true, price: true },
    orderBy: { name: 'asc' },
    skip: (page - 1) * take,
    take,
  });
  res.set('Cache-Control', 'private, max-age=60');
  res.json({ page, items });
});
