"""Add (or remove) realistic sample listings for demos.

Photos come from Wikimedia Commons, public-domain or CC0 only. Listings are owned by
real Discord accounts so making an offer on one starts a real negotiation; floors are
KMS-encrypted like any other listing. Every sample is tagged `sample=true`.

    python scripts/seed_samples.py --sellers 111,222        # add
    python scripts/seed_samples.py --remove                  # remove all samples
"""

import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import boto3
from boto3.dynamodb.conditions import Attr
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from web_call import REGION, stack_outputs  # noqa: E402

import store  # noqa: E402
from scheduler import CAMPUS_TZ  # noqa: E402

UA = "haggle-seed/0.1 (student hackathon project; contact via github.com/kp-krish)"
FREE_LICENSES = ("cc0", "public domain", "pd")

# Each photo was picked by eye from Wikimedia Commons (public domain or CC0).
ITEMS = [
    dict(
        title="Microwave, 700 W",
        category="appliances",
        asking=35,
        floor=22,
        area="central",
        desc="Compact, fits on a dorm shelf. Turntable and timer work fine.",
        photo='File:Microwave oven "Erisson".jpg',
    ),
    dict(
        title="Road bike, medium frame",
        category="bikes-transport",
        asking=160,
        floor=120,
        area="south",
        large=True,
        desc="Recently tuned with new tubes. Lock not included.",
        photo="File:'Parked Racer' in Soho on 'Friday party night'..jpg",
    ),
    dict(
        title="TI-84 Plus graphing calculator",
        category="electronics",
        asking=55,
        floor=38,
        area="any",
        desc="Works for calculus and stats classes. Fresh batteries.",
        photo="File:TI-84 Plus on white background.JPG",
    ),
    dict(
        title="Electric kettle",
        category="kitchen",
        asking=12,
        floor=7,
        area="central",
        desc="Boils in about two minutes, with auto shut-off.",
        photo="File:Electric kettle phillips white.JPG",
    ),
    dict(
        title="Acoustic guitar with soft case",
        category="other",
        asking=90,
        floor=65,
        area="any",
        desc="Full size, new strings. Soft case included.",
        photo="File:Fender California Series Acoustic Guitar (serial no. CSC10001615) "
        "(2018-04-26 13.21.46 Piqsels.com id olkmb).jpg",
    ),
    dict(
        title="Skateboard",
        category="sports-outdoors",
        asking=30,
        floor=18,
        area="north",
        desc="Smooth bearings, some scuffs on the deck.",
        photo="File:Skateboard upside.jpg",
    ),
    dict(
        title="Bedside lamp",
        category="decor",
        asking=15,
        floor=9,
        area="north",
        desc="Soft warm light, linen shade. Bulb included.",
        photo="File:MarsPerSundstedtAteljeLyktan.png",
    ),
    dict(
        title="Small desk fan",
        category="appliances",
        asking=10,
        floor=6,
        area="south",
        desc="Quiet, plugs into USB. Clips to a shelf or stands on the desk.",
        photo="File:Small Desk Fan 1.jpg",
    ),
    dict(
        title='22" computer monitor',
        category="electronics",
        asking=60,
        floor=42,
        area="central",
        desc="1080p, VGA and DVI inputs. Stand included, no dead pixels.",
        photo="File:Computer monitor.jpg",
    ),
    dict(
        title="Over-ear headphones",
        category="electronics",
        asking=25,
        floor=15,
        area="any",
        desc="Wired, comfortable for long study sessions. Cable has no shorts.",
        photo="File:Headphones on wood in black and white (Unsplash).jpg",
    ),
    dict(
        title="Red laptop backpack",
        category="clothing",
        asking=20,
        floor=12,
        area="central",
        desc="Fits a 15-inch laptop. All zippers work.",
        photo="File:Wenger backpack.jpg",
    ),
    dict(
        title="Textbook bundle",
        category="textbooks",
        asking=40,
        floor=25,
        area="north",
        desc="Eight paperback course books in good shape, light highlighting.",
        photo="File:(Indonesia) Buku SMA Kelas 10 - Kurikulum Merdeka.jpg",
    ),
]


def fetch(url: str) -> bytes:
    """GET with a polite User-Agent, backing off when Commons rate-limits."""
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("rate limited by Commons")


