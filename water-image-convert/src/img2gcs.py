import functools
import os
from datetime import date, datetime
from typing import Optional

import ee
import typed_argparse as tap
from tqdm import tqdm

ee.Initialize(
    credentials=ee.ServiceAccountCredentials(
        email=os.environ["GOOGLE_SERVICE_ACCOUNT"],
        key_file=os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
    ),
    project=os.environ["GOOGLE_CLOUD_PROJECT"],
)


class Img2GCSArgs(tap.TypedArgs):
    start_date: date = tap.arg(
        "-sd",
        "--start-date",
        type=lambda x: datetime.strptime(x, "%d-%m-%Y").date(),
    )
    end_date: date = tap.arg(
        "-ed",
        "--end-date",
        type=lambda x: datetime.strptime(x, "%d-%m-%Y").date(),
        default=datetime.strftime(date.today(), "%d-%m-%Y"),
    )
    roi_start: list = tap.arg(
        "-rs",
        "--roi-start",
        type=lambda x: list(map(float, x.replace(" ", "").split(",", maxsplit=1))),
    )
    roi_end: list = tap.arg(
        "-re",
        "--roi-end",
        type=lambda x: list(map(float, x.replace(" ", "").split(",", maxsplit=1))),
    )
    cloud_level: float = tap.arg("-cl", "--cloud-level", default=50.0)
    ndwi_threshold: Optional[float] = tap.arg("-nt", "--ndwi-threshold")
    bucket: str = tap.arg("-b", "--bucket")
    prefix: Optional[str] = tap.arg("-p", "--prefix")
    scale: float = tap.arg("-s", "--scale", default=1.0)
    max_pixel: int = tap.arg("-mp", "--max-pixel", default=100000000)


def calculate_chlo(image: ee.Image):
    r = image.expression(
        "log10(B2 / B3)", {"B2": image.select("B2"), "B3": image.select("B3")}
    ).rename("R")
    chlo = (
        image.expression(
            "10 ** (A0 + A1 * R + A2 * (R ** 2) + A3 * (R ** 3)) + A4",
            {
                "A0": 0.354,
                "A1": -2.8009,
                "A2": 2.902,
                "A3": -1.977,
                "A4": 0.0750,
                "R": r,
            },
        )
        .toFloat()
        .rename("CHLO")
    )
    return image.addBands(chlo)


def calculate_ndwi(image: ee.Image):
    ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")
    return image.addBands(ndwi)


def ndwi_filter(ndwi_threshold: float, image: ee.Image):
    chlo_masked = (
        image.select("CHLO")
        .updateMask(image.select("NDWI").gte(ndwi_threshold))
        .rename("CHLO")
    )
    return image.addBands(chlo_masked, overwrite=True)


def img_to_gcs(args: Img2GCSArgs):
    north, west = args.roi_start
    south, east = args.roi_end
    region = ee.Geometry.BBox(west, south, east, north)

    features = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(args.start_date.isoformat(), args.end_date.isoformat())
        .filterBounds(region)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", args.cloud_level))
        .map(calculate_chlo)
        .map(calculate_ndwi)
    )

    if args.ndwi_threshold is not None:
        features = features.map(
            functools.partial(ndwi_filter, args.ndwi_threshold)
        ).select("CHLO")
    else:
        features = features.select(["CHLO", "NDWI"])

    prefix = "gee-chlo-ndwi/{}".format(
        args.prefix or ",".join(map(str, [north, west, south, east]))
    )

    for i in tqdm(range(features.size().getInfo())):
        image = ee.Image(ee.List(features.toList(1, i)).get(0))
        stem = image.date().format().getInfo()
        name = "{}/{}".format(prefix, stem)

        task = ee.batch.Export.image.toCloudStorage(
            image=image,
            bucket=args.bucket,
            description=stem,
            fileNamePrefix=name,
            scale=args.scale,
            crs="EPSG:4326",
            region=region,
            maxPixels=args.max_pixel,
        )
        task.start()


def main() -> None:
    tap.Parser(Img2GCSArgs).bind(img_to_gcs).run()
