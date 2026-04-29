from __future__ import annotations

import csv
import random
import string
from pathlib import Path

OUTPUT_PATH = Path(__file__).resolve().parent / "training_data.csv"
RANDOM_SEED = 42
ROWS_PER_CATEGORY = 500

NOISE_TERMS = [
    "card purchase",
    "POS",
    "online payment",
    "invoice",
    "subscription",
    "refund",
    "transfer",
    "recurring",
    "manual entry",
    "ACH",
    "bank card",
    "mobile pay",
]

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "sep", "oct", "nov", "dec"]
REFERENCES = ["ref", "txn", "auth", "inv", "card", "batch", "order"]

RANDOM_MERCHANT_ROOTS = [
    "northstar",
    "bluebird",
    "summit",
    "riverstone",
    "brightline",
    "metro",
    "harbor",
    "clearview",
    "evergreen",
    "solid oak",
    "silverline",
    "atlas",
    "cobalt",
    "redwood",
    "lighthouse",
]

RANDOM_MERCHANT_SUFFIXES = [
    "llc",
    "group",
    "co",
    "services",
    "market",
    "solutions",
    "partners",
    "systems",
    "hub",
]

ABBREVIATIONS = {
    "payment": ["pmt", "paymt"],
    "invoice": ["inv", "invoice"],
    "monthly": ["mo", "monthly"],
    "subscription": ["sub", "subs"],
    "professional": ["pro"],
    "transportation": ["transport"],
    "advertising": ["ads", "ad"],
    "campaign": ["campgn"],
    "services": ["svc", "svcs"],
    "supplies": ["supply", "supplies"],
    "software": ["sw", "software"],
}

