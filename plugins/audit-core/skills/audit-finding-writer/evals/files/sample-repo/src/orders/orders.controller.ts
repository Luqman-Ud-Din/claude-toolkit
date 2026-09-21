import { Controller, Get, Param, UseGuards } from '@nestjs/common';
import { AuthGuard } from '../auth/auth.guard';
import { OrdersRepository } from './orders.repository';

@Controller('api/orders')
@UseGuards(AuthGuard)
export class OrdersController {
  constructor(private readonly repo: OrdersRepository) {}

  @Get()
  listOrders() {
    return this.repo.find(); // returns every row, no take/skip, no filter
  }

  @Get(':id')
  getOrder(@Param('id') id: string) {
    return this.repo.findOne({ where: { id } });
  }
}
