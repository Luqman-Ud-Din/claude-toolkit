import { Component, Input, OnChanges } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import DOMPurify from 'dompurify';

export interface HelpArticle {
  slug: string;
  html: string; // authored in the help CMS; may contain tables and headings
}

const ALLOWED_TAGS = ['p', 'b', 'i', 'strong', 'em', 'a', 'ul', 'ol', 'li', 'h2', 'h3', 'table', 'thead', 'tbody', 'tr', 'th', 'td'];
const ALLOWED_ATTR = ['href', 'title'];

@Component({
  selector: 'app-help-article',
  standalone: true,
  template: `<article [innerHTML]="safeHtml"></article>`,
})
export class HelpArticleComponent implements OnChanges {
  @Input() article!: HelpArticle;
  safeHtml: SafeHtml = '';

  constructor(private sanitizer: DomSanitizer) {}

  ngOnChanges(): void {
    // JUSTIFIED bypass (must be reported as Info, not High): Angular's default sanitizer
    // strips <table> styling the help centre needs, so we run DOMPurify with a fixed
    // allow-list on the same value immediately before trusting it.
    const clean = DOMPurify.sanitize(this.article.html, { ALLOWED_TAGS, ALLOWED_ATTR });
    this.safeHtml = this.sanitizer.bypassSecurityTrustHtml(clean);
  }
}