CATEGORY_CONFIG: dict[str, dict[str, list[str]]] = {
    "Shopping": {
        "merchants": [
            "Amazon",
            "Walmart",
            "Target",
            "Costco",
            "Best Buy",
            "IKEA",
            "Home Depot",
            "eBay",
            "Etsy",
            "local store",
            "marketplace seller",
        ],
        "objects": [
            "online order",
            "retail purchase",
            "store pickup",
            "checkout",
            "electronics",
            "furniture",
            "misc supplies",
            "replacement parts",
            "bulk order",
        ],
        "contexts": [
            "for office setup",
            "general purchase",
            "small equipment",
            "client materials",
            "stock up",
            "quick run",
        ],
    },
    "Food & Dining": {
        "merchants": [
            "Starbucks",
            "DoorDash",
            "Uber Eats",
            "Subway",
            "local cafe",
            "pizza place",
            "restaurant",
            "catering company",
            "coffee shop",
            "bakery",
            "deli counter",
        ],
        "objects": [
            "team lunch",
            "client dinner",
            "coffee",
            "breakfast meeting",
            "meal delivery",
            "office snacks",
            "catering order",
            "working lunch",
            "refreshments",
        ],
        "contexts": [
            "with client",
            "for team meeting",
            "after sales call",
            "during travel day",
            "late meeting",
            "staff event",
        ],
    },
    "Transportation": {
        "merchants": [
            "Uber",
            "Lyft",
            "Shell",
            "Exxon",
            "airport parking",
            "metro station",
            "taxi service",
            "train station",
            "parking garage",
            "toll authority",
            "rental car desk",
        ],
        "objects": [
            "airport ride",
            "gas fill up",
            "parking fee",
            "train ticket",
            "bus pass",
            "taxi ride",
            "toll payment",
            "rental car",
            "client commute",
        ],
        "contexts": [
            "to meeting",
            "airport trip",
            "client visit",
            "downtown",
            "business travel",
            "late pickup",
        ],
    },
    "Utilities": {
        "merchants": [
            "electric company",
            "water utility",
            "internet provider",
            "mobile carrier",
            "gas company",
            "trash service",
            "broadband provider",
            "phone company",
            "power service",
            "sewer utility",
            "fiber provider",
        ],
        "objects": [
            "electric bill",
            "water bill",
            "internet service",
            "phone plan",
            "gas utility charge",
            "trash pickup",
            "broadband bill",
            "utility payment",
            "service charge",
        ],
        "contexts": [
            "monthly office bill",
            "service period",
            "metered usage",
            "account payment",
            "automatic debit",
            "late fee included",
        ],
    },
    "Rent": {
        "merchants": [
            "property manager",
            "office landlord",
            "warehouse owner",
            "coworking space",
            "storage facility",
            "commercial lease",
            "studio landlord",
            "parking space owner",
            "business center",
            "rental property",
            "suite management",
        ],
        "objects": [
            "office rent",
            "monthly lease",
            "warehouse rent",
            "coworking rent",
            "storage unit rent",
            "rent payment",
            "commercial space",
            "facility rent",
            "office lease",
        ],
        "contexts": [
            "april payment",
            "monthly payment",
            "lease invoice",
            "due today",
            "suite charge",
            "space rental",
        ],
    },
    "Software": {
        "merchants": [
            "GitHub",
            "Slack",
            "Adobe",
            "Google Workspace",
            "Microsoft 365",
            "Zoom",
            "Figma",
            "Notion",
            "Dropbox",
            "AWS",
            "Vercel",
            "QuickBooks",
        ],
        "objects": [
            "software subscription",
            "cloud bill",
            "team license",
            "hosting charge",
            "design tool",
            "developer tool",
            "productivity app",
            "CRM software",
            "SaaS renewal",
        ],
        "contexts": [
            "monthly plan",
            "seat renewal",
            "workspace billing",
            "cloud usage",
            "pro account",
            "team upgrade",
        ],
    },
    "Marketing": {
        "merchants": [
            "Facebook Ads",
            "Meta",
            "Google Ads",
            "Instagram",
            "LinkedIn Ads",
            "Mailchimp",
            "HubSpot",
            "SEO agency",
            "print shop",
            "trade show",
            "sponsorship platform",
        ],
        "objects": [
            "ads campaign",
            "paid promotion",
            "email marketing",
            "social media ads",
            "PPC campaign",
            "brand design",
            "flyer printing",
            "content marketing",
            "lead generation",
        ],
        "contexts": [
            "campaign invoice",
            "monthly ad spend",
            "launch promo",
            "audience test",
            "retargeting",
            "sponsored post",
        ],
    },
    "Office Supplies": {
        "merchants": [
            "Office Depot",
            "Staples",
            "printer supplier",
            "paper vendor",
            "cleaning supplier",
            "desk store",
            "stationery shop",
            "kitchen supply store",
            "furniture outlet",
            "equipment supplier",
            "ink warehouse",
        ],
        "objects": [
            "printer paper",
            "ink cartridges",
            "desk accessories",
            "notebooks",
            "pens and pencils",
            "office chairs",
            "cleaning supplies",
            "monitor stand",
            "toner refill",
        ],
        "contexts": [
            "office restock",
            "supply cabinet",
            "front desk",
            "admin area",
            "printer room",
            "staff supplies",
        ],
    },
    "Professional Services": {
        "merchants": [
            "law firm",
            "accounting firm",
            "tax preparer",
            "business consultant",
            "IT support",
            "freelance designer",
            "payroll provider",
            "compliance advisor",
            "financial advisor",
            "web developer",
            "HR consultant",
        ],
        "objects": [
            "legal consultation",
            "accounting services",
            "tax preparation",
            "consulting fee",
            "IT support",
            "design invoice",
            "payroll service",
            "compliance review",
            "advisor fee",
        ],
        "contexts": [
            "monthly retainer",
            "project invoice",
            "expert review",
            "support contract",
            "client project",
            "professional fee",
        ],
    },
    "Income": {
        "merchants": [
            "client",
            "customer",
            "marketplace payout",
            "stripe payout",
            "retainer client",
            "wholesale buyer",
            "partner",
            "course platform",
            "affiliate network",
            "sponsor",
            "invoice portal",
        ],
        "objects": [
            "invoice payment received",
            "product sale",
            "service revenue",
            "consulting income",
            "monthly retainer income",
            "project milestone payment",
            "subscription revenue",
            "commission earned",
            "deposit received",
        ],
        "contexts": [
            "paid invoice",
            "incoming transfer",
            "client payment",
            "settlement batch",
            "revenue deposit",
            "customer paid",
        ],
    },
}

AMBIGUOUS_EXAMPLES: dict[str, list[str]] = {
    "Shopping": [
        "online payment for replacement parts",
        "card purchase general supplies",
        "refund from marketplace order",
    ],
    "Food & Dining": [
        "grabbed coffee for client meeting",
        "POS cafe charge during airport wait",
        "refund for catering deposit",
    ],
    "Transportation": [
        "uber airport ride",
        "card purchase at station kiosk",
        "transfer to toll account",
    ],
    "Utilities": [
        "online payment monthly service bill",
        "subscription internet account charge",
        "refund from utility provider",
    ],
    "Rent": [
        "office lease april payment",
        "transfer for monthly space",
        "invoice from property account",
    ],
    "Software": [
        "monthly aws cloud bill",
        "subscription workspace renewal",
        "online payment for team seats",
    ],
    "Marketing": [
        "paid meta campaign invoice",
        "transfer for sponsored post",
        "subscription email campaign tool",
    ],
    "Office Supplies": [
        "printer ink and paper",
        "POS toner refill and notebooks",
        "card purchase admin supplies",
    ],
    "Professional Services": [
        "invoice for advisory review",
        "transfer to legal consultant",
        "subscription support contract",
    ],
    "Income": [
        "client invoice payment received",
        "transfer from customer account",
        "refund payout from marketplace sale",
    ],
}


def _random_reference(rng: random.Random) -> str:
    prefix = rng.choice(REFERENCES)
    if rng.random() < 0.5:
        value = "".join(rng.choices(string.ascii_uppercase + string.digits, k=rng.randint(4, 8)))
    else:
        value = str(rng.randint(1000, 999999))
    return f"{prefix} {value}"


