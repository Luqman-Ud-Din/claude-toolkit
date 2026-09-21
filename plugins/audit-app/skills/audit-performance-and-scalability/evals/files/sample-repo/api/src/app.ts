import express from 'express';
import session from 'express-session';
import { productsRouter } from './products.routes';
import { ordersRouter } from './orders.routes';

const app = express();
app.use(express.json());

// PERF (STATE): default MemoryStore - session lives in this process only; a second
// instance (or a restart) logs everyone out. No `store:` option.
app.use(session({ secret: process.env.SESSION_SECRET || 'dev', resave: false, saveUninitialized: false, cookie: { secure: true } }));

// PERF (COMPRESS): no compression() middleware anywhere - JSON lists go out uncompressed.

app.use('/api', productsRouter);
app.use('/api', ordersRouter);

app.listen(3000);
