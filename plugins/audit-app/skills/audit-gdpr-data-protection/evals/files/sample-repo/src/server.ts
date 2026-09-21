import express from 'express';
import usersRouter from './routes/users.routes';

const app = express();
app.use(express.json());
app.use('/api', usersRouter);
app.listen(3000);
