import express from 'express';
import Knex from 'knex';
import { Model } from 'objection';
import { ordersRouter } from './routes/orders.routes';
import { catalogRouter } from './routes/catalog.routes';
import { requireApiKey } from './middleware/auth';

const knex = Knex(require('../knexfile'));
Model.knex(knex);

const app = express();
app.use(express.json());
app.use(requireApiKey);
app.use('/orders', ordersRouter);
app.use('/', catalogRouter);
app.use((err: any, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  console.error(err);
  res.status(err.name === 'ZodError' ? 400 : 500).json({ error: err.message });
});

app.listen(3000, () => console.log('orderly listening on 3000'));
