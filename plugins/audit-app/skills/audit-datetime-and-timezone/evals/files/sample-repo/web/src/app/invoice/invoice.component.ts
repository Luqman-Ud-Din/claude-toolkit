import { Component, Input } from '@angular/core';

export interface InvoiceDto {
  id: number;
  // API sends "2024-03-10T14:30:00" (no offset) for this field
  dueDate: string;
  // API sends "2024-03-10T09:30:00Z" for this field
  createdAt: string;
}

@Component({
  selector: 'app-invoice',
  standalone: true,
  template: `
    <p>Due: {{ due | date:'dd/MM/yyyy HH:mm' }}</p>
    <p>Created: {{ created | date:'medium':'UTC' }} UTC</p>
  `,
})
export class InvoiceComponent {
  due!: Date;
  created!: Date;

  @Input() set invoice(value: InvoiceDto) {
    // ISSUE: dueDate has no offset, so new Date() treats it as browser-local.
    // A customer in Dubai and one in Karachi see different instants; the
    // "overdue" badge below flips an hour apart.
    this.due = new Date(value.dueDate);

    // Correct (negative case): createdAt carries a Z offset; parsing is unambiguous.
    this.created = new Date(value.createdAt);
  }

  get isOverdue(): boolean {
    return this.due.getTime() < Date.now();
  }
}
