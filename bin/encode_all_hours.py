"""Force-encode hours 00..13 of today via the live skycam_processor functions."""
import sys
sys.path.insert(0, "/home/peter/Berrylands/gardencam")
import logging
import boto3
from skycam_processor import encode_hour, rerender_day, AWS_REGION

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("oneshot")
s3 = boto3.client("s3", region_name=AWS_REGION)

DATE = "2026-05-18"
for h in range(14):
    hh = f"{h:02d}"
    log.info(f"=== encoding {DATE}/{hh} ===")
    encode_hour(DATE, hh, log, force=True, s3=s3)

log.info("=== day rerender ===")
rerender_day(DATE, log, s3=s3)
