import { Analytics } from '@segment/analytics-node';
import * as bcrypt from 'bcrypt';
import { AppDataSource } from '../data-source';
import { User } from '../models/user.model';
import { logger } from '../logger';

const analytics = new Analytics({ writeKey: process.env.SEGMENT_WRITE_KEY! });

export class UserService {
  private repo = AppDataSource.getRepository(User);

  async register(body: any): Promise<User> {
    const user = this.repo.create({
      email: body.email,
      phone: body.phone,
      firstName: body.firstName,
      lastName: body.lastName,
      passwordHash: await bcrypt.hash(body.password, 12),
      marketingConsent: body.marketingConsent === true,
    });
    await this.repo.save(user);

    logger.info(`Created user ${user.email} (${user.firstName} ${user.lastName})`);

    analytics.identify({
      userId: user.id,
      traits: { email: user.email, firstName: user.firstName, marketingConsent: user.marketingConsent },
    });

    return user;
  }

  async findById(id: string) {
    logger.debug(`Lookup user ${id}`);
    return this.repo.findOneBy({ id });
  }

  async update(id: string, body: any) {
    await this.repo.update({ id }, { firstName: body.firstName, lastName: body.lastName, phone: body.phone });
    return this.repo.findOneBy({ id });
  }

  async revokeSession(token: string) {
    // sessions live in Redis; unrelated to personal data erasure
  }
}
