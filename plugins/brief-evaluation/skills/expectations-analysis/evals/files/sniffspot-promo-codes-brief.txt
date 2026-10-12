Sniffspot Take-Home: Promo Codes
Thanks for taking this on! This repo is a small shopping app: a Rails API in backend/ and a React Native (TypeScript) app in mobile/. It's meant to let shoppers sign in, browse products, manage a cart, check out, and see their order history.
Your job is to add one feature, the same way you would on a real product team.

The feature: promo codes
Why we want it
Promotions are one of our best tools for bringing people back. Examples: a welcome discount on a first order, a seasonal sale, or a make-good code from customer support when something goes wrong. Right now the app has no way to offer a discount, and marketing wants to start running promotions next month.
What shoppers need

A signed-in shopper can enter a promo code on their cart.
If the code works, they see the discount and their new total before they check out.
If it doesn't work, they understand why and can try a different code.
When they check out, the order reflects what they actually paid, and so does their order history.

What marketing needs

Some codes take a percentage off and others take a fixed amount off.
A code can have an end date, and marketing needs to be able to switch a code off early.
Only one code can be used per order.
Marketing will eventually want to create and manage codes themselves. For this exercise, it's enough to give us a way to try out a few working codes. How you do that is up to you.

What we're leaving to you
This is a product brief, not a spec, on purpose. There are plenty of things it doesn't cover. Wherever that happens, make the decision you'd make if this were shipping to real customers, then tell us what you decided and why. We don't have a hidden checklist of right answers. What we care about is how you reason.

How to work

Timebox: about 2–3 hours of hands-on work. Writing notes and recording the video don't count toward that. Please don't go much over. Deciding what fits in the time is part of the exercise, so tell us what you'd do next if you had more.
Use AI. We expect it, because that's how our team works. Any tools are fine (Claude, Cursor, Copilot, ChatGPT, and so on). We're interested in how you direct them, not in whether you used them.
If the mobile setup fights you, don't spend your timebox on Xcode or Gradle. A working backend plus a mobile layer that's clearly marked as mocked is better than a half-configured build. Just tell us what you did.
Treat it like an existing codebase. We don't promise that everything runs cleanly out of the box. If you run into something that's broken, fix it or work around it, and tell us what you found and what you did about it.
Applying for the Backend role? Focus on the backend and do as much of the mobile side as you can. We'll take the role into account when we review, so just tell us what you didn't get to.
Commit as you go. Your real history is more useful to us than one squashed commit.


Getting started
Backend (Ruby 3.2.2):
cd backend
bundle install
rails db:migrate db:seed
rails server -b 0.0.0.0
Mobile:
cd mobile
npm install
cp .env.example .env    # set API_URL; on a physical device, use your computer's IP instead of localhost
# iOS
cd ios && bundle install && bundle exec pod install && cd ..
npx react-native run-ios
# Android
npx react-native run-android
Seeded login: test@example.com / password123
backend/README.md and mobile/README.md have more detail.

What to send us
Everything goes in one private GitLab repo. When you're done, reply to our message on Wellfound with the repo link. That's your whole submission.


Your code. Push your work, commits and all, to a private GitLab repo and add @pbhepworth, @skulikov112, and @mshmykov as members with the Reporter role (Project → Manage → Members). If you normally use GitHub, GitLab can import a GitHub repo in a couple of clicks. Please don't publish your solution anywhere public.


PROMPTS.md, all of the AI prompts you used to build this. If your tool can export the whole session (for example Claude Code's /export, Cursor's chat export, or a ChatGPT share link), include that export. We'd rather see the raw session than a cleaned-up one. At the top, add a few lines covering which tools you used, the moments where the AI got something wrong, and the places where you changed direction.


A 5–10 minute video walkthrough. Screen plus voice is plenty, and the camera is optional. First show the feature working. Then walk us through what you built and why: your key decisions, the trade-offs you made, what you chose not to do, and anything else a reviewer should know. Upload it somewhere with an unlisted link (Loom, unlisted YouTube, Google Drive, S3, or similar) and put the link in SUBMISSION.md.


SUBMISSION.md, a short note at the root of the repo. You can start from this:
# Submission — <your name> — <Mobile | Backend>

**Video walkthrough:** <link>
**Time spent:** <roughly, and on what>
**AI tools used:** <list>

## How to run what I added
## Promo codes to try
## Decisions and assumptions
## What I didn't get to, and what I'd do next



What happens next
We'll confirm we've received your submission within one business day. We review every submission, usually within 3 business days, and we'll let you know the outcome either way. If it's a good fit, we'll invite you to a live technical interview with our engineers. There we may go through your submission together and answer any outstanding questions about your solution. Expect questions about your decisions and your prompts, and we may extend the feature together.
Questions? If you have a question about setup or logistics, reply to our message on Wellfound. If you have a question about the product, make the call you'd make and write it down. That's part of the exercise.