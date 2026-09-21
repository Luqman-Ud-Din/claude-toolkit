import { DataSource } from 'typeorm';
export const AppDataSource = new DataSource({
  type: 'postgres',
  url: process.env.DATABASE_URL,
  ssl: false,
  entities: [__dirname + '/models/*.ts'],
});
