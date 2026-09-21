import { Component, Input, OnInit } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

export interface Comment {
  id: number;
  authorId: number;
  body: string; // free text typed by any user, stored on the server
}

@Component({
  selector: 'app-comment',
  standalone: true,
  template: `<div class="comment" [innerHTML]="safeBody"></div>`,
})
export class CommentComponent implements OnInit {
  @Input() comment!: Comment;
  safeBody: SafeHtml = '';

  constructor(private sanitizer: DomSanitizer) {}

  ngOnInit(): void {
    // ISSUE (planted, unjustified): comment.body is user-typed, stored, shown to every
    // user who opens the thread, and nothing sanitizes it before the bypass.
    this.safeBody = this.sanitizer.bypassSecurityTrustHtml(this.comment.body);
  }
}