def _random_merchant(rng: random.Random) -> str:
    root = rng.choice(RANDOM_MERCHANT_ROOTS)
    suffix = rng.choice(RANDOM_MERCHANT_SUFFIXES)
    if rng.random() < 0.35:
        return f"{root} {suffix}".upper()
    if rng.random() < 0.5:
        return f"{root.title()} {suffix.title()}"
    return f"{root} {suffix}"


def _apply_abbreviations(rng: random.Random, text: str) -> str:
    words = text.split()
    result = []
    for word in words:
        clean = word.strip(string.punctuation).casefold()
        if clean in ABBREVIATIONS and rng.random() < 0.22:
            replacement = rng.choice(ABBREVIATIONS[clean])
            result.append(word.replace(word.strip(string.punctuation), replacement))
        else:
            result.append(word)
    return " ".join(result)


def _apply_typo(rng: random.Random, text: str) -> str:
    if rng.random() > 0.18:
        return text
    words = [word for word in text.split() if len(word.strip(string.punctuation)) >= 5]
    if not words:
        return text
    target = rng.choice(words)
    clean = target.strip(string.punctuation)
    index = rng.randrange(1, len(clean))
    typo_types = ["drop", "swap", "double"]
    typo_type = rng.choice(typo_types)
    if typo_type == "drop":
        changed = clean[:index] + clean[index + 1 :]
    elif typo_type == "swap" and index < len(clean) - 1:
        changed = clean[:index] + clean[index + 1] + clean[index] + clean[index + 2 :]
    else:
        changed = clean[:index] + clean[index] + clean[index:]
    return text.replace(clean, changed, 1)


def _apply_case_variation(rng: random.Random, text: str) -> str:
    roll = rng.random()
    if roll < 0.18:
        return text.lower()
    if roll < 0.28:
        return text.upper()
    if roll < 0.44:
        return text.title()
    return text


def _shuffle_tail(rng: random.Random, parts: list[str]) -> list[str]:
    if rng.random() > 0.28 or len(parts) < 4:
        return parts
    head = parts[:1]
    tail = parts[1:]
    rng.shuffle(tail)
    return head + tail


def _description(rng: random.Random, category: str) -> str:
    config = CATEGORY_CONFIG[category]
    merchant = rng.choice(config["merchants"])
    if rng.random() < 0.38:
        merchant = _random_merchant(rng)
    obj = rng.choice(config["objects"])
    context = rng.choice(config["contexts"])
    noise = rng.choice(NOISE_TERMS)
    month = rng.choice(MONTHS)
    ref = _random_reference(rng)

    templates = [
        "{merchant} {obj} {context}",
        "{noise} {merchant} {obj}",
        "{obj} at {merchant} {noise}",
        "{merchant} - {obj} - {ref}",
        "{month} {obj} {noise}",
        "{context} {obj} from {merchant}",
        "{merchant} {noise} {context}",
        "{obj} {context} {ref}",
        "{noise} for {obj} {month}",
        "{merchant} {obj} {month} {noise}",
    ]
    text = rng.choice(templates).format(
        merchant=merchant,
        obj=obj,
        context=context,
        noise=noise,
        month=month,
        ref=ref,
    )

    if rng.random() < 0.12:
        text = rng.choice(AMBIGUOUS_EXAMPLES[category])

    parts = _shuffle_tail(rng, text.split())
    text = " ".join(parts)
    text = _apply_abbreviations(rng, text)
    text = _apply_typo(rng, text)
    text = _apply_case_variation(rng, text)
    return " ".join(text.split())


def generate_rows() -> list[dict[str, str]]:
    rng = random.Random(RANDOM_SEED)
    seen: set[str] = set()
    rows: list[dict[str, str]] = []

    for category, descriptions in AMBIGUOUS_EXAMPLES.items():
        for description in descriptions:
            key = f"{description.casefold()}::{category}"
            if key not in seen:
                seen.add(key)
                rows.append({"description": description, "category": category})

    for category in CATEGORY_CONFIG:
        attempts = 0
        while sum(1 for row in rows if row["category"] == category) < ROWS_PER_CATEGORY:
            attempts += 1
            if attempts > ROWS_PER_CATEGORY * 100:
                raise RuntimeError(f"Could not generate enough unique rows for {category}")
            description = _description(rng, category)
            key = f"{description.casefold()}::{category}"
            if key in seen:
                continue
            seen.add(key)
            rows.append({"description": description, "category": category})

    rng.shuffle(rows)
    return rows


def main() -> None:
    rows = generate_rows()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["description", "category"])
        writer.writeheader()
        writer.writerows(rows)

    categories = sorted({row["category"] for row in rows})
    print(f"Generated {len(rows)} rows")
    print(f"Categories: {', '.join(categories)}")
    print(f"Rows per category: {ROWS_PER_CATEGORY}")
    print(f"Saved training data to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
