import { Component } from '@angular/core';
import { FormBuilder } from '@angular/forms';
import { ToastService } from '../core/toast.service';

@Component({
  selector: 'app-checkout',
  standalone: true,
  templateUrl: './checkout.component.html',
})
export class CheckoutComponent {
  form = this.fb.group({ name: [''], email: [''], phone: [''] });
  items: Array<{ id: number; price: number }> = [];
  confirmOpen = false;
  product = { image: '' };

  constructor(private fb: FormBuilder, private toast: ToastService) {}

  get total(): number {
    return this.items.reduce((s, i) => s + i.price, 0);
  }

  submit(): void {
    this.confirmOpen = true;
  }

  confirm(): void {
    const placedAt = new Date().toLocaleDateString();
    const summary = this.items.length + ' items';
    this.toast.show('Order placed on ' + placedAt + ' (' + summary + ', $' + this.total.toFixed(2) + ')');
    this.confirmOpen = false;
  }

  cancel(): void { this.confirmOpen = false; }
  applyCoupon(): void {}
  removeItem(): void {}
}
