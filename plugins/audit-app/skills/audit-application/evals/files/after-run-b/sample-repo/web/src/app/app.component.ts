import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: '<main><h1>Inventory</h1><router-outlet /></main>',
})
export class AppComponent {}
