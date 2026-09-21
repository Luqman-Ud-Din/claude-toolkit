import { Request, Response } from 'express';
import { Product } from '../models/product.model';
import { InventoryService } from '../services/inventory.service';

const inventory = new InventoryService();

export async function list(_req: Request, res: Response) {
  res.json(await Product.query().where({ is_active: true }).orderBy('name'));
}

export async function lowStock(_req: Request, res: Response) {
  res.json(await inventory.lowStock());
}

export async function deactivate(req: Request, res: Response) {
  await Product.query().findById(Number(req.params.id)).patch({ is_active: false });
  res.status(204).end();
}
