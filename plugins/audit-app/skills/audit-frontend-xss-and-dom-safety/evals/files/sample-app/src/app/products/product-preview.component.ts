import { AfterViewInit, Component, ElementRef, Input, ViewChild } from '@angular/core';

export interface Product {
  id: number;
  name: string;
  description: string; // entered by tenant users in the product form
}

@Component({
  selector: 'app-product-preview',
  standalone: true,
  template: `
    <h3>{{ product.name }}</h3>
    <div #descriptionBox class="description"></div>
  `,
})
export class ProductPreviewComponent implements AfterViewInit {
  @Input() product!: Product;
  @ViewChild('descriptionBox') descriptionBox!: ElementRef<HTMLDivElement>;

  ngAfterViewInit(): void {
    // ISSUE (planted): raw innerHTML write with user data. Angular's sanitizer never
    // runs on this path; a description containing <img src=x onerror=...> executes.
    this.descriptionBox.nativeElement.innerHTML = this.product.description;
  }
}
