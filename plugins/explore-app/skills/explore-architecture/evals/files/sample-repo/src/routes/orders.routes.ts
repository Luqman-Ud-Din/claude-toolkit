import { Router } from 'express';
import * as orders from '../controllers/orders.controller';
import * as shipments from '../controllers/shipments.controller';

export const ordersRouter = Router();
ordersRouter.get('/', orders.list);
ordersRouter.post('/', orders.create);
ordersRouter.post('/:id/confirm', orders.confirm);
ordersRouter.post('/:id/pay', orders.pay);
ordersRouter.post('/:id/cancel', orders.cancel);
ordersRouter.post('/:id/ship', shipments.ship);
ordersRouter.post('/:id/deliver', shipments.deliver);
