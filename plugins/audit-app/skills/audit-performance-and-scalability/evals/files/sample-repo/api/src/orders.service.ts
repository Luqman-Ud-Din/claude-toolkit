import axios from 'axios';

const customersClient = axios.create({ baseURL: process.env.CUSTOMERS_URL, timeout: 3000 });
const pricingClient = axios.create({ baseURL: process.env.PRICING_URL, timeout: 3000 });
const taxClient = axios.create({ baseURL: process.env.TAX_URL, timeout: 3000 });
const stockClient = axios.create({ baseURL: process.env.STOCK_URL, timeout: 3000 });

export interface OrderDto { customerId: string; region: string; items: { sku: string; qty: number }[] }

export class OrdersService {
  // PERF (SEQ): three independent upstream calls awaited one after another.
  // Each is ~250 ms; the request pays ~750 ms instead of ~250 ms.
  async create(dto: OrderDto) {
    const customer = await customersClient.get(`/customers/${dto.customerId}`);
    const quote = await pricingClient.post('/quotes', { items: dto.items });
    const tax = await taxClient.get(`/rates/${dto.region}`);
    return { customer: customer.data.name, total: quote.data.total * (1 + tax.data.rate) };
  }

  // OK: independent calls run concurrently - must NOT be flagged as sequential.
  async availability(orderId: string) {
    const [stock, eta] = await Promise.all([
      stockClient.get(`/stock/${orderId}`),
      stockClient.get(`/eta/${orderId}`),
    ]);
    return { inStock: stock.data.available, eta: eta.data.days };
  }
}
