import { Router } from 'express';
import * as products from '../controllers/products.controller';
import * as customers from '../controllers/customers.controller';

export const catalogRouter = Router();
catalogRouter.get('/products', products.list);
catalogRouter.get('/products/low-stock', products.lowStock);
catalogRouter.post('/products/:id/deactivate', products.deactivate);
catalogRouter.post('/customers', customers.create);
