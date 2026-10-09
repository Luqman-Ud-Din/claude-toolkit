#!/usr/bin/env bash
# Builds the four test submissions under $1 (default: ./fixtures-build).
# Each gets docs/evaluator-expectations/ from evals/files/lenses/<name>/.
set -euo pipefail
OUT="${1:-./fixtures-build}"
HERE="$(cd "$(dirname "$0")" && pwd)"
LENSES="$HERE/lenses"
rm -rf "$OUT"; mkdir -p "$OUT"

lens() { mkdir -p "$1/docs/evaluator-expectations"; cp "$LENSES/$2"/*.md "$1/docs/evaluator-expectations/"; }
gitc() { # gitc <dir> <iso-date> <message>
  GIT_AUTHOR_DATE="$2" GIT_COMMITTER_DATE="$2" git -C "$1" add -A >/dev/null
  GIT_AUTHOR_DATE="$2" GIT_COMMITTER_DATE="$2" git -C "$1" -c user.name=dev -c user.email=dev@example.com commit -qm "$3"
}

############################################################################
# 1. promo-codes — code take-home, careful code, approval-only transcript
############################################################################
P="$OUT/promo-codes-submission"; mkdir -p "$P"; git -C "$P" init -q
lens "$P" promo-codes
cat > "$P/README.md" <<'EOF'
# Shopping app

Rails API in `backend/`, React Native app in `mobile/`. See `backend/README.md` and `mobile/README.md`.
EOF
mkdir -p "$P/backend/app/models" "$P/backend/app/services" "$P/backend/app/controllers" "$P/backend/db/migrate" "$P/backend/spec" "$P/mobile/src/screens"
cat > "$P/backend/README.md" <<'EOF'
# Backend
Ruby 3.2.2. `bundle install && rails db:migrate db:seed && rails server -b 0.0.0.0`.
EOF
cat > "$P/backend/app/models/order.rb" <<'EOF'
class Order < ApplicationRecord
  belongs_to :user
  has_many :line_items
  def subtotal_cents = line_items.sum { |li| li.unit_price_cents * li.quantity }
end
EOF
gitc "$P" "2026-10-06T18:02:00+05:00" "Initial app snapshot"

cat > "$P/backend/db/migrate/20261009180500_create_promo_codes.rb" <<'EOF'
class CreatePromoCodes < ActiveRecord::Migration[7.1]
  def change
    create_table :promo_codes do |t|
      t.string  :code, null: false
      t.string  :kind, null: false            # "percent" | "fixed"
      t.integer :value, null: false           # percent (1..100) or cents
      t.datetime :expires_at
      t.boolean :active, null: false, default: true
      t.integer :max_uses
      t.integer :uses_count, null: false, default: 0
      t.timestamps
    end
    add_index :promo_codes, "lower(code)", unique: true, name: "idx_promo_codes_lower_code"
    add_reference :carts, :promo_code, foreign_key: true, null: true
    add_column :orders, :promo_code_snapshot, :jsonb
    add_column :orders, :discount_cents, :integer, null: false, default: 0
  end
end
EOF
cat > "$P/backend/app/models/promo_code.rb" <<'EOF'
class PromoCode < ApplicationRecord
  KINDS = %w[percent fixed].freeze
  validates :code, presence: true
  validates :kind, inclusion: { in: KINDS }
  validates :value, numericality: { greater_than: 0 }
  validates :value, numericality: { less_than_or_equal_to: 100 }, if: -> { kind == "percent" }

  def self.find_by_code(raw) = where("lower(code) = ?", raw.to_s.strip.downcase).first

  def usable?(now: Time.current)
    active && (expires_at.nil? || expires_at > now) && (max_uses.nil? || uses_count < max_uses)
  end

  def discount_for(subtotal_cents)
    d = kind == "percent" ? (subtotal_cents * value / 100.0).round : value
    [d, subtotal_cents].min
  end
end
EOF
gitc "$P" "2026-10-06T18:41:00+05:00" "Add PromoCode model and migration"

cat > "$P/backend/app/services/apply_promo_code.rb" <<'EOF'
# Applies a promo code to a cart. Returns [ok, error_code].
class ApplyPromoCode
  ERRORS = { not_found: "We don't recognise that code", expired: "That code has expired",
             inactive: "That code isn't active", exhausted: "That code has been fully used" }.freeze

  def self.call(cart:, raw_code:)
    code = PromoCode.find_by_code(raw_code)
    return [false, :not_found] unless code
    return [false, :inactive] unless code.active
    return [false, :expired] if code.expires_at && code.expires_at <= Time.current
    return [false, :exhausted] if code.max_uses && code.uses_count >= code.max_uses
    cart.update!(promo_code: code)   # replaces any existing code: one per order
    [true, nil]
  end
end
EOF
cat > "$P/backend/app/services/checkout.rb" <<'EOF'
class Checkout
  # Re-validates the code at checkout and reserves a use atomically so two
  # concurrent checkouts cannot both consume the last use of a limited code.
  def self.call(cart:)
    ActiveRecord::Base.transaction do
      code = cart.promo_code&.lock!("FOR UPDATE")
      discount = 0
      snapshot = nil
      if code
        raise CheckoutError, ApplyPromoCode::ERRORS[:expired] unless code.usable?
        updated = PromoCode.where(id: code.id).where("max_uses IS NULL OR uses_count < max_uses")
                           .update_all("uses_count = uses_count + 1")
        raise CheckoutError, ApplyPromoCode::ERRORS[:exhausted] if updated.zero?
        discount = code.discount_for(cart.subtotal_cents)
        snapshot = { code: code.code, kind: code.kind, value: code.value, discount_cents: discount }
      end
      Order.create!(user: cart.user, line_items: cart.line_items, discount_cents: discount,
                    promo_code_snapshot: snapshot, total_cents: cart.subtotal_cents - discount)
    end
  end
end
EOF
cat > "$P/backend/app/controllers/promo_codes_controller.rb" <<'EOF'
class PromoCodesController < ApplicationController
  before_action :authenticate_user!
  def apply
    ok, err = ApplyPromoCode.call(cart: current_cart, raw_code: params[:code])
    return render json: { error: ApplyPromoCode::ERRORS[err] }, status: :unprocessable_entity unless ok
    render json: CartSerializer.new(current_cart.reload)
  end
  def remove
    current_cart.update!(promo_code: nil)
    render json: CartSerializer.new(current_cart)
  end
end
EOF
cat > "$P/backend/spec/apply_promo_code_spec.rb" <<'EOF'
require "rails_helper"
RSpec.describe ApplyPromoCode do
  it "is case-insensitive" do
    PromoCode.create!(code: "WELCOME10", kind: "percent", value: 10)
    ok, _ = described_class.call(cart: create(:cart), raw_code: " welcome10 ")
    expect(ok).to be true
  end
  it "rejects expired codes with a reason" do
    PromoCode.create!(code: "OLD", kind: "fixed", value: 500, expires_at: 1.day.ago)
    expect(described_class.call(cart: create(:cart), raw_code: "OLD")).to eq [false, :expired]
  end
end
RSpec.describe Checkout do
  it "does not let two checkouts consume the last use" do
    code = PromoCode.create!(code: "LAST", kind: "fixed", value: 500, max_uses: 1)
    carts = 2.times.map { create(:cart, promo_code: code) }
    results = carts.map { |c| Thread.new { Checkout.call(cart: c) rescue :failed } }.map(&:value)
    expect(results.count(:failed)).to eq 1
  end
end
EOF
gitc "$P" "2026-10-06T19:35:00+05:00" "Apply/remove endpoints, checkout snapshot, race-safe usage limit"

cat > "$P/backend/db/seeds.rb" <<'EOF'
PromoCode.create!(code: "WELCOME10", kind: "percent", value: 10)
PromoCode.create!(code: "FIVEOFF", kind: "fixed", value: 500)
PromoCode.create!(code: "EXPIRED", kind: "percent", value: 20, expires_at: 1.day.ago)
PromoCode.create!(code: "PAUSED", kind: "fixed", value: 300, active: false)
PromoCode.create!(code: "ONCE", kind: "fixed", value: 1000, max_uses: 1)
EOF
gitc "$P" "2026-10-06T20:10:00+05:00" "Seed promo codes"

cat > "$P/mobile/src/screens/CartScreen.tsx" <<'EOF'
// MOCKED: the apply call below hits a local stub, not the API. See SUBMISSION.md.
import React, { useState } from "react";
export function PromoBox({ onApply }: { onApply: (c: string) => Promise<{ error?: string }> }) {
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  return (
    <>
      <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="Promo code" />
      <button onClick={async () => { const r = await onApply(code); setErr(r.error ?? null); }}>Apply</button>
      {err && <p>{err}</p>}
    </>
  );
}
EOF
gitc "$P" "2026-10-06T20:48:00+05:00" "Mobile promo box (mocked)"

cat > "$P/SUBMISSION.md" <<'EOF'
# Submission — A. Dev — Backend

**Video walkthrough:** https://www.loom.com/share/placeholder-unlisted
**Time spent:** about 3 hours
**AI tools used:** Claude Code

## How to run what I added
`cd backend && bundle install && rails db:migrate db:seed && rails server -b 0.0.0.0`. Log in with the seeded user. `POST /cart/promo {code}` applies, `DELETE /cart/promo` removes.

## Promo codes to try
WELCOME10 (10% off), FIVEOFF ($5 off), EXPIRED, PAUSED, ONCE (single use).

## Decisions and assumptions
- Codes are matched case-insensitively.
- Percentage and fixed types are stored in one table with a `kind` column.
- The discount is snapshotted onto the order at checkout.
- Added a per-code usage limit (`max_uses`) with a race-safe decrement, since limited-use codes are common.

## What I didn't get to, and what I'd do next
The mobile screen is mocked rather than wired to the API because the Android build didn't complete. With more time I'd wire it up, add an admin UI for marketing, and add more tests.
EOF
cat > "$P/PROMPTS.md" <<'EOF'
# Prompts

Tools: Claude Code throughout. The AI was very helpful and produced most of the code. It got a couple of small things wrong (a wrong column name) which I corrected. I changed direction once on naming the service object.

## Session export

> Here is the take-home brief: [brief pasted]. Implement the promo codes feature in the Rails backend.

Claude: I'll start by looking at the existing models. I propose a `promo_codes` table with code, kind (percent/fixed), value, expires_at, active, and a cart→promo_code reference. Shall I proceed?

> ok

Claude: Created the migration and model. I added a unique index on lower(code) so lookups are case-insensitive. Next I'll add an ApplyPromoCode service that validates and attaches the code to the cart.

> continue

Claude: Done. I also added error messages for not found, expired, inactive. Should the service replace an existing code or reject a second one? I'd suggest replacing, since the brief says one code per order and shoppers may want to try another.

> yes do that

Claude: Implemented. Now checkout: I propose re-validating the code at checkout and snapshotting the discount onto the order so later edits to the code don't change history.

> looks good

Claude: I noticed a potential race if two checkouts use a limited code at once. I'll add a max_uses column and an atomic update_all guard inside the transaction.

> ok

Claude: Added, with a spec that runs two threads. Should I add seeds so you can try the codes?

> yes

Claude: Seeded five codes covering the paths. Moving to mobile — the Android build is failing on Gradle. I suggest mocking the apply call and marking it clearly.

> ok go ahead

Claude: Mobile PromoBox added with a MOCKED comment. I'll write SUBMISSION.md and PROMPTS.md now.

> I'd call the service ApplyPromoCode not PromoApplier

Claude: Renamed. Writing the notes.

> ok thanks
EOF
gitc "$P" "2026-10-06T21:40:00+05:00" "Submission notes and prompts"
git -C "$P" log --oneline | cat

############################################################################
# 2. dashboard-proposal — text proposal, fails the gate and the veto
############################################################################
D="$OUT/dashboard-proposal"; mkdir -p "$D"; lens "$D" dashboard-proposal
cat > "$D/proposal.md" <<'EOF'
Hi there!

I'm a senior full-stack developer with 8+ years of experience building data products for e-commerce brands. I've worked extensively with React, Next.js, Node, PostgreSQL, Supabase, dbt, Airbyte and AWS, and I've delivered several analytics dashboards for Shopify merchants.

For your dashboard I'd recommend a modern stack: Airbyte to sync Shopify, Meta Ads, Google Ads and Klaviyo into a Postgres warehouse, dbt for the transformation layer, and a custom Next.js frontend with Recharts for the visualisations. This gives you full flexibility and avoids the limitations of tools like Looker Studio.

The dashboard will show revenue, orders and AOV by day/week/month, ad spend and ROAS per channel, Klaviyo email revenue, top 10 products and refund rate — everything in your list — with filters and a date picker.

Timeline: I can have this live in 2 weeks.

Budget: $1,500 as posted.

Portfolio:
- https://example.com/portfolio/ecommerce-dashboard
- https://example.com/portfolio/saas-analytics
- https://example.com/portfolio/marketing-attribution

I'm available to start immediately and would love to discuss further on a call. Looking forward to working with you!

Best,
R.
EOF

############################################################################
# 3. fellowship — narrative (over limit, product-first) + budget.xlsx + sample
############################################################################
G="$OUT/fellowship-application"; mkdir -p "$G"; lens "$G" fellowship
python3 - "$G" <<'PY'
import sys, os
g=sys.argv[1]
para = lambda n, s: " ".join([s]*n)
narr = f"""# CivicPulse: An Open Data Platform for Neighbourhood Decision-Making

## The idea

Local decisions are made without local data. Residents' associations, tenants' groups and small community organisations lack the tools to collect, hold and interpret the information that affects them, and so decisions default to whoever has a consultant. CivicPulse is an open-source platform that changes this: a lightweight web application that lets any community group run surveys, map responses, and publish live dashboards without technical help. I have been designing it for two years alongside my consultancy work and have a working prototype.

## Why now

{para(7, "Municipal open-data portals have grown, but the data is published in formats that community groups cannot use, and the questions those portals answer are the city's questions, not the residents'. CivicPulse closes that gap by putting a simple collection and visualisation tool directly in the hands of groups, so that the data they gather is theirs to interpret.")}

## The community

The pilot community will be a neighbourhood in the east of the city where I have run two paid workshops for the council on data literacy. Several residents' groups attended and expressed interest in a tool like this. I would recruit three to five of these groups as pilot users of the platform, onboard them in the first two months, and gather usage data to refine the product.

## The question

Different groups will have different questions; the platform is designed to be question-agnostic. Example questions a group might ask include: where are the worst pavements, how long do repairs take, which streets flood. The fellowship would let me validate the platform across several such questions.

## Plan

{para(8, "Months one to three: finalise the prototype, deploy a hosted instance, and run onboarding workshops. Months four to nine: pilot groups collect data on their chosen questions, with fortnightly check-ins. Months ten to twelve: synthesise findings, publish a public report, open-source the codebase under a permissive licence, and present at two civic-tech conferences.")}

## Handover

At the end of the fellowship we will publish a report summarising what each group found, and the CivicPulse codebase will be open-sourced so that any community can deploy it. Pilot groups will keep access to the hosted instance for a further six months at no cost.

## What I will learn

{para(3, "I am a data consultant by trade. My work is commissioned by organisations with a clear brief, a budget, and a deadline. I have never built something whose users set the agenda. The fellowship would let me learn how to design with a community rather than for a client, and in particular how to hold back my own ideas about what the data should show.")}

## Budget summary

See budget.xlsx. $40,000 over 12 months: my time ($24,000), hosting and software ($9,000), participant stipends ($2,500), workshop costs ($2,500), travel and conferences ($2,000).

{para(8, "The platform's design principles are openness, simplicity and ownership: open because the code and the data formats are public, simple because a volunteer with a phone must be able to use it, and owned because each group's data lives in their own workspace.")}
"""
open(os.path.join(g,"narrative.md"),"w").write(narr)
print("narrative words:", len(narr.split()))
open(os.path.join(g,"work-sample.md"),"w").write("""# Work sample: Retail Footfall Dashboard

A dashboard built for a high-street business improvement district showing weekly footfall, dwell time and conversion against weather and events. Built in Metabase on top of a Postgres warehouse I designed. Delivered in 2025 and still in use by the BID's marketing team.

Screenshots: footfall-1.png, footfall-2.png
""")
import openpyxl
wb=openpyxl.Workbook(); ws=wb.active; ws.title="Budget"
rows=[("Category","Item","Amount (USD)"),
("Fellow time","12 months @ 40% FTE","24000"),
("Tools","Cloud hosting (12 months)","4200"),
("Tools","Mapping API and survey SaaS","3300"),
("Tools","Laptop upgrade","1500"),
("Participants","Stipends for pilot group leads","2500"),
("Workshops","Venue and catering (6 sessions)","2500"),
("Travel","Two conferences","2000"),
("","TOTAL","40000")]
for r in rows: ws.append(list(r))
# note: amounts typed as strings, total hardcoded — a finding
wb.save(os.path.join(g,"budget.xlsx"))
print("budget.xlsx written")
PY

############################################################################
# 4. rate-limiter — HALFWAY through; partial-mode fixture
############################################################################
R="$OUT/rate-limiter-halfway"; mkdir -p "$R"; git -C "$R" init -q
lens "$R" rate-limiter
cat > "$R/docker-compose.yml" <<'EOF'
services:
  redis:
    image: redis:7
    ports: ["6379:6379"]
EOF
cat > "$R/README.md" <<'EOF'
# Rate limiter

WIP. `docker compose up -d` then `python limiter.py`.
EOF
cat > "$R/limiter.py" <<'EOF'
import time, redis

LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count < limit then
  redis.call('ZADD', key, now, ARGV[4])
  redis.call('PEXPIRE', key, window)
  return 1
end
return 0
"""

class RateLimiter:
    def __init__(self, r: redis.Redis, limit: int, window_ms: int = 60_000):
        self.r, self.limit, self.window = r, limit, window_ms
        self.sha = r.script_load(LUA)

    def allow(self, key: str) -> bool:
        sec, usec = self.r.time()                      # Redis clock, not instance clock
        now_ms = sec * 1000 + usec // 1000
        member = f"{now_ms}-{id(self)}-{time.perf_counter_ns()}"
        return self.r.evalsha(self.sha, 1, f"rl:{key}", now_ms, self.window, self.limit, member) == 1
EOF
gitc "$R" "2026-10-07T09:05:00+05:00" "Sliding-log limiter in Lua, Redis TIME as clock"
cat > "$R/DESIGN.md" <<'EOF'
# Design

## Algorithm
Sliding log in a Redis sorted set, one member per admitted request, scored by Redis server time. Chosen over token bucket / GCRA because the brief's invariant is "never N+1 in any rolling 60-second window regardless of timing", and the rate-based algorithms admit up to ~2N across a window boundary after a burst; the log is exact. Memory is O(N) per key, acceptable at the stated limits.

## Race handling
The read-prune-count-add sequence runs inside one Lua script via EVALSHA, so it executes atomically on the Redis server; no two instances can interleave between the ZCARD and the ZADD. What it does not guarantee: durability across a Redis restart (the log is in memory), and consistency across an async replica failover.
EOF
gitc "$R" "2026-10-07T10:20:00+05:00" "DESIGN: algorithm choice and race handling"
git -C "$R" log --oneline | cat

echo; echo "Built under $OUT:"; ls "$OUT"
