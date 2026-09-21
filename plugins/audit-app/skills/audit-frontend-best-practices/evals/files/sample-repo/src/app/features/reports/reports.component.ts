import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import * as _ from 'lodash';
import moment from 'moment';
import { ReportsService } from './reports.service';

@Component({
  selector: 'app-reports',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './reports.component.html',
})
export class ReportsComponent implements OnInit {
  rows: any[] = [];
  generatedAt = moment().format('LLL');

  constructor(private reports: ReportsService) {}

  ngOnInit(): void {
    this.reports.list().subscribe((data: any) => {
      // @ts-ignore
      this.rows = _.sortBy(data, 'name');
    });
  }
}