def commons_photo(file_title: str) -> tuple[bytes, dict]:
    """A specific Commons file at ~1200px, refusing anything not public domain or CC0."""
    params = {
        "action": "query", "format": "json", "titles": file_title,
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": "1200",
    }  # fmt: skip
    data = json.loads(
        fetch("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params))
    )
    page = next(iter(data["query"]["pages"].values()))
    info = page["imageinfo"][0]
    license_name = info.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")
    if not any(f in license_name.lower() for f in FREE_LICENSES):
        raise ValueError(f"{file_title} is {license_name!r}, not public domain or CC0")
    raw = fetch(info.get("thumburl") or info["url"])
    return raw, {"source": info.get("descriptionurl"), "license": license_name, "title": file_title}


def square_jpeg(raw: bytes) -> bytes:
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    side = min(img.size)
    left, top = (img.width - side) // 2, (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((1200, 1200))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


def week_windows() -> list[dict]:
    """Free 10:00-18:00 campus time every day for the next week."""
    tz = CAMPUS_TZ
    today = datetime.now(tz).date()
    out = []
    for d in range(1, 8):
        day = today + timedelta(days=d)
        start = datetime(day.year, day.month, day.day, 10, tzinfo=tz)
        out.append({"start": start.isoformat(), "end": (start + timedelta(hours=8)).isoformat()})
    return out


def listings_table_name() -> str:
    cf = boto3.client("cloudformation", region_name=REGION)
    resource = cf.describe_stack_resource(StackName="haggle-dev", LogicalResourceId="ListingsTable")
    return resource["StackResourceDetail"]["PhysicalResourceId"]


def add(sellers: list[str]) -> None:
    out = stack_outputs()
    os.environ.setdefault("AWS_DEFAULT_REGION", REGION)
    os.environ["LISTINGS_TABLE"] = listings_table_name()
    os.environ["LIMITS_KEY_ID"] = "alias/haggle-dev-limits"
    s3, bucket = boto3.client("s3", region_name=REGION), out["PhotosBucketName"]
    windows = week_windows()

    for i, item in enumerate(ITEMS):
        seller = sellers[i % len(sellers)]
        title, asking, area = item["title"], item["asking"], item["area"]
        try:
            raw, credit = commons_photo(item["photo"])
        except Exception as e:
            print(f"  skip {title}: {e}")
            continue
        listing_id = store.new_id("lst")
        key = f"photos/{listing_id}.jpg"
        s3.put_object(Bucket=bucket, Key=key, Body=square_jpeg(raw), ContentType="image/jpeg")
        created = (
            datetime.now().astimezone() - timedelta(minutes=37 * (len(ITEMS) - i))
        ).isoformat(timespec="seconds")
        store.table("listings").put_item(
            Item={
                "listing_id": listing_id,
                "seller_id": seller,
                "seller_notes": item["desc"],
                "title": title,
                "description": item["desc"],
                "category": item["category"],
                "asking": asking,
                "area": area,
                "large": item.get("large", False),
                "style": "balanced",
                "photo_key": key,
                "photo_credit": credit,
                "windows": windows,
                "floor_enc": store.encrypt_limit(item["floor"], f"listing#{listing_id}", seller),
                "status": "open",
                "source": "web",
                "sample": True,
                "created_at": created,
                "published_at": created,
            }
        )
        print(f"  added {title:32} ${asking:<4} {area:8} seller …{seller[-4:]}  {credit['title']}")
        time.sleep(0.5)  # be gentle with Commons


def remove() -> None:
    out = stack_outputs()
    table = boto3.resource("dynamodb", region_name=REGION).Table(listings_table_name())
    s3 = boto3.client("s3", region_name=REGION)
    items = table.scan(FilterExpression=Attr("sample").eq(True))["Items"]
    for item in items:
        if item.get("photo_key"):
            s3.delete_object(Bucket=out["PhotosBucketName"], Key=item["photo_key"])
        table.delete_item(Key={"listing_id": item["listing_id"]})
        print(f"  removed {item.get('title')}")
    print(f"Removed {len(items)} sample listings")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sellers", help="comma-separated Discord user ids that own the samples")
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    if args.remove:
        remove()
    elif args.sellers:
        add([s.strip() for s in args.sellers.split(",") if s.strip()])
    else:
        parser.error("pass --sellers or --remove")


if __name__ == "__main__":
    main()
