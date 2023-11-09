import io
import tempfile
import time
import webbrowser
from pathlib import Path
from typing import Optional

import branca.colormap as cm
import folium
import numpy as np
import rasterio
import typed_argparse as tap
from google.cloud.storage import Client


class GCS2MatrixArgs(tap.TypedArgs):
    path: str = tap.arg("-p", "--path", type=lambda x: x.removeprefix("gs://"))
    zoom: int = tap.arg("-z", "--zoom", default=16)
    output: Optional[Path] = tap.arg("-o", "--output")
    ndwi_threshold: float = tap.arg("-nt", "--ndwi-threshold", default=0.0)


def download_dataset(bucket: str, key: str):
    client = Client()
    bucket = client.get_bucket(bucket)
    blob = bucket.get_blob(key)

    tiff_fp = io.BytesIO()
    blob.download_to_file(tiff_fp)
    tiff_fp.seek(0)

    return rasterio.open(tiff_fp)


def build_chlo_cmap(dataset, ndwi_threshold: float):
    chlo = dataset.read(1)

    if dataset.count > 1:
        ndwi = dataset.read(2)
        chlo = np.where(ndwi > ndwi_threshold, chlo, np.nan)

    lower = -1
    upper = 101
    chlo_nonan = np.nan_to_num(chlo, nan=lower)

    chlo_cmap = cm.LinearColormap(
        colors=["#ffffff", "#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"],
        index=[lower, 0, 10, 50, 100, upper],
        caption="Chlorophyll-a concentration",
        vmin=lower,
        vmax=upper,
        tick_labels=[0, 100],
    )
    return chlo_nonan, chlo_cmap


def gcs_to_matrix(args: GCS2MatrixArgs):
    bucket, key = args.path.split("/", maxsplit=1)

    dataset = download_dataset(bucket, key)
    region = dataset.bounds

    chlo_map = folium.Map(
        [(region.top + region.bottom) / 2, (region.left + region.right) / 2],
        zoom_start=args.zoom,
    )

    chlo_nonan, chlo_cmap = build_chlo_cmap(dataset, args.ndwi_threshold)
    folium.raster_layers.ImageOverlay(
        name="Chlorophyll-a concentration",
        image=chlo_nonan,
        bounds=[
            [region.top, region.left],
            [region.bottom, region.right],
        ],
        interactive=True,
        cross_origin=False,
        zindex=1,
        overlay=True,
        colormap=chlo_cmap,
    ).add_to(chlo_map)
    chlo_cmap.add_to(chlo_map)
    folium.LayerControl().add_to(chlo_map)

    _temp_output = tempfile.NamedTemporaryFile(suffix=".html")
    output = Path(args.output or _temp_output.name).resolve(False)
    chlo_map.save(str(output))
    webbrowser.open("file://{}".format(output))
    if not args.output:
        time.sleep(5)


def main() -> None:
    tap.Parser(GCS2MatrixArgs).bind(gcs_to_matrix).run()
