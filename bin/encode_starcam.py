import sys, logging, boto3
sys.path.insert(0, "/home/peter/Berrylands/gardencam")
from starcam_processor import encode_hour, rerender_day, AWS_REGION
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("oneshot-starcam")
s3 = boto3.client("s3", region_name=AWS_REGION)
DATE = "2026-05-18"
for h in range(15):
    hh = f"{h:02d}"
    log.info(f"=== encoding starcam {DATE}/{hh} ===")
    encode_hour(DATE, hh, log, force=True, s3=s3)
log.info("=== starcam day rerender ===")
rerender_day(DATE, log, s3=s3)
